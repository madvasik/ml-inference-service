import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from backend.app.monitoring.metrics import (
    prediction_requests_total, 
    prediction_latency_seconds,
    prediction_errors_total
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware для сбора метрик Prometheus"""
    
    async def dispatch(self, request: Request, call_next):
        # Пропускаем метрики и health check
        if request.url.path in ["/metrics", "/health", "/"]:
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Собираем метрики для предсказаний
            # Примечание: метрика инкрементируется здесь только для создания запроса
            # Реальный статус (completed/failed) обновляется в Celery task
            if "/predictions" in request.url.path and request.method == "POST":
                # Статус "pending" означает, что запрос создан и отправлен в очередь
                status = "pending" if response.status_code == 202 else "error"
                # Извлекаем model_id из запроса, если возможно
                model_id = "unknown"
                try:
                    if hasattr(request.state, "model_id"):
                        model_id = str(request.state.model_id)
                except:
                    pass
                
                prediction_requests_total.labels(status=status, model_id=model_id).inc()
                
                # Реальная задержка выполнения предсказания измеряется в Celery task (prediction_tasks.py)
                # Здесь мы только регистрируем создание запроса
                if status != "success":
                    # Регистрируем ошибку API
                    error_type = "api_error"
                    if response.status_code == 404:
                        error_type = "model_not_found"
                    elif response.status_code == 402:
                        error_type = "insufficient_credits"
                    prediction_errors_total.labels(error_type=error_type).inc()
            
            return response
            
        except Exception as e:
            # Обработка ошибок
            if "/predictions" in request.url.path:
                model_id = "unknown"
                try:
                    if hasattr(request.state, "model_id"):
                        model_id = str(request.state.model_id)
                except:
                    pass
                prediction_requests_total.labels(status="error", model_id=model_id).inc()
                prediction_errors_total.labels(error_type="exception").inc()
            raise
