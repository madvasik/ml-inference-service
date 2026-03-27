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


def test_topup_balance(client, test_user):
    """Тест пополнения баланса"""
    token = _login(client, test_user.email, "testpassword")
    
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
    token = _login(client, test_user.email, "testpassword")
    
    response = client.post(
        "/api/v1/billing/topup",
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


def test_create_payment_intent_and_confirm(client, test_user):
    token = _login(client, test_user.email, "testpassword")

    create_response = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 75},
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    create_data = create_response.json()
    assert create_data["status"] == "pending"
    assert create_data["amount"] == 75

    confirm_response = client.post(
        f"/api/v1/billing/payments/{create_data['payment_id']}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert confirm_response.status_code == status.HTTP_200_OK
    confirm_data = confirm_response.json()
    assert confirm_data["payment"]["status"] == "confirmed"
    assert confirm_data["credits"] >= 75


def test_confirm_payment_is_idempotent(client, test_user):
    token = _login(client, test_user.email, "testpassword")

    payment_id = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 20},
    ).json()["payment_id"]

    first_confirm = client.post(
        f"/api/v1/billing/payments/{payment_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    second_confirm = client.post(
        f"/api/v1/billing/payments/{payment_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first_confirm.status_code == status.HTTP_200_OK
    assert second_confirm.status_code == status.HTTP_200_OK
    assert first_confirm.json()["credits"] == second_confirm.json()["credits"]


def test_list_payments(client, test_user):
    token = _login(client, test_user.email, "testpassword")

    create_response = client.post(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 10},
    )
    payment_id = create_response.json()["payment_id"]
    client.post(
        f"/api/v1/billing/payments/{payment_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )

    list_response = client.get(
        "/api/v1/billing/payments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == status.HTTP_200_OK
    data = list_response.json()
    assert data["total"] >= 1
    assert data["payments"][0]["provider"] == "mock"
