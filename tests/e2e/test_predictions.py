"""E2e tests for prediction creation, execution, scoping, and edge cases."""
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
def test_live_full_prediction_workflow():
    """Register → fund → upload → predict → wait → verify balance and transactions."""
    headers = _register_and_fund("e2e", amount=50)
    model_id = _upload_model(headers)

    create = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert create.status_code == 202
    prediction_id = create.json()["prediction_id"]

    def fetch(pid):
        r = _request("GET", f"/api/v1/predictions/{pid}", headers=headers)
        assert r.status_code == 200
        return r.json()

    prediction = wait_for_prediction(fetch, prediction_id)
    assert prediction["status"] == "completed"
    assert prediction["result"] is not None

    balance = _request("GET", "/api/v1/billing/balance", headers=headers)
    assert balance.status_code == 200
    assert balance.json()["credits"] == 50 - prediction["credits_spent"]

    transactions = _request("GET", "/api/v1/billing/transactions", headers=headers)
    types = [t["type"] for t in transactions.json()["transactions"]]
    assert "credit" in types
    assert "debit" in types


@pytest.mark.e2e
def test_live_prediction_fails_with_zero_balance():
    headers = _register_and_fund("zerobalpred", amount=0)
    model_id = _upload_model(headers)

    resp = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert resp.status_code == 402


@pytest.mark.e2e
def test_live_prediction_for_nonexistent_model():
    headers = _register_and_fund("nomodel", amount=50)

    resp = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers,
        json={"model_id": 999999, "input_data": {"feature1": 1}},
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_live_prediction_rejects_foreign_model():
    headers_a = _register_and_fund("ownera", amount=0)
    headers_b = _register_and_fund("ownerb", amount=0)

    model_id = _upload_model(headers_b)

    resp = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers_a,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert resp.status_code == 404

    own_models = _request("GET", "/api/v1/models", headers=headers_a)
    assert own_models.json()["total"] == 0


@pytest.mark.e2e
def test_live_prediction_insufficient_balance():
    headers = _register_and_fund("insuffbal", amount=0)

    with temporary_model_file() as model_path:
        with open(model_path, "rb") as f:
            upload = _request(
                "POST",
                "/api/v1/models/upload",
                headers=headers,
                data={"model_name": "own-model"},
                files={"file": ("model.pkl", f, "application/octet-stream")},
            )
    assert upload.status_code == 201

    resp = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers,
        json={"model_id": upload.json()["id"], "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert resp.status_code == 402


@pytest.mark.e2e
def test_live_prediction_list_is_scoped_to_user():
    headers_a = _register_and_fund("scopea", amount=50)
    headers_b = _register_and_fund("scopeb", amount=50)
    model_id = _upload_model(headers_a)

    create = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers_a,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert create.status_code == 202
    prediction_id = create.json()["prediction_id"]

    preds_b = _request("GET", "/api/v1/predictions", headers=headers_b)
    assert preds_b.status_code == 200
    assert all(p["id"] != prediction_id for p in preds_b.json()["predictions"])

    detail_b = _request("GET", f"/api/v1/predictions/{prediction_id}", headers=headers_b)
    assert detail_b.status_code == 404


@pytest.mark.e2e
def test_live_multiple_predictions_debit_correctly():
    headers = _register_and_fund("multipred", amount=100)
    model_id = _upload_model(headers)

    prediction_ids = []
    for _ in range(3):
        resp = _request(
            "POST",
            "/api/v1/predictions",
            headers=headers,
            json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
        )
        assert resp.status_code == 202, resp.text
        prediction_ids.append(resp.json()["prediction_id"])

    def fetch(pid):
        return _request("GET", f"/api/v1/predictions/{pid}", headers=headers).json()

    for pid in prediction_ids:
        result = wait_for_prediction(fetch, pid)
        assert result["status"] == "completed", f"Prediction {pid}: {result}"

    balance = _request("GET", "/api/v1/billing/balance", headers=headers)
    assert balance.status_code == 200
    assert balance.json()["credits"] == 100 - 30

    transactions = _request("GET", "/api/v1/billing/transactions", headers=headers)
    debits = [t for t in transactions.json()["transactions"] if t["type"] == "debit"]
    assert len(debits) == 3


@pytest.mark.e2e
def test_live_prediction_after_model_delete_fails():
    headers = _register_and_fund("delpred", amount=50)
    model_id = _upload_model(headers)

    _request("DELETE", f"/api/v1/models/{model_id}", headers=headers)

    resp = _request(
        "POST",
        "/api/v1/predictions",
        headers=headers,
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
    )
    assert resp.status_code == 404
