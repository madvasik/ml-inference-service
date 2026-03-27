from unittest.mock import Mock, patch

import pytest

from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.tasks.prediction_tasks import DatabaseTask, execute_prediction


@pytest.fixture
def mock_prediction(db_session, test_user, test_ml_model):
    """Создание тестового предсказания."""
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature1": 1.0, "feature2": 2.0},
        status=PredictionStatus.PENDING,
        base_cost=10,
        discount_percent=0,
        discount_amount=0,
        credits_spent=10,
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)
    return prediction


@patch("backend.app.tasks.prediction_tasks.load_model")
@patch("backend.app.tasks.prediction_tasks.predict")
@patch("backend.app.tasks.prediction_tasks.charge_prediction")
def test_execute_prediction_success_integration(
    mock_charge_prediction,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
):
    mock_load_model.return_value = Mock()
    mock_predict.return_value = {"prediction": [0.85], "probabilities": [0.15, 0.85]}
    mock_charge_prediction.return_value = (True, Mock())

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=mock_prediction.id)

    assert result["status"] == "completed"
    assert result["prediction_id"] == mock_prediction.id
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.COMPLETED
    assert mock_prediction.result is not None
    assert mock_prediction.completed_at is not None


@patch("backend.app.tasks.prediction_tasks.load_model")
def test_execute_prediction_not_found(mock_load_model, db_session):
    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=99999)

    assert result["status"] == "failed"
    assert "not found" in result["error"].lower()
    mock_load_model.assert_not_called()


@patch("backend.app.tasks.prediction_tasks.load_model")
def test_execute_prediction_model_not_found_integration(mock_load_model, db_session, mock_prediction):
    mock_prediction.model_id = 99999
    db_session.commit()

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=mock_prediction.id)

    assert result["status"] == "failed"
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED
    assert mock_prediction.failure_reason == "model_not_found"
    mock_load_model.assert_not_called()


@patch("backend.app.tasks.prediction_tasks.load_model")
@patch("backend.app.tasks.prediction_tasks.predict")
@patch("backend.app.tasks.prediction_tasks.charge_prediction")
def test_execute_prediction_insufficient_credits_integration(
    mock_charge_prediction,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
):
    mock_load_model.return_value = Mock()
    mock_predict.return_value = {"prediction": [0.85]}
    mock_charge_prediction.return_value = (False, None)

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=mock_prediction.id)

    assert result["status"] == "failed"
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED
    assert mock_prediction.failure_reason == "insufficient_credits"


@patch("backend.app.tasks.prediction_tasks.load_model")
@patch("backend.app.tasks.prediction_tasks.predict")
@patch("backend.app.tasks.prediction_tasks.charge_prediction")
def test_execute_prediction_load_model_error(
    mock_charge_prediction,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
):
    mock_load_model.side_effect = ValueError("Failed to load model")

    task = execute_prediction
    task._db = db_session
    original_max_retries = task.max_retries
    task.max_retries = 0

    try:
        result = task.run(prediction_id=mock_prediction.id)
    finally:
        task.max_retries = original_max_retries

    assert result["status"] == "failed"
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED
    assert "Failed to load model" in mock_prediction.failure_reason
    mock_charge_prediction.assert_not_called()
    mock_predict.assert_not_called()


@patch("backend.app.tasks.prediction_tasks.load_model")
@patch("backend.app.tasks.prediction_tasks.predict")
@patch("backend.app.tasks.prediction_tasks.charge_prediction")
def test_execute_prediction_predict_error(
    mock_charge_prediction,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
):
    mock_load_model.return_value = Mock()
    mock_predict.side_effect = ValueError("Prediction failed")

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=mock_prediction.id)

    assert result["status"] == "failed"
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED
    assert "Prediction failed" in mock_prediction.failure_reason
    mock_charge_prediction.assert_not_called()


def test_execute_prediction_returns_existing_completed_prediction(db_session, mock_prediction):
    mock_prediction.status = PredictionStatus.COMPLETED
    mock_prediction.result = {"prediction": [1.0]}
    db_session.commit()

    task = execute_prediction
    task._db = db_session

    result = task.run(prediction_id=mock_prediction.id)

    assert result["status"] == "completed"
    assert result["result"] == {"prediction": [1.0]}


def test_database_task_property(db_session):
    task = DatabaseTask()
    task._db = db_session
    assert task.db == db_session


def test_database_task_creates_db():
    task = DatabaseTask()
    db = task.db
    assert db is not None
    task.after_return()
    assert task._db is None
