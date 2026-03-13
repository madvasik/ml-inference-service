import pytest
from fastapi import status


def test_get_current_user(client, test_user):
    """Тест получения информации о текущем пользователе"""
    # Логинимся
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # Получаем информацию о пользователе
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == test_user.email
    assert data["id"] == test_user.id


def test_get_current_user_unauthorized(client):
    """Тест получения информации без авторизации"""
    response = client.get("/api/v1/users/me")
    # HTTPBearer возвращает 401 когда нет токена, а не 403
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
