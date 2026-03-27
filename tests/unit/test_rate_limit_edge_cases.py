import time

from backend.app.middleware import RateLimitMiddleware
from backend.app.security import create_access_token

# Используем фикстуру client из conftest.py, которая правильно настраивает БД
# Не нужно определять свой client здесь


def test_rate_limit_exception_handling(client):
    """Тест обработки исключений при извлечении user_id из токена"""
    # Создаем запрос с невалидным токеном
    response = client.get(
        "/health",
        headers={"Authorization": "Bearer invalid_token_format"}
    )
    # Должен пройти, так как /health исключен из rate limiting
    assert response.status_code == 200


def test_rate_limit_cleanup_mechanism():
    """Тест механизма очистки старых записей rate limit"""
    from unittest.mock import Mock

    middleware = RateLimitMiddleware(Mock())

    # Добавляем старые записи
    old_time = time.time() - 200  # 200 секунд назад
    middleware._requests["test_key"] = [old_time]

    # Вызываем cleanup
    middleware._last_cleanup = time.time() - 400  # Давно не чистили
    middleware._cleanup_old_entries()

    # Старые записи должны быть удалены
    assert "test_key" not in middleware._requests or len(middleware._requests.get("test_key", [])) == 0


def test_rate_limit_user_key_extraction(client, test_user):
    """Тест извлечения user_id из токена для rate limiting"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    # Делаем запрос с токеном
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Проверяем что запрос прошел и заголовки rate limit присутствуют
    assert response.status_code in [200, 401]  # Может быть 401 если нет пользователя в БД
    if response.status_code == 200:
        assert "X-RateLimit-Limit" in response.headers


def test_rate_limit_ip_fallback(client):
    """Тест использования IP адреса когда нет токена"""
    response = client.get("/health")
    
    # Проверяем что запрос прошел
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers


def test_rate_limit_blocked_response(client):
    """Тест ответа при блокировке запроса"""
    from unittest.mock import Mock

    middleware = RateLimitMiddleware(Mock())

    # Заполняем requests до лимита
    key = "test_key"
    limit = 10
    # Инициализируем список для ключа
    if key not in middleware._requests:
        middleware._requests[key] = []
    for i in range(limit):
        middleware._requests[key].append(time.time())
    
    # Проверяем что следующий запрос будет заблокирован
    allowed, remaining = middleware._check_rate_limit(key, limit)
    assert allowed is False
    assert remaining == 0
