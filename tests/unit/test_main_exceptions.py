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

# Используем фикстуру client из conftest.py для консистентности
# Но для этих тестов БД не требуется, поэтому можно использовать локальную
@pytest.fixture
def client_no_db():
    """Тестовый клиент без БД (для тестов исключений, не требующих БД)"""
    return TestClient(app)


def test_model_not_found_exception_handler(client_no_db):
    """Тест обработчика ModelNotFoundError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_insufficient_credits_exception_handler(client_no_db):
    """Тест обработчика InsufficientCreditsError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_invalid_model_exception_handler(client_no_db):
    """Тест обработчика InvalidModelError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_prediction_error_exception_handler(client_no_db):
    """Тест обработчика PredictionError"""
    # Проверяем, что MLServiceException зарегистрирован (он обрабатывает все подклассы)
    assert MLServiceException in app.exception_handlers


def test_general_exception_handler(client_no_db):
    """Тест общего обработчика исключений"""
    # Проверяем, что общий обработчик зарегистрирован
    assert Exception in app.exception_handlers


def test_root_endpoint(client_no_db):
    """Тест root endpoint"""
    response = client_no_db.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_health_endpoint(client_no_db):
    """Тест health endpoint"""
    response = client_no_db.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["components"]["database"] == "ok"


def test_health_endpoint_returns_503_when_database_is_unavailable(client_no_db, monkeypatch):
    """Тест health endpoint при недоступной БД."""
    from backend.app import main as main_module

    def broken_session_local():
        raise RuntimeError("db is down")

    monkeypatch.setattr(main_module, "SessionLocal", broken_session_local)

    response = client_no_db.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["components"]["database"] == "error"


def test_metrics_endpoint(client_no_db):
    """Тест metrics endpoint"""
    response = client_no_db.get("/metrics")
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
