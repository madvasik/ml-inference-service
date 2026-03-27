from unittest.mock import Mock, patch

from backend.app.domain.models.prediction import Prediction, PredictionStatus
from backend.app.workers.prediction_tasks import execute_prediction


def _create_prediction(db_session, test_user, test_ml_model, credits_spent: int = 10) -> Prediction:
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature1": 1.5},
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


@patch("backend.app.workers.prediction_tasks.load_model")
@patch("backend.app.workers.prediction_tasks.predict")
@patch("backend.app.workers.prediction_tasks.charge_prediction")
def test_execute_prediction_success(mock_charge_prediction, mock_predict, mock_load_model, db_session, test_user, test_ml_model):
    prediction = _create_prediction(db_session, test_user, test_ml_model)
    mock_load_model.return_value = Mock()
    mock_predict.return_value = {"prediction": [0.85]}
    mock_charge_prediction.return_value = (True, Mock())

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=prediction.id)

    assert result["status"] == "completed"
    db_session.refresh(prediction)
    assert prediction.status == PredictionStatus.COMPLETED


def test_execute_prediction_model_not_found(db_session, test_user, test_ml_model):
    prediction = _create_prediction(db_session, test_user, test_ml_model)
    prediction.model_id = 99999
    db_session.commit()

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=prediction.id)

    assert result["status"] == "failed"
    db_session.refresh(prediction)
    assert prediction.failure_reason == "model_not_found"


@patch("backend.app.workers.prediction_tasks.load_model")
@patch("backend.app.workers.prediction_tasks.predict")
@patch("backend.app.workers.prediction_tasks.charge_prediction")
def test_execute_prediction_insufficient_credits(mock_charge_prediction, mock_predict, mock_load_model, db_session, test_user, test_ml_model):
    prediction = _create_prediction(db_session, test_user, test_ml_model)
    mock_load_model.return_value = Mock()
    mock_predict.return_value = {"prediction": [0.85]}
    mock_charge_prediction.return_value = (False, None)

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=prediction.id)

    assert result["status"] == "failed"
    db_session.refresh(prediction)
    assert prediction.failure_reason == "insufficient_credits"
