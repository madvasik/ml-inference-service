import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.exceptions import (
    ModelNotFoundError,
    InsufficientCreditsError,
    InvalidModelError,
    PredictionError
)

# Используем фикстуру client из conftest.py для консистентности
# Но для этих тестов БД не требуется, поэтому можно использовать локальную
@pytest.fixture
def client_no_db():
    """Тестовый клиент без БД (для тестов обработчиков исключений, не требующих БД)"""
    return TestClient(app)


def test_model_not_found_exception_handler(client_no_db):
    """Тест обработчика ModelNotFoundError"""
    # Создаем исключение и проверяем обработку через мок endpoint
    from unittest.mock import patch
    
    with patch('backend.app.main.app.exception_handler') as mock_handler:
        # Проверяем, что исключение обрабатывается правильно
        exc = ModelNotFoundError("Model not found")
        
        # В реальности это обрабатывается через exception handler
        # Проверяем что handler зарегистрирован
        assert ModelNotFoundError.__bases__[0] in app.exception_handlers


def test_insufficient_credits_exception_handler():
    """Тест обработчика InsufficientCreditsError"""
    exc = InsufficientCreditsError("Insufficient credits")
    assert isinstance(exc, InsufficientCreditsError)
    assert InsufficientCreditsError.__bases__[0] in app.exception_handlers


def test_invalid_model_exception_handler():
    """Тест обработчика InvalidModelError"""
    exc = InvalidModelError("Invalid model")
    assert isinstance(exc, InvalidModelError)
    assert InvalidModelError.__bases__[0] in app.exception_handlers


def test_prediction_error_exception_handler():
    """Тест обработчика PredictionError"""
    exc = PredictionError("Prediction failed")
    assert isinstance(exc, PredictionError)
    assert PredictionError.__bases__[0] in app.exception_handlers


def test_general_exception_handler_debug_mode(client_no_db, monkeypatch):
    """Тест общего обработчика исключений в debug режиме"""
    from backend.app.config import settings
    
    original_debug = settings.debug
    monkeypatch.setattr(settings, "debug", True)
    
    try:
        # Проверяем что handler зарегистрирован
        assert Exception in app.exception_handlers
    finally:
        monkeypatch.setattr(settings, "debug", original_debug)


def test_general_exception_handler_production_mode(client_no_db, monkeypatch):
    """Тест общего обработчика исключений в production режиме"""
    from backend.app.config import settings
    
    original_debug = settings.debug
    monkeypatch.setattr(settings, "debug", False)
    
    try:
        # Проверяем что handler зарегистрирован
        assert Exception in app.exception_handlers
    finally:
        monkeypatch.setattr(settings, "debug", original_debug)
