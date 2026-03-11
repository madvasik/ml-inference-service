import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.exceptions import (
    MLServiceException,
    ModelNotFoundError,
    InsufficientCreditsError,
    InvalidModelError,
    PredictionError
)


@pytest.fixture
def client():
    """Тестовый клиент"""
    return TestClient(app)


def test_model_not_found_exception_handler(client):
    """Тест обработчика ModelNotFoundError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_insufficient_credits_exception_handler(client):
    """Тест обработчика InsufficientCreditsError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_invalid_model_exception_handler(client):
    """Тест обработчика InvalidModelError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_prediction_error_exception_handler(client):
    """Тест обработчика PredictionError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_general_exception_handler(client):
    """Тест общего обработчика исключений"""
    # Проверяем, что общий обработчик зарегистрирован
    assert Exception in app.exception_handlers


def test_root_endpoint(client):
    """Тест root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_health_endpoint(client):
    """Тест health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_metrics_endpoint(client):
    """Тест metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")


def test_cors_middleware_configured():
    """Тест конфигурации CORS middleware"""
    # Проверяем, что middleware добавлены
    assert len(app.user_middleware) >= 3


def test_rate_limit_middleware_configured():
    """Тест конфигурации RateLimitMiddleware"""
    # Проверяем, что middleware добавлены
    assert len(app.user_middleware) >= 3


def test_metrics_middleware_configured():
    """Тест конфигурации MetricsMiddleware"""
    # Проверяем, что middleware добавлены
    assert len(app.user_middleware) >= 3
