from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.middleware import RateLimitMiddleware

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


def test_rate_limit_blocks_excessive_requests(monkeypatch):
    """Тест блокировки при превышении лимита"""
    limited_app = FastAPI()
    limited_app.add_middleware(RateLimitMiddleware)

    @limited_app.get("/limited")
    def limited():
        return {"ok": True}

    original_limit = settings.rate_limit_per_minute
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)

    try:
        with TestClient(limited_app) as local_client:
            assert local_client.get("/limited").status_code == 200
            assert local_client.get("/limited").status_code == 200

            blocked_response = local_client.get("/limited")
            assert blocked_response.status_code == 429
            assert blocked_response.json()["detail"] == "Rate limit exceeded. Please try again later."
    finally:
        monkeypatch.setattr(settings, "rate_limit_per_minute", original_limit)
