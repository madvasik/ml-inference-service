from unittest.mock import Mock, patch

from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError

from backend.app.billing import charge_prediction
from backend.app.models import Balance, Prediction, PredictionStatus, Transaction, TransactionType
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

    result = execute_prediction.run(prediction_id=prediction.id)

    db_session.refresh(prediction)
    assert result["status"] == "failed"
    assert prediction.failure_reason == "insufficient_credits"
    assert db_session.query(Transaction).count() == 0


@patch("backend.app.worker.load_model", side_effect=ValueError("broken model"))
def test_worker_keeps_credits_when_model_load_fails(_mock_load_model, db_session, test_user, test_ml_model):
    prediction = _create_prediction(db_session, test_user, test_ml_model)

    result = execute_prediction.run(prediction_id=prediction.id)

    db_session.refresh(prediction)
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).one()
    assert result["status"] == "failed"
    assert prediction.status == PredictionStatus.FAILED
    assert prediction.failure_reason == "execution_error"
    assert balance.credits == 1000
    assert db_session.query(Transaction).count() == 0


@patch("backend.app.worker.load_model")
@patch("backend.app.worker.predict", side_effect=OperationalError("stmt", None, None))
def test_operational_error_before_max_retries_does_not_refund(
    _mock_predict, _mock_load, db_session, test_user, test_ml_model
):
    prediction = _create_prediction(db_session, test_user, test_ml_model)
    charge_prediction(db_session, prediction)
    db_session.commit()
    db_session.refresh(prediction)

    with patch("backend.app.worker.refund_prediction_if_debited") as mock_refund:
        with patch.object(execute_prediction, "retry", side_effect=RuntimeError("retry_scheduled")):
            with patch.object(execute_prediction.request, "retries", 0):
                with patch.object(execute_prediction, "max_retries", 3):
                    try:
                        execute_prediction.run(prediction_id=prediction.id)
                    except RuntimeError as exc:
                        if str(exc) != "retry_scheduled":
                            raise
    mock_refund.assert_not_called()
    assert db_session.query(Transaction).filter(Transaction.type == TransactionType.REFUND).count() == 0


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

    result = recalculate_monthly_loyalty.run()

    assert result["updated_users"] >= 1
