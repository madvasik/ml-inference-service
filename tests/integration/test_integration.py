import pytest
from fastapi import status


def test_full_workflow(client, test_model_file):
    """Полный workflow: регистрация → загрузка модели → предсказание → проверка баланса"""
    # 1. Регистрация
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "workflow@example.com",
            "password": "password123"
        }
    )
    assert register_response.status_code == status.HTTP_201_CREATED
    token = register_response.json()["access_token"]
    
    # 2. Загрузка модели
    with open(test_model_file, 'rb') as f:
        model_response = client.post(
            "/api/v1/models/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("model.pkl", f, "application/octet-stream")},
            data={"model_name": "workflow_model"}
        )
    assert model_response.status_code == status.HTTP_201_CREATED
    model_id = model_response.json()["id"]
    
    # 3. Пополнение баланса
    payment_response = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 100}
    )
    assert payment_response.status_code == status.HTTP_200_OK
    
    # 4. Создание предсказания
    from unittest.mock import patch
    with patch('backend.app.api.routes.predictions.execute_prediction.delay') as mock_celery:
        mock_task = type('MockTask', (), {'id': 'test-task-id'})()
        mock_celery.return_value = mock_task
        
        prediction_response = client.post(
            "/api/v1/predictions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_id": model_id,
                "input_data": {"feature1": 1.0, "feature2": 2.0}
            }
        )
        assert prediction_response.status_code == status.HTTP_202_ACCEPTED
        prediction_data = prediction_response.json()
        assert prediction_data["status"] == "pending"
    
    # 5. Проверка баланса (пока не изменился, т.к. предсказание асинхронное)
    balance_response = client.get(
        "/api/v1/billing/balance",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert balance_response.status_code == status.HTTP_200_OK
    balance = balance_response.json()["credits"]
    assert balance == 100  # Баланс пока не изменился, т.к. предсказание асинхронное
    
    # 6. Проверка транзакций (должна быть транзакция пополнения)
    transactions_response = client.get(
        "/api/v1/billing/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert transactions_response.status_code == status.HTTP_200_OK
    transactions = transactions_response.json()["transactions"]
    assert len(transactions) >= 1  # Должна быть транзакция пополнения
