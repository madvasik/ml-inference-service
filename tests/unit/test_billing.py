import pytest
from fastapi import status


def test_get_balance(client, test_user):
    """Тест получения баланса"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.get(
        "/api/v1/billing/balance",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "credits" in data
    assert data["credits"] >= 0


def test_topup_balance(client, test_user):
    """Тест пополнения баланса"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # Получаем текущий баланс
    balance_response = client.get(
        "/api/v1/billing/balance",
        headers={"Authorization": f"Bearer {token}"}
    )
    initial_balance = balance_response.json()["credits"]
    
    # Пополняем баланс
    response = client.post(
        "/api/v1/billing/topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 100}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["credits"] == initial_balance + 100


def test_topup_negative_amount(client, test_user):
    """Тест пополнения с отрицательной суммой"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.post(
        "/api/v1/billing/topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": -10}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_list_transactions(client, test_user):
    """Тест получения списка транзакций"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.get(
        "/api/v1/billing/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "transactions" in data
    assert "total" in data
