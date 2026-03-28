from __future__ import annotations

import os

import pytest
import requests

from tests.helpers import auth_headers, temporary_model_file, unique_email


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@mlservice.com")
ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")


def _request(method: str, path: str, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)


def _register_user(prefix: str) -> tuple[str, dict[str, str], dict]:
    email = unique_email(prefix)
    password = "password123"
    register = _request(
        "POST",
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register.status_code == 201, register.text
    token_payload = register.json()
    return password, auth_headers(token_payload["access_token"]), token_payload


@pytest.mark.e2e
def test_live_auth_refresh_and_profile_flow():
    password, headers, token_payload = _register_user("authflow")

    profile = _request("GET", "/api/v1/users/me", headers=headers)
    assert profile.status_code == 200, profile.text

    login = _request(
        "POST",
        "/api/v1/auth/login",
        json={"email": profile.json()["email"], "password": password},
    )
    assert login.status_code == 200, login.text

    refresh = _request(
        "POST",
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["access_token"] != token_payload["access_token"]

    unauthorized_profile = _request("GET", "/api/v1/users/me")
    assert unauthorized_profile.status_code == 403


@pytest.mark.e2e
def test_live_billing_history_and_admin_access_control():
    _password, headers, _token_payload = _register_user("billingflow")

    payment = _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": 25})
    assert payment.status_code == 200, payment.text
    assert payment.json()["credits"] == 25

    balance = _request("GET", "/api/v1/billing/balance", headers=headers)
    assert balance.status_code == 200, balance.text
    assert balance.json()["credits"] == 25

    payments = _request("GET", "/api/v1/billing/payments", headers=headers)
    assert payments.status_code == 200, payments.text
    assert payments.json()["total"] >= 1

    transactions = _request("GET", "/api/v1/billing/transactions", headers=headers)
    assert transactions.status_code == 200, transactions.text
    assert any(item["type"] == "credit" for item in transactions.json()["transactions"])

    non_admin = _request("GET", "/api/v1/admin/users", headers=headers)
    assert non_admin.status_code == 403, non_admin.text


@pytest.mark.e2e
def test_live_prediction_rejects_foreign_model_and_insufficient_balance():
    _password_a, headers_a, _tokens_a = _register_user("ownera")
    _password_b, headers_b, _tokens_b = _register_user("ownerb")

    with temporary_model_file() as model_path:
        with open(model_path, "rb") as file:
            upload = _request(
                "POST",
                "/api/v1/models/upload",
                headers=headers_b,
                data={"model_name": "foreign-model"},
                files={"file": ("model.pkl", file, "application/octet-stream")},
            )
    assert upload.status_code == 201, upload.text
    model_id = upload.json()["id"]

    foreign_model_prediction = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers_a,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert foreign_model_prediction.status_code == 404, foreign_model_prediction.text

    own_models = _request("GET", "/api/v1/models", headers=headers_a)
    assert own_models.status_code == 200, own_models.text
    assert own_models.json()["total"] == 0

    with temporary_model_file() as model_path:
        with open(model_path, "rb") as file:
            own_upload = _request(
                "POST",
                "/api/v1/models/upload",
                headers=headers_a,
                data={"model_name": "owner-a-model"},
                files={"file": ("model.pkl", file, "application/octet-stream")},
            )
    assert own_upload.status_code == 201, own_upload.text

    insufficient_balance_prediction = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers_a,
        json={"model_id": own_upload.json()["id"], "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert insufficient_balance_prediction.status_code == 402, insufficient_balance_prediction.text


@pytest.mark.e2e
def test_live_model_upload_validation():
    _password, headers, _tokens = _register_user("badmodel")

    invalid_upload = _request(
        "POST",
        "/api/v1/models/upload",
        headers=headers,
        data={"model_name": "bad-model"},
        files={"file": ("model.txt", b"not-a-model", "text/plain")},
    )
    assert invalid_upload.status_code == 400, invalid_upload.text


@pytest.mark.e2e
def test_live_admin_can_observe_platform_data():
    _user_password, user_headers, _tokens = _register_user("adminview")

    payment = _request("POST", "/api/v1/billing/payments", headers=user_headers, json={"amount": 15})
    assert payment.status_code == 200, payment.text

    admin_login = _request(
        "POST",
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = auth_headers(admin_login.json()["access_token"])

    users = _request("GET", "/api/v1/admin/users", headers=admin_headers)
    assert users.status_code == 200, users.text

    payments = _request("GET", "/api/v1/admin/payments", headers=admin_headers)
    assert payments.status_code == 200, payments.text

    transactions = _request("GET", "/api/v1/admin/transactions", headers=admin_headers)
    assert transactions.status_code == 200, transactions.text

    registered_email = _request("GET", "/api/v1/users/me", headers=user_headers).json()["email"]
    assert any(item["email"] == registered_email for item in users.json())
    assert any(item["amount"] == 15 for item in payments.json()["payments"])
    assert any(item["amount"] == 15 and item["type"] == "credit" for item in transactions.json()["transactions"])
