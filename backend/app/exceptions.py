"""Кастомные исключения для приложения"""
from fastapi import HTTPException, status


class MLServiceException(Exception):
    """Базовое исключение для ML сервиса"""
    pass


class ModelNotFoundError(MLServiceException):
    """Модель не найдена"""
    pass


class InsufficientCreditsError(MLServiceException):
    """Недостаточно кредитов"""
    pass


class InvalidModelError(MLServiceException):
    """Невалидная модель"""
    pass


class PredictionError(MLServiceException):
    """Ошибка при выполнении предсказания"""
    pass
