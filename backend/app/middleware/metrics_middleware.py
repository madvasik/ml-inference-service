import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from backend.app.monitoring.metrics import prediction_requests_total, prediction_latency_seconds


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
            if "/predictions" in request.url.path and request.method == "POST":
                status = "success" if response.status_code < 400 else "error"
                # Извлекаем model_id из запроса, если возможно
                model_id = "unknown"
                try:
                    if hasattr(request.state, "model_id"):
                        model_id = str(request.state.model_id)
                except:
                    pass
                
                prediction_requests_total.labels(status=status, model_id=model_id).inc()
                
                latency = time.time() - start_time
                prediction_latency_seconds.labels(model_id=model_id).observe(latency)
            
            return response
            
        except Exception as e:
            # Обработка ошибок
            if "/predictions" in request.url.path:
                prediction_requests_total.labels(status="error", model_id="unknown").inc()
            raise
