import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.app.tasks.prediction_tasks import execute_prediction, DatabaseTask
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.models.ml_model import MLModel
from backend.app.models.user import User
from backend.app.models.balance import Balance


@pytest.fixture
def mock_prediction(db_session, test_user, test_ml_model):
    """Создание тестового предсказания"""
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature1": 1.0, "feature2": 2.0},
        status=PredictionStatus.PENDING,
        credits_spent=0
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)
    return prediction


@pytest.fixture
def mock_balance(db_session, test_user):
    """Создание баланса для теста"""
    balance = Balance(user_id=test_user.id, credits=1000)
    db_session.add(balance)
    db_session.commit()
    return balance


@patch('backend.app.tasks.prediction_tasks.load_model')
@patch('backend.app.tasks.prediction_tasks.predict')
@patch('backend.app.tasks.prediction_tasks.deduct_credits')
def test_execute_prediction_success_integration(
    mock_deduct_credits,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
    test_ml_model,
    test_user
):
    """Интеграционный тест успешного выполнения предсказания"""
    mock_ml_model = Mock()
    mock_load_model.return_value = mock_ml_model
    mock_predict.return_value = {"prediction": [0.85], "probabilities": [0.15, 0.85]}
    mock_deduct_credits.return_value = True
    
    # Используем реальную БД сессию
    task = execute_prediction
    task._db = db_session
    
    result = task.run(
        prediction_id=mock_prediction.id,
        model_id=test_ml_model.id,
        user_id=test_user.id,
        input_data={"feature1": 1.0, "feature2": 2.0}
    )
    
    assert result["status"] == "completed"
    assert result["prediction_id"] == mock_prediction.id
    assert "result" in result
    
    # Проверяем, что предсказание обновлено в БД
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.COMPLETED
    assert mock_prediction.result is not None


@patch('backend.app.tasks.prediction_tasks.load_model')
def test_execute_prediction_not_found(mock_load_model, db_session, test_ml_model, test_user):
    """Тест обработки случая, когда предсказание не найдено"""
    task = execute_prediction
    task._db = db_session
    
    result = task.run(
        prediction_id=99999,
        model_id=test_ml_model.id,
        user_id=test_user.id,
        input_data={"feature1": 1.0}
    )
    
    assert result["status"] == "failed"
    assert "error" in result
    assert "not found" in result["error"].lower()
    # load_model не должен вызываться если предсказание не найдено
    mock_load_model.assert_not_called()


@patch('backend.app.tasks.prediction_tasks.load_model')
def test_execute_prediction_model_not_found_integration(
    mock_load_model,
    db_session,
    mock_prediction,
    test_user
):
    """Интеграционный тест обработки случая, когда модель не найдена"""
    task = execute_prediction
    task._db = db_session
    
    result = task.run(
        prediction_id=mock_prediction.id,
        model_id=99999,
        user_id=test_user.id,
        input_data={"feature1": 1.0}
    )
    
    assert result["status"] == "failed"
    assert "error" in result
    
    # Проверяем, что предсказание помечено как FAILED
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED


@patch('backend.app.tasks.prediction_tasks.load_model')
@patch('backend.app.tasks.prediction_tasks.predict')
@patch('backend.app.tasks.prediction_tasks.deduct_credits')
def test_execute_prediction_insufficient_credits_integration(
    mock_deduct_credits,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
    test_ml_model,
    test_user
):
    """Интеграционный тест обработки недостаточного баланса"""
    mock_ml_model = Mock()
    mock_load_model.return_value = mock_ml_model
    mock_predict.return_value = {"prediction": [0.85]}
    mock_deduct_credits.return_value = False  # Недостаточно кредитов
    
    task = execute_prediction
    task._db = db_session
    
    result = task.run(
        prediction_id=mock_prediction.id,
        model_id=test_ml_model.id,
        user_id=test_user.id,
        input_data={"feature1": 1.0}
    )
    
    assert result["status"] == "failed"
    assert "error" in result
    
    # Проверяем, что предсказание помечено как FAILED
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED


@patch('backend.app.tasks.prediction_tasks.load_model')
@patch('backend.app.tasks.prediction_tasks.predict')
@patch('backend.app.tasks.prediction_tasks.deduct_credits')
def test_execute_prediction_load_model_error(
    mock_deduct_credits,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
    test_ml_model,
    test_user
):
    """Тест обработки ошибки загрузки модели"""
    mock_load_model.side_effect = ValueError("Failed to load model")
    
    task = execute_prediction
    task._db = db_session
    task.max_retries = 0  # Отключаем retry для теста
    
    result = task.run(
        prediction_id=mock_prediction.id,
        model_id=test_ml_model.id,
        user_id=test_user.id,
        input_data={"feature1": 1.0}
    )
    
    assert result["status"] == "failed"
    assert "error" in result
    
    # Проверяем, что предсказание помечено как FAILED
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED
    # deduct_credits не должен вызываться при ошибке загрузки модели
    mock_deduct_credits.assert_not_called()


@patch('backend.app.tasks.prediction_tasks.load_model')
@patch('backend.app.tasks.prediction_tasks.predict')
@patch('backend.app.tasks.prediction_tasks.deduct_credits')
def test_execute_prediction_predict_error(
    mock_deduct_credits,
    mock_predict,
    mock_load_model,
    db_session,
    mock_prediction,
    test_ml_model,
    test_user
):
    """Тест обработки ошибки предсказания"""
    mock_ml_model = Mock()
    mock_load_model.return_value = mock_ml_model
    mock_predict.side_effect = ValueError("Prediction failed")
    
    task = execute_prediction
    task._db = db_session
    
    result = task.run(
        prediction_id=mock_prediction.id,
        model_id=test_ml_model.id,
        user_id=test_user.id,
        input_data={"feature1": 1.0}
    )
    
    assert result["status"] == "failed"
    assert "error" in result
    
    # Проверяем, что предсказание помечено как FAILED
    db_session.refresh(mock_prediction)
    assert mock_prediction.status == PredictionStatus.FAILED


def test_database_task_property(db_session):
    """Тест свойства db в DatabaseTask"""
    task = DatabaseTask()
    task._db = db_session
    
    assert task.db == db_session


def test_database_task_creates_db():
    """Тест автоматического создания БД сессии"""
    task = DatabaseTask()
    
    # При первом обращении должна создаться сессия
    db = task.db
    assert db is not None
    
    # Очистка
    task.after_return()
    assert task._db is None
