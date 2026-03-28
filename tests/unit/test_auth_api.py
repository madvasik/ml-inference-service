from fastapi import status

from tests.helpers import auth_headers


def test_register_login_refresh_and_me_flow(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "password123"},
    )
    assert register.status_code == status.HTTP_201_CREATED
    tokens = register.json()
    assert tokens["token_type"] == "bearer"

    me = client.get("/api/v1/users/me", headers=auth_headers(tokens["access_token"]))
    assert me.status_code == status.HTTP_200_OK
    assert me.json()["email"] == "newuser@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": "password123"},
    )
    assert login.status_code == status.HTTP_200_OK

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refresh.status_code == status.HTTP_200_OK
    assert refresh.json()["access_token"]


def test_register_rejects_duplicate_email(client, test_user):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": test_user.email, "password": "password123"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_login_rejects_wrong_password(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "wrongpassword"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_rejects_access_token(client, access_token_for, test_user):
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token_for(test_user)},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_rejects_malformed_subject(client, monkeypatch):
    from backend.app.api import auth as auth_module

    monkeypatch.setattr(
        auth_module,
        "decode_token",
        lambda _token: {"type": "refresh", "sub": "not-an-int"},
    )

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "bad-token"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_users_me_requires_authentication(client):
    response = client.get("/api/v1/users/me")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_invalid_token_is_rejected(client):
    response = client.get("/api/v1/users/me", headers=auth_headers("not-a-real-token"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_rate_limit_headers_are_present(client):
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
