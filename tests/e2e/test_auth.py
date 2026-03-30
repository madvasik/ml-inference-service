"""E2e tests for authentication, tokens, and user profile."""
from __future__ import annotations

import os

import pytest
import requests

from tests.helpers import auth_headers, unique_email


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")


def _request(method: str, path: str, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)


def _register(prefix: str) -> tuple[str, dict[str, str], dict]:
    """Register a user and return (password, headers, token_payload)."""
    email = unique_email(prefix)
    password = "password123"
    reg = _request("POST", "/api/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201, reg.text
    payload = reg.json()
    return password, auth_headers(payload["access_token"]), payload


@pytest.mark.e2e
def test_live_auth_refresh_and_profile_flow():
    password, headers, _ = _register("authflow")

    profile = _request("GET", "/api/v1/users/me", headers=headers)
    assert profile.status_code == 200

    login = _request("POST", "/api/v1/auth/login", json={"email": profile.json()["email"], "password": password})
    assert login.status_code == 200

    refresh = _request("POST", "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]
    assert refresh.json()["refresh_token"]

    unauthorized = _request("GET", "/api/v1/users/me")
    assert unauthorized.status_code == 401


@pytest.mark.e2e
def test_live_register_duplicate_email():
    email = unique_email("dup")
    reg1 = _request("POST", "/api/v1/auth/register", json={"email": email, "password": "password123"})
    assert reg1.status_code == 201
    reg2 = _request("POST", "/api/v1/auth/register", json={"email": email, "password": "password123"})
    assert reg2.status_code == 400


@pytest.mark.e2e
def test_live_login_wrong_password():
    email = unique_email("wrongpw")
    _request("POST", "/api/v1/auth/register", json={"email": email, "password": "password123"})
    resp = _request("POST", "/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.e2e
def test_live_refresh_with_invalid_token():
    resp = _request("POST", "/api/v1/auth/refresh", json={"refresh_token": "invalid-token"})
    assert resp.status_code == 401


@pytest.mark.e2e
def test_live_protected_endpoints_require_auth():
    endpoints = [
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/models"),
        ("GET", "/api/v1/predictions"),
        ("GET", "/api/v1/billing/balance"),
        ("GET", "/api/v1/billing/payments"),
        ("GET", "/api/v1/billing/transactions"),
    ]
    for method, path in endpoints:
        resp = _request(method, path)
        assert resp.status_code in (401, 403), f"{method} {path} returned {resp.status_code}"


@pytest.mark.e2e
def test_live_user_profile_shows_loyalty_tier():
    _, headers, _ = _register("profile")
    me = _request("GET", "/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "user"
    assert body["loyalty_tier"] == "none"
    assert body["loyalty_discount_percent"] == 0
    assert "created_at" in body
