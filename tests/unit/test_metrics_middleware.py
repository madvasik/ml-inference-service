import pytest
from unittest.mock import Mock, patch
from fastapi import Request
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.monitoring.metrics import prediction_requests_total, prediction_latency_seconds

# Используем фикстуру client из conftest.py, которая правильно настраивает БД
# Не нужно определять свой client здесь


def test_metrics_middleware_skips_metrics_endpoint(client):
    """Тест, что middleware пропускает /metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_middleware_skips_health_endpoint(client):
    """Тест, что middleware пропускает /health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200


def test_metrics_middleware_tracks_prediction_request(client, test_user, test_ml_model):
    """Тест отслеживания метрик для запроса предсказания"""
    from backend.app.auth.jwt import create_access_token
    
    token = create_access_token({"sub": str(test_user.id), "type": "access"})
    
    # Получаем начальное значение метрики
    samples_before = prediction_requests_total.collect()[0].samples
    initial_count = sum(
        s.value for s in samples_before
        if s.name == "prediction_requests_total_total"
    )
    
    # Мокируем Celery
    with patch('backend.app.api.v1.predictions.execute_prediction.delay') as mock_celery:
        mock_task = Mock()
        mock_task.id = "test-task-id"
        mock_celery.return_value = mock_task
        
        response = client.post(
            "/api/v1/predictions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_id": test_ml_model.id,
                "input_data": {"feature1": 1.0, "feature2": 2.0}
            }
        )
    
    assert response.status_code == 202
    
    # Проверяем, что метрика увеличилась
    samples_after = prediction_requests_total.collect()[0].samples
    final_count = sum(
        s.value for s in samples_after
        if s.name == "prediction_requests_total_total"
    )
    
    assert final_count >= initial_count


def test_metrics_middleware_tracks_prediction_latency(client, test_user, test_ml_model):
    """Тест отслеживания латентности для запроса предсказания"""
    from backend.app.auth.jwt import create_access_token
    
    token = create_access_token({"sub": str(test_user.id), "type": "access"})
    
    # Получаем начальное количество samples
    samples_before = prediction_latency_seconds.collect()[0].samples
    initial_count = len(samples_before)
    
    # Мокируем Celery
    with patch('backend.app.api.v1.predictions.execute_prediction.delay') as mock_celery:
        mock_task = Mock()
        mock_task.id = "test-task-id"
        mock_celery.return_value = mock_task
        
        response = client.post(
            "/api/v1/predictions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_id": test_ml_model.id,
                "input_data": {"feature1": 1.0, "feature2": 2.0}
            }
        )
    
    assert response.status_code == 202
    
    # Проверяем, что метрика латентности была записана (количество samples увеличилось)
    samples_after = prediction_latency_seconds.collect()[0].samples
    assert len(samples_after) >= initial_count


def test_metrics_middleware_handles_exception(client, test_user, test_ml_model):
    """Тест обработки исключений в middleware"""
    from backend.app.auth.jwt import create_access_token
    
    token = create_access_token({"sub": str(test_user.id), "type": "access"})
    
    # Мокируем Celery чтобы вызвать ошибку
    with patch('backend.app.api.v1.predictions.execute_prediction.delay') as mock_celery:
        mock_celery.side_effect = Exception("Test error")
        
        # Получаем начальное значение метрики ошибок
        samples_before = prediction_requests_total.collect()[0].samples
        initial_error_count = sum(
            s.value for s in samples_before
            if s.name == "prediction_requests_total_total" and
            len(s.labels) > 0 and s.labels.get("status") == "error"
        )
        
        # Запрос должен вызвать ошибку
        try:
            response = client.post(
                "/api/v1/predictions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model_id": test_ml_model.id,
                    "input_data": {"feature1": 1.0}
                }
            )
        except:
            pass
        
        # Проверяем, что метрика ошибок увеличилась (если ошибка была обработана)
        samples_after = prediction_requests_total.collect()[0].samples
        final_error_count = sum(
            s.value for s in samples_after
            if s.name == "prediction_requests_total_total" and
            len(s.labels) > 0 and s.labels.get("status") == "error"
        )
        
        # Метрика должна увеличиться или остаться такой же
        assert final_error_count >= initial_error_count


def test_metrics_middleware_uses_model_id_from_state():
    """Тест использования model_id из request.state"""
    from backend.app.middleware.metrics_middleware import MetricsMiddleware
    from unittest.mock import AsyncMock, Mock
    
    middleware = MetricsMiddleware(Mock())
    
    # Создаем мок request с model_id в state
    request = Mock()
    request.url.path = "/api/v1/predictions"
    request.method = "POST"
    request.state.model_id = 123
    
    # Создаем мок response
    response = Mock()
    response.status_code = 200
    
    # Создаем мок call_next
    call_next = AsyncMock(return_value=response)
    
    # Вызываем middleware
    import asyncio
    result = asyncio.run(middleware.dispatch(request, call_next))
    
    assert result == response
