from unittest.mock import patch

from fastapi import status

from backend.app.models import Balance
from tests.helpers import auth_headers


def test_prediction_requires_sufficient_balance(client, db_session, test_user, test_ml_model):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "testpassword"},
    )
    assert login_response.status_code == status.HTTP_200_OK
    headers = auth_headers(login_response.json()["access_token"])

    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    assert balance is not None
    balance.credits = 0
    db_session.commit()

    prediction_response = client.post(
        "/api/v1/predictions",
        headers=headers,
        json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
    )
    assert prediction_response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert "Insufficient balance" in prediction_response.json()["detail"]


def test_queue_failure_marks_prediction_failed(client, test_user, test_ml_model):
    from backend.app.security import create_access_token

    token = create_access_token(data={"sub": str(test_user.id), "email": test_user.email})
    headers = auth_headers(token)

    with patch("backend.app.api.routes.predictions.execute_prediction.delay", side_effect=RuntimeError("queue down")):
        response = client.post(
            "/api/v1/predictions",
            headers=headers,
            json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    detail = response.json()["detail"]
    assert "queue" in detail.lower()
