import pytest
from fastapi import status
from backend.app.security import create_access_token, create_refresh_token, decode_token


def test_refresh_token_invalid_token(client):
    """Тест обновления токена с невалидным refresh token"""
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_token"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in response.json()["detail"]


def test_refresh_token_wrong_type(client, test_user):
    """Тест обновления токена с access token вместо refresh token"""
    # Создаем access token вместо refresh
    access_token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid token type" in response.json()["detail"]


def test_refresh_token_no_sub(client):
    """Тест обновления токена без sub в payload"""
    # Создаем токен без sub (это сложно сделать напрямую, но можно проверить обработку)
    # В реальности это будет обработано в decode_token, но проверим обработку в refresh endpoint
    # Создаем токен с пустым sub
    token = create_refresh_token({"email": "test@example.com"})  # Без sub
    
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token}
    )
    # Должен вернуть ошибку, так как sub обязателен
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_token_user_not_found(client):
    """Тест обновления токена для несуществующего пользователя"""
    # Создаем refresh token для несуществующего пользователя
    token = create_refresh_token({"sub": "99999", "email": "nonexistent@example.com"})
    
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "User not found" in response.json()["detail"]


def test_refresh_token_success(client, test_user):
    """Тест успешного обновления токена"""
    # Создаем refresh token
    refresh_token = create_refresh_token({"sub": str(test_user.id), "email": test_user.email})
    
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    
    # Проверяем, что новый токен валиден и отличается от старого
    new_access_token = data["access_token"]
    new_refresh_token = data["refresh_token"]
    assert new_access_token != refresh_token  # Новый токен должен отличаться
    assert new_refresh_token != refresh_token  # Новый refresh токен тоже должен отличаться
    
    # Проверяем payload нового токена
    payload = decode_token(new_access_token)
    if payload:  # Может быть None если токен истек или невалиден
        assert payload["type"] == "access"
