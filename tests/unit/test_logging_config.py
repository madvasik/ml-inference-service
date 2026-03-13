import pytest
import logging
import json
import sys
from io import StringIO
from backend.app.logging_config import setup_logging, JSONFormatter


def test_json_formatter_basic():
    """Тест базового форматирования JSON"""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None
    )
    
    result = formatter.format(record)
    data = json.loads(result)
    
    assert data["level"] == "INFO"
    assert data["message"] == "Test message"
    assert data["logger"] == "test"
    assert "timestamp" in data
    assert "module" in data
    assert "function" in data
    assert "line" in data


def test_json_formatter_with_exception():
    """Тест форматирования с исключением"""
    formatter = JSONFormatter()
    
    try:
        raise ValueError("Test exception")
    except Exception:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Test error",
            args=(),
            exc_info=sys.exc_info()
        )
    
    result = formatter.format(record)
    data = json.loads(result)
    
    assert data["level"] == "ERROR"
    assert "exception" in data
    assert "ValueError" in data["exception"]


def test_json_formatter_with_extra_fields():
    """Тест форматирования с дополнительными полями"""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None
    )
    
    # Добавляем extra поля
    record.request_id = "req-123"
    record.user_id = 456
    
    result = formatter.format(record)
    data = json.loads(result)
    
    assert data["request_id"] == "req-123"
    assert data["user_id"] == 456


def test_setup_logging_debug_mode():
    """Тест настройки логирования в debug режиме"""
    # Сохраняем текущие handlers
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    
    try:
        setup_logging(debug=True, json_format=False)
        
        # Проверяем уровень
        assert root_logger.level == logging.DEBUG
        
        # Проверяем наличие handler
        assert len(root_logger.handlers) > 0
    finally:
        # Восстанавливаем handlers
        root_logger.handlers = original_handlers


def test_setup_logging_info_mode():
    """Тест настройки логирования в info режиме"""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    
    try:
        setup_logging(debug=False, json_format=False)
        
        # Проверяем уровень
        assert root_logger.level == logging.INFO
    finally:
        root_logger.handlers = original_handlers


def test_setup_logging_json_format():
    """Тест настройки логирования с JSON форматом"""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    
    try:
        setup_logging(debug=False, json_format=True)
        
        # Проверяем наличие handler
        assert len(root_logger.handlers) > 0
        
        # Проверяем форматтер
        handler = root_logger.handlers[-1]
        assert isinstance(handler.formatter, JSONFormatter)
    finally:
        root_logger.handlers = original_handlers


def test_setup_logging_sets_third_party_levels():
    """Тест настройки уровней для сторонних библиотек"""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    
    try:
        setup_logging(debug=False, json_format=False)
        
        # Проверяем уровни для сторонних библиотек
        assert logging.getLogger("uvicorn").level == logging.INFO
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
        assert logging.getLogger("celery").level == logging.INFO
    finally:
        root_logger.handlers = original_handlers


def test_setup_logging_outputs_to_stdout(capsys):
    """Тест, что логирование выводится в stdout"""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    
    try:
        setup_logging(debug=True, json_format=False)
        
        # Логируем сообщение
        root_logger.info("Test log message")
        
        # Проверяем вывод
        captured = capsys.readouterr()
        assert "Test log message" in captured.out
    finally:
        root_logger.handlers = original_handlers
