from unittest.mock import patch

from backend.app.models import Prediction, PredictionStatus, Transaction
from backend.app.worker import execute_prediction
from tests.helpers import auth_headers


def test_queue_failure_marks_prediction_failed_without_debit(client, db_session, test_user, test_ml_model, access_token_for):
    headers = auth_headers(access_token_for(test_user))

    with patch("backend.app.api.predictions.execute_prediction.delay", side_effect=RuntimeError("queue down")):
        response = client.post(
            "/api/v1/predictions",
            headers=headers,
            json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
        )

    assert response.status_code == 503
    prediction = db_session.query(Prediction).filter(Prediction.user_id == test_user.id).order_by(Prediction.id.desc()).one()
    assert prediction.status == PredictionStatus.FAILED
    assert prediction.failure_reason == "queue_unavailable"
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 0


def test_worker_failure_keeps_balance_unchanged(client, db_session, test_user, test_ml_model, access_token_for):
    headers = auth_headers(access_token_for(test_user))

    with patch("backend.app.api.predictions.execute_prediction.delay", return_value=type("Task", (), {"id": "queued"})()):
        create_response = client.post(
            "/api/v1/predictions",
            headers=headers,
            json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
        )
    prediction_id = create_response.json()["prediction_id"]

    execute_prediction._db = db_session
    with patch("backend.app.worker.load_model", side_effect=ValueError("broken model")):
        result = execute_prediction.run(prediction_id=prediction_id)

    balance_response = client.get("/api/v1/billing/balance", headers=headers)
    prediction_response = client.get(f"/api/v1/predictions/{prediction_id}", headers=headers)

    assert result["status"] == "failed"
    assert balance_response.json()["credits"] == 1000
    assert prediction_response.json()["status"] == PredictionStatus.FAILED.value
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 0
