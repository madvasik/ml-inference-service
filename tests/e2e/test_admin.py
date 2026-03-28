"""E2e tests for admin endpoints: user listing, filtering, and access control."""
from __future__ import annotations

import os

import pytest
import requests

from tests.helpers import auth_headers, temporary_model_file, unique_email, wait_for_prediction


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@mlservice.com")
ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")


def _request(method: str, path: str, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)


def _admin_headers() -> dict[str, str]:
    login = _request("POST", "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert login.status_code == 200, login.text
    return auth_headers(login.json()["access_token"])


def _register_and_fund(prefix: str, amount: int = 100) -> dict[str, str]:
    email = unique_email(prefix)
    reg = _request("POST", "/api/v1/auth/register", json={"email": email, "password": "password123"})
    assert reg.status_code == 201, reg.text
    headers = auth_headers(reg.json()["access_token"])
    if amount > 0:
        pay = _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": amount})
        assert pay.status_code == 200, pay.text
    return headers


def _upload_model(headers: dict[str, str]) -> int:
    with temporary_model_file() as model_path:
        with open(model_path, "rb") as f:
            resp = _request(
                "POST",
                "/api/v1/models/upload",
                headers=headers,
                data={"model_name": "e2e-test-model"},
                files={"file": ("model.pkl", f, "application/octet-stream")},
            )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.e2e
def test_live_admin_can_observe_platform_data():
    user_headers = _register_and_fund("adminview", amount=15)
    admin_headers = _admin_headers()

    users = _request("GET", "/api/v1/admin/users", headers=admin_headers)
    assert users.status_code == 200

    payments = _request("GET", "/api/v1/admin/payments", headers=admin_headers)
    assert payments.status_code == 200

    transactions = _request("GET", "/api/v1/admin/transactions", headers=admin_headers)
    assert transactions.status_code == 200

    registered_email = _request("GET", "/api/v1/users/me", headers=user_headers).json()["email"]
    assert any(item["email"] == registered_email for item in users.json())
    assert any(item["amount"] == 15 for item in payments.json()["payments"])
    assert any(item["amount"] == 15 and item["type"] == "credit" for item in transactions.json()["transactions"])


@pytest.mark.e2e
def test_live_admin_can_filter_predictions_by_user():
    user_headers = _register_and_fund("adminfilt", amount=50)
    model_id = _upload_model(user_headers)

    create = _request(
        "POST",
        "/api/v1/predictions",
        headers=user_headers,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert create.status_code == 202
    prediction_id = create.json()["prediction_id"]

    def fetch(pid):
        return _request("GET", f"/api/v1/predictions/{pid}", headers=user_headers).json()

    wait_for_prediction(fetch, prediction_id)

    me = _request("GET", "/api/v1/users/me", headers=user_headers).json()
    user_id = me["id"]
    admin_h = _admin_headers()

    preds = _request("GET", f"/api/v1/admin/predictions?user_id={user_id}", headers=admin_h)
    assert preds.status_code == 200
    assert all(p["user_id"] == user_id for p in preds.json()["predictions"])
    assert preds.json()["total"] >= 1

    txns = _request("GET", f"/api/v1/admin/transactions?user_id={user_id}", headers=admin_h)
    assert txns.status_code == 200
    assert all(t["user_id"] == user_id for t in txns.json()["transactions"])

    user_detail = _request("GET", f"/api/v1/admin/users/{user_id}", headers=admin_h)
    assert user_detail.status_code == 200
    assert user_detail.json()["id"] == user_id

    pred_detail = _request("GET", f"/api/v1/admin/predictions/{prediction_id}", headers=admin_h)
    assert pred_detail.status_code == 200
    assert pred_detail.json()["id"] == prediction_id


@pytest.mark.e2e
def test_live_admin_get_nonexistent_user():
    admin_h = _admin_headers()
    resp = _request("GET", "/api/v1/admin/users/999999", headers=admin_h)
    assert resp.status_code == 404


@pytest.mark.e2e
def test_live_non_admin_cannot_access_admin_endpoints():
    headers = _register_and_fund("nonadmin", amount=0)
    resp = _request("GET", "/api/v1/admin/users", headers=headers)
    assert resp.status_code == 403
