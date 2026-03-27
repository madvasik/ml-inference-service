from unittest.mock import Mock, patch

from backend.app.models import PredictionStatus, Transaction
from backend.app.worker import execute_prediction
from tests.helpers import auth_headers


def test_full_workflow_charges_only_after_success(client, db_session, test_model_file):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "workflow@example.com", "password": "password123"},
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]
    headers = auth_headers(token)

    payment_response = client.post("/api/v1/billing/payments", headers=headers, json={"amount": 100})
    assert payment_response.status_code == 200

    with open(test_model_file, "rb") as file:
        model_response = client.post(
            "/api/v1/models/upload",
            headers=headers,
            files={"file": ("model.pkl", file, "application/octet-stream")},
            data={"model_name": "workflow-model"},
        )
    assert model_response.status_code == 201
    model_id = model_response.json()["id"]

    with patch("backend.app.api.predictions.execute_prediction.delay", return_value=Mock(id="test-task-id")):
        create_response = client.post(
            "/api/v1/predictions",
            headers=headers,
            json={"model_id": model_id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
        )
    assert create_response.status_code == 202
    prediction_id = create_response.json()["prediction_id"]

    balance_before_worker = client.get("/api/v1/billing/balance", headers=headers)
    assert balance_before_worker.json()["credits"] == 100

    execute_prediction._db = db_session
    worker_result = execute_prediction.run(prediction_id=prediction_id)
    assert worker_result["status"] == "completed"

    prediction_response = client.get(f"/api/v1/predictions/{prediction_id}", headers=headers)
    balance_response = client.get("/api/v1/billing/balance", headers=headers)
    transaction_count = db_session.query(Transaction).filter(Transaction.user_id == prediction_response.json()["user_id"]).count()

    assert prediction_response.status_code == 200
    assert prediction_response.json()["status"] == PredictionStatus.COMPLETED.value
    assert prediction_response.json()["result"] is not None
    assert balance_response.json()["credits"] == 90
    assert transaction_count == 2
