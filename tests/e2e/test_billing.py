"""E2e tests for billing: payments, balance, and transactions."""
from __future__ import annotations

import os

import pytest
import requests

from tests.helpers import auth_headers, unique_email


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")


def _request(method: str, path: str, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)


def _register_and_fund(prefix: str, amount: int = 100) -> dict[str, str]:
    """Register a user, optionally fund, return headers."""
    email = unique_email(prefix)
    reg = _request("POST", "/api/v1/auth/register", json={"email": email, "password": "password123"})
    assert reg.status_code == 201, reg.text
    headers = auth_headers(reg.json()["access_token"])
    if amount > 0:
        pay = _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": amount})
        assert pay.status_code == 200, pay.text
    return headers


@pytest.mark.e2e
def test_live_billing_history_and_transactions():
    headers = _register_and_fund("billingflow", amount=25)

    balance = _request("GET", "/api/v1/billing/balance", headers=headers)
    assert balance.status_code == 200
    assert balance.json()["credits"] == 25

    payments = _request("GET", "/api/v1/billing/payments", headers=headers)
    assert payments.status_code == 200
    assert payments.json()["total"] >= 1

    transactions = _request("GET", "/api/v1/billing/transactions", headers=headers)
    assert transactions.status_code == 200
    assert any(item["type"] == "credit" for item in transactions.json()["transactions"])


@pytest.mark.e2e
def test_live_billing_rejects_non_positive_amount():
    headers = _register_and_fund("negpay", amount=0)

    zero = _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": 0})
    assert zero.status_code == 400

    negative = _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": -10})
    assert negative.status_code == 400


@pytest.mark.e2e
def test_live_billing_multiple_payments_accumulate():
    headers = _register_and_fund("multipay", amount=0)

    _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": 30})
    _request("POST", "/api/v1/billing/payments", headers=headers, json={"amount": 20})

    balance = _request("GET", "/api/v1/billing/balance", headers=headers)
    assert balance.status_code == 200
    assert balance.json()["credits"] == 50

    payments = _request("GET", "/api/v1/billing/payments", headers=headers)
    assert payments.json()["total"] == 2
