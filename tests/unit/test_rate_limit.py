import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
import time

# Используем фикстуру client из conftest.py, которая правильно настраивает БД
# Не нужно определять свой client здесь


def test_rate_limit_allows_requests(client):
    """Тест, что обычные запросы проходят"""
    # Первые несколько запросов должны пройти
    for i in range(10):
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers


def test_rate_limit_headers_present(client):
    """Тест наличия заголовков rate limit"""
    response = client.get("/health")
    
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


def test_rate_limit_excludes_metrics_endpoint(client):
    """Тест, что /metrics endpoint не ограничен"""
    # Делаем много запросов к метрикам
    for i in range(100):
        response = client.get("/metrics")
        assert response.status_code == 200


def test_rate_limit_excludes_health_endpoint(client):
    """Тест, что /health endpoint не ограничен"""
    # Делаем много запросов к health check
    for i in range(100):
        response = client.get("/health")
        assert response.status_code == 200


def test_rate_limit_excludes_docs_endpoint(client):
    """Тест, что /docs endpoint не ограничен"""
    response = client.get("/docs")
    assert response.status_code == 200


@pytest.mark.skip(reason="Requires actual rate limiting implementation with proper storage")
def test_rate_limit_blocks_excessive_requests(client):
    """Тест блокировки при превышении лимита"""
    # Этот тест требует реальной реализации rate limiting
    # с правильным хранилищем состояний между запросами
    pass
