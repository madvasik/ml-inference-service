import pytest
from fastapi import status


def _login(client, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return response.json()["access_token"]


def test_get_balance(client, test_user):
    """Тест получения баланса"""
    token = _login(client, test_user.email, "testpassword")
    
    response = client.get(
        "/api/v1/billing/balance",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "credits" in data
    assert data["credits"] >= 0


def test_create_payment_adds_credits(client, test_user):
    """Тест пополнения баланса"""
    token = _login(client, test_user.email, "testpassword")

    balance_response = client.get(
        "/api/v1/billing/balance",
        headers={"Authorization": f"Bearer {token}"}
    )
    initial_balance = balance_response.json()["credits"]

    response = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 100}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["payment"]["status"] == "confirmed"
    assert data["payment"]["amount"] == 100
    assert data["credits"] == initial_balance + 100


def test_create_payment_negative_amount(client, test_user):
    """Тест пополнения с отрицательной суммой"""
    token = _login(client, test_user.email, "testpassword")

    response = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": -10}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_list_transactions(client, test_user):
    """Тест получения списка транзакций"""
    token = _login(client, test_user.email, "testpassword")
    
    response = client.get(
        "/api/v1/billing/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "transactions" in data
    assert "total" in data


def test_create_payment_returns_confirmed_payment(client, test_user):
    token = _login(client, test_user.email, "testpassword")

    response = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 75},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["payment"]["status"] == "confirmed"
    assert data["payment"]["amount"] == 75
    assert data["credits"] >= 75


def test_list_payments(client, test_user):
    token = _login(client, test_user.email, "testpassword")

    response = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 10},
    )
    assert response.status_code == status.HTTP_200_OK

    list_response = client.get(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == status.HTTP_200_OK
    data = list_response.json()
    assert data["total"] >= 1
    assert data["payments"][0]["provider"] == "mock"
