from unittest.mock import Mock, patch

from datetime import datetime, timezone

from backend.app.models import Balance, Prediction, PredictionStatus, Transaction
from backend.app.worker import execute_prediction, recalculate_monthly_loyalty


def _create_prediction(db_session, test_user, test_ml_model, credits_spent: int = 10) -> Prediction:
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature1": 1.0, "feature2": 2.0},
        status=PredictionStatus.PENDING,
        base_cost=10,
        discount_percent=0,
        discount_amount=0,
        credits_spent=credits_spent,
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)
    return prediction


@patch("backend.app.worker.load_model")
@patch("backend.app.worker.predict")
def test_worker_completes_prediction_and_debits_once(mock_predict, mock_load_model, db_session, test_user, test_ml_model):
    prediction = _create_prediction(db_session, test_user, test_ml_model)
    mock_load_model.return_value = Mock()
    mock_predict.return_value = {"prediction": 1}

    execute_prediction._db = db_session
    result = execute_prediction.run(prediction_id=prediction.id)
    duplicate = execute_prediction.run(prediction_id=prediction.id)

    db_session.refresh(prediction)
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).one()
    assert result["status"] == "completed"
    assert duplicate["status"] == "completed"
    assert prediction.status == PredictionStatus.COMPLETED
    assert balance.credits == 990
    assert db_session.query(Transaction).count() == 1


@patch("backend.app.worker.load_model")
@patch("backend.app.worker.predict")
def test_worker_marks_prediction_failed_when_balance_is_gone(mock_predict, mock_load_model, db_session, test_user, test_ml_model):
    prediction = _create_prediction(db_session, test_user, test_ml_model, credits_spent=1001)
    mock_load_model.return_value = Mock()
    mock_predict.return_value = {"prediction": 1}

    execute_prediction._db = db_session
    result = execute_prediction.run(prediction_id=prediction.id)

    db_session.refresh(prediction)
    assert result["status"] == "failed"
    assert prediction.failure_reason == "insufficient_credits"
    assert db_session.query(Transaction).count() == 0


@patch("backend.app.worker.load_model", side_effect=ValueError("broken model"))
def test_worker_keeps_credits_when_model_load_fails(_mock_load_model, db_session, test_user, test_ml_model):
    prediction = _create_prediction(db_session, test_user, test_ml_model)

    execute_prediction._db = db_session
    result = execute_prediction.run(prediction_id=prediction.id)

    db_session.refresh(prediction)
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).one()
    assert result["status"] == "failed"
    assert prediction.status == PredictionStatus.FAILED
    assert "broken model" in prediction.failure_reason
    assert balance.credits == 1000
    assert db_session.query(Transaction).count() == 0


def test_monthly_loyalty_task_recalculates_users(db_session, test_user, test_ml_model):
    db_session.add(
        Prediction(
            user_id=test_user.id,
            model_id=test_ml_model.id,
            input_data={"feature1": 1.0, "feature2": 2.0},
            result={"prediction": 1},
            status=PredictionStatus.COMPLETED,
            base_cost=10,
            discount_percent=0,
            discount_amount=0,
            credits_spent=10,
            completed_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    recalculate_monthly_loyalty._db = None
    result = recalculate_monthly_loyalty.run()

    assert result["updated_users"] >= 1
