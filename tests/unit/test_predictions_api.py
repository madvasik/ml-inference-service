from unittest.mock import Mock, patch

from backend.app.models import Balance, LoyaltyTier, Prediction, PredictionStatus, Transaction
from tests.helpers import auth_headers


def test_prediction_creation_persists_discount_snapshot(client, access_token_for, test_user, test_ml_model, db_session):
    test_user.loyalty_tier = LoyaltyTier.GOLD
    test_user.loyalty_discount_percent = 20
    db_session.commit()

    with patch("backend.app.api.predictions.execute_prediction.delay", return_value=Mock(id="task-1")):
        response = client.post(
            "/api/v1/predictions",
            headers=auth_headers(access_token_for(test_user)),
            json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
        )

    assert response.status_code == 202
    prediction = db_session.get(Prediction, response.json()["prediction_id"])
    assert prediction.status == PredictionStatus.PENDING
    assert prediction.discount_percent == 20
    assert prediction.discount_amount == 2
    assert prediction.credits_spent == 8
    assert prediction.task_id == "task-1"


def test_prediction_requires_balance(client, access_token_for, test_user, test_ml_model, db_session):
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).one()
    balance.credits = 0
    db_session.commit()

    response = client.post(
        "/api/v1/predictions",
        headers=auth_headers(access_token_for(test_user)),
        json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
    )

    assert response.status_code == 402


def test_queue_failure_marks_prediction_failed_without_transaction(client, access_token_for, test_user, test_ml_model, db_session):
    with patch("backend.app.api.predictions.execute_prediction.delay", side_effect=RuntimeError("queue down")):
        response = client.post(
            "/api/v1/predictions",
            headers=auth_headers(access_token_for(test_user)),
            json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
        )

    assert response.status_code == 503
    prediction = db_session.query(Prediction).filter(Prediction.user_id == test_user.id).order_by(Prediction.id.desc()).one()
    assert prediction.status == PredictionStatus.FAILED
    assert prediction.failure_reason == "queue_unavailable"
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 0


def test_prediction_endpoints_are_scoped_to_owner(client, access_token_for, admin_user, test_ml_model):
    response = client.post(
        "/api/v1/predictions",
        headers=auth_headers(access_token_for(admin_user)),
        json={"model_id": test_ml_model.id, "input_data": {"feature1": 1.0, "feature2": 2.0}},
    )

    assert response.status_code == 404
