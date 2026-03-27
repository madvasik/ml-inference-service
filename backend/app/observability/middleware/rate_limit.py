import time
from collections import defaultdict
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from backend.app.core.config import settings
from typing import Dict, Tuple


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware для rate limiting с in-memory хранилищем"""
    
    def __init__(self, app):
        super().__init__(app)
        # Хранилище: {key: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._cleanup_interval = 300  # Очистка каждые 5 минут
        self._last_cleanup = time.time()
    
    def _get_key(self, request: Request) -> Tuple[str, bool]:
        """Получает ключ для rate limiting (IP или user_id)"""
        # Пытаемся извлечь user_id из токена
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from backend.app.auth.jwt import decode_token
                token = auth_header.split(" ")[1]
                payload = decode_token(token)
                if payload and payload.get("type") == "access":
                    user_id = payload.get("sub")
                    if user_id:
                        return f"user:{user_id}", True
            except:
                pass
        
        # Используем IP адрес
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}", False
    
    def _cleanup_old_entries(self):
        """Очистка старых записей"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff_time = current_time - 120  # Удаляем записи старше 2 минут
        keys_to_delete = []
        
        for key, timestamps in self._requests.items():
            self._requests[key] = [ts for ts in timestamps if ts > cutoff_time]
            if not self._requests[key]:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self._requests[key]
        
        self._last_cleanup = current_time
    
    def _check_rate_limit(self, key: str, limit: int, window: int = 60) -> Tuple[bool, int]:
        """Проверяет rate limit и возвращает (allowed, remaining)"""
        current_time = time.time()
        cutoff_time = current_time - window
        
        # Очищаем старые записи
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff_time]
        
        # Проверяем лимит
        count = len(self._requests[key])
        if count >= limit:
            return False, 0
        
        # Добавляем текущий запрос
        self._requests[key].append(current_time)
        remaining = max(0, limit - count - 1)
        
        return True, remaining
    
    async def dispatch(self, request: Request, call_next):
        # Пропускаем метрики, health check и документацию (но все равно добавляем заголовки)
        is_excluded = request.url.path in ["/metrics", "/health", "/", "/docs", "/openapi.json", "/redoc"]
        
        # Периодическая очистка
        self._cleanup_old_entries()
        
        # Получаем ключ для rate limiting
        key, is_user = self._get_key(request)
        
        # Применяем соответствующий лимит
        if is_user:
            limit = settings.rate_limit_per_user_per_minute
        else:
            limit = settings.rate_limit_per_minute
        
        # Для исключенных endpoints не проверяем лимит, но все равно добавляем заголовки
        if is_excluded:
            response = await call_next(request)
            # Добавляем заголовки rate limit даже для исключенных endpoints
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(limit)  # Для исключенных endpoints всегда полный лимит
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
            return response
        
        allowed, remaining = self._check_rate_limit(key, limit)
        
        if not allowed:
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + 60),
                    "Retry-After": "60"
                }
            )
        
        response = await call_next(request)
        
        # Добавляем заголовки rate limit
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
        
        return response
