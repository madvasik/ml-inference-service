from unittest.mock import patch

from fastapi import status

from tests.helpers import auth_headers


def test_full_workflow(client, test_model_file):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "workflow@example.com", "password": "password123"},
    )
    assert register_response.status_code == status.HTTP_201_CREATED
    token = register_response.json()["access_token"]
    headers = auth_headers(token)

    with open(test_model_file, "rb") as file:
        model_response = client.post(
            "/api/v1/models/upload",
            headers=headers,
            files={"file": ("model.pkl", file, "application/octet-stream")},
            data={"model_name": "workflow_model"},
        )
    assert model_response.status_code == status.HTTP_201_CREATED
    model_id = model_response.json()["id"]

    payment_response = client.post(
        "/api/v1/billing/payments",
        headers=headers,
        json={"amount": 100},
    )
    assert payment_response.status_code == status.HTTP_200_OK

    with patch("backend.app.api.routes.predictions.execute_prediction.delay") as mock_celery:
        mock_task = type("MockTask", (), {"id": "test-task-id"})()
        mock_celery.return_value = mock_task

        prediction_response = client.post(
            "/api/v1/predictions",
            headers=headers,
            json={"model_id": model_id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
        )
        assert prediction_response.status_code == status.HTTP_202_ACCEPTED
        assert prediction_response.json()["status"] == "pending"

    balance_response = client.get("/api/v1/billing/balance", headers=headers)
    assert balance_response.status_code == status.HTTP_200_OK
    assert balance_response.json()["credits"] == 100

    transactions_response = client.get("/api/v1/billing/transactions", headers=headers)
    assert transactions_response.status_code == status.HTTP_200_OK
    assert len(transactions_response.json()["transactions"]) >= 1
