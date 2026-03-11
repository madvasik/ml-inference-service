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
    topup_response = client.post(
        "/api/v1/billing/topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 100}
    )
    assert topup_response.status_code == status.HTTP_200_OK
    
    # 4. Создание предсказания
    prediction_response = client.post(
        "/api/v1/predictions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model_id": model_id,
            "input_data": {"feature1": 1.0, "feature2": 2.0}
        }
    )
    assert prediction_response.status_code == status.HTTP_201_CREATED
    prediction_data = prediction_response.json()
    assert prediction_data["status"] == "completed"
    
    # 5. Проверка баланса (должен уменьшиться)
    balance_response = client.get(
        "/api/v1/billing/balance",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert balance_response.status_code == status.HTTP_200_OK
    balance = balance_response.json()["credits"]
    assert balance < 100  # Должен быть списан хотя бы 1 кредит
    
    # 6. Проверка транзакций
    transactions_response = client.get(
        "/api/v1/billing/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert transactions_response.status_code == status.HTTP_200_OK
    transactions = transactions_response.json()["transactions"]
    assert len(transactions) >= 2  # Должна быть транзакция пополнения и списания
