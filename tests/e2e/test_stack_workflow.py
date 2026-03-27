from __future__ import annotations

import os

import requests
import pytest

from tests.helpers import auth_headers, temporary_model_file, unique_email, wait_for_prediction


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@mlservice.com")
ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")


def _request(method: str, path: str, **kwargs):
    response = requests.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)
    return response


@pytest.mark.e2e
def test_live_stack_prediction_workflow():
    register = _request(
        "POST",
        "/api/v1/auth/register",
        json={"email": unique_email("e2e"), "password": "password123"},
    )
    assert register.status_code == 201, register.text
    token = register.json()["access_token"]
    headers = auth_headers(token)

    payment = _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": 50})
    assert payment.status_code == 200, payment.text

    with temporary_model_file() as model_path:
        with open(model_path, "rb") as file:
            upload = _request(
                "POST",
                "/api/v1/models/upload",
                headers=headers,
                data={"model_name": "e2e-model"},
                files={"file": ("model.pkl", file, "application/octet-stream")},
            )
    assert upload.status_code == 201, upload.text
    model_id = upload.json()["id"]

    create_prediction = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert create_prediction.status_code == 202, create_prediction.text
    prediction_id = create_prediction.json()["prediction_id"]

    def fetch_prediction(prediction_id: int) -> dict:
        response = _request("GET", f"/api/v1/predictions/{prediction_id}", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    prediction = wait_for_prediction(fetch_prediction, prediction_id)
    assert prediction["status"] == "completed"
    assert prediction["result"] is not None

    balance = _request("GET", "/api/v1/billing/balance", headers=headers)
    assert balance.status_code == 200, balance.text
    assert balance.json()["credits"] == 50 - prediction["credits_spent"]

    transactions = _request("GET", "/api/v1/billing/transactions", headers=headers)
    assert transactions.status_code == 200, transactions.text
    transaction_types = [item["type"] for item in transactions.json()["transactions"]]
    assert "credit" in transaction_types
    assert "debit" in transaction_types

    admin_login = _request(
        "POST",
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = auth_headers(admin_login.json()["access_token"])
    admin_predictions = _request("GET", f"/api/v1/admin/predictions?user_id={prediction['user_id']}", headers=admin_headers)
    assert admin_predictions.status_code == 200, admin_predictions.text
    assert any(item["id"] == prediction_id for item in admin_predictions.json()["predictions"])
