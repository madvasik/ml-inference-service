import pytest
from unittest.mock import patch, MagicMock
from fastapi import status


@patch('backend.app.api.v1.predictions.execute_prediction.delay')
def test_create_prediction(mock_celery_delay, client, test_user, test_ml_model):
    """Тест создания предсказания"""
    # Мокируем Celery задачу
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    mock_celery_delay.return_value = mock_task
    
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.post(
        "/api/v1/predictions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model_id": test_ml_model.id,
            "input_data": {"feature1": 1.0, "feature2": 2.0}
        }
    )
    assert response.status_code == status.HTTP_202_ACCEPTED  # Асинхронная задача возвращает 202
    data = response.json()
    assert data["status"] == "pending"
    assert "task_id" in data
    assert "prediction_id" in data
    mock_celery_delay.assert_called_once()


def test_create_prediction_insufficient_balance(client, test_user, test_ml_model, db_session):
    """Тест создания предсказания с недостаточным балансом"""
    from backend.app.models.balance import Balance
    # Устанавливаем нулевой баланс
    balance = db_session.query(Balance).filter_by(user_id=test_user.id).first()
    if balance:
        balance.credits = 0
        db_session.commit()
    
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.post(
        "/api/v1/predictions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model_id": test_ml_model.id,
            "input_data": {"feature1": 1.0, "feature2": 2.0}
        }
    )
    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED


def test_list_predictions(client, test_user):
    """Тест получения списка предсказаний"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.get(
        "/api/v1/predictions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "predictions" in data
    assert "total" in data
