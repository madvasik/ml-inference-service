import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from backend.app.tasks.prediction_tasks import execute_prediction
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.models.ml_model import MLModel
from backend.app.models.user import User


@pytest.fixture
def mock_db():
    """Мок для сессии БД"""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_prediction():
    """Мок для предсказания"""
    prediction = Mock(spec=Prediction)
    prediction.id = 1
    prediction.status = PredictionStatus.PENDING
    prediction.result = None
    prediction.credits_spent = 0
    return prediction


@pytest.fixture
def mock_model():
    """Мок для модели"""
    model = Mock(spec=MLModel)
    model.id = 1
    model.file_path = "/test/model.pkl"
    return model


@patch('backend.app.tasks.prediction_tasks.load_model')
@patch('backend.app.tasks.prediction_tasks.predict')
@patch('backend.app.tasks.prediction_tasks.deduct_credits')
def test_execute_prediction_success(
    mock_deduct_credits,
    mock_predict,
    mock_load_model,
    mock_db,
    mock_prediction,
    mock_model
):
    """Тест успешного выполнения предсказания"""
    # Настройка моков
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_prediction,  # Для prediction
        mock_model  # Для model
    ]
    
    mock_ml_model = Mock()
    mock_load_model.return_value = mock_ml_model
    mock_predict.return_value = {"prediction": [0.85]}
    mock_deduct_credits.return_value = True
    
    # Создаем задачу
    task = execute_prediction
    task.db = mock_db
    
    # Выполняем задачу
    result = task.run(
        prediction_id=1,
        model_id=1,
        user_id=1,
        input_data={"feature1": 1.5}
    )
    
    # Проверки
    assert result["status"] == "completed"
    assert result["prediction_id"] == 1
    assert "result" in result
    mock_deduct_credits.assert_called_once()
    mock_db.commit.assert_called()


@patch('backend.app.tasks.prediction_tasks.load_model')
def test_execute_prediction_model_not_found(
    mock_load_model,
    mock_db,
    mock_prediction
):
    """Тест обработки случая, когда модель не найдена"""
    # Настройка моков
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_prediction,  # Для prediction
        None  # Для model - не найдена
    ]
    
    # Создаем задачу
    task = execute_prediction
    task.db = mock_db
    
    # Выполняем задачу
    result = task.run(
        prediction_id=1,
        model_id=999,
        user_id=1,
        input_data={"feature1": 1.5}
    )
    
    # Проверки
    assert result["status"] == "failed"
    assert "error" in result
    assert mock_prediction.status == PredictionStatus.FAILED
    mock_db.commit.assert_called()


@patch('backend.app.tasks.prediction_tasks.load_model')
@patch('backend.app.tasks.prediction_tasks.predict')
@patch('backend.app.tasks.prediction_tasks.deduct_credits')
def test_execute_prediction_insufficient_credits(
    mock_deduct_credits,
    mock_predict,
    mock_load_model,
    mock_db,
    mock_prediction,
    mock_model
):
    """Тест обработки недостаточного баланса"""
    # Настройка моков
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_prediction,
        mock_model
    ]
    
    mock_ml_model = Mock()
    mock_load_model.return_value = mock_ml_model
    mock_predict.return_value = {"prediction": [0.85]}
    mock_deduct_credits.return_value = False  # Недостаточно кредитов
    
    # Создаем задачу
    task = execute_prediction
    task.db = mock_db
    
    # Выполняем задачу
    result = task.run(
        prediction_id=1,
        model_id=1,
        user_id=1,
        input_data={"feature1": 1.5}
    )
    
    # Проверки
    assert result["status"] == "failed"
    assert "error" in result
    assert mock_prediction.status == PredictionStatus.FAILED
    mock_db.commit.assert_called()
