import pytest
from datetime import timedelta

from backend.app.config import settings
from backend.app.security import create_access_token, create_refresh_token, decode_token


def test_create_access_token_with_custom_expires_delta():
    """Тест создания access token с кастомным expires_delta"""
    custom_delta = timedelta(hours=2)
    token = create_access_token({"sub": "123"}, expires_delta=custom_delta)
    
    assert token is not None
    assert len(token) > 0
    
    # Декодируем и проверяем
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "123"
    assert payload["type"] == "access"


def test_create_access_token_with_default_expires():
    """Тест создания access token с дефолтным expires"""
    token = create_access_token({"sub": "123"})
    
    assert token is not None
    payload = decode_token(token)
    assert payload is not None
    assert "exp" in payload


def test_create_refresh_token():
    """Тест создания refresh token"""
    token = create_refresh_token({"sub": "123"})
    
    assert token is not None
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "123"
    assert payload["type"] == "refresh"


def test_decode_token_invalid_token():
    """Тест декодирования невалидного токена"""
    result = decode_token("invalid.token.here")
    assert result is None


def test_decode_token_wrong_secret():
    """Тест декодирования токена с неправильным секретом"""
    # Создаем токен с правильным секретом
    token = create_access_token({"sub": "123"})
    
    # Меняем секрет в настройках временно
    original_secret = settings.secret_key
    settings.secret_key = "wrong_secret"
    
    try:
        result = decode_token(token)
        # Должен вернуть None из-за неправильного секрета
        assert result is None
    finally:
        settings.secret_key = original_secret


def test_decode_token_expired_token():
    """Тест декодирования истекшего токена"""
    # Создаем токен с отрицательным expires_delta (уже истек)
    expired_delta = timedelta(seconds=-1)
    token = create_access_token({"sub": "123"}, expires_delta=expired_delta)
    
    # Декодирование истекшего токена должно вернуть None
    result = decode_token(token)
    assert result is None


def test_decode_token_empty_string():
    """Тест декодирования пустой строки"""
    result = decode_token("")
    assert result is None


def test_decode_token_malformed():
    """Тест декодирования неправильно сформированного токена"""
    result = decode_token("not.a.valid.jwt.token")
    assert result is None


def test_token_payload_structure():
    """Тест структуры payload токена"""
    token = create_access_token({"sub": "123", "custom": "value"})
    payload = decode_token(token)
    
    assert payload is not None
    assert payload["sub"] == "123"
    assert payload["custom"] == "value"
    assert payload["type"] == "access"
    assert "exp" in payload
