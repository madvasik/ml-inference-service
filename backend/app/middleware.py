from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.config import settings
from backend.app.metrics import prediction_errors_total, prediction_requests_total


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for Prometheus request accounting."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/metrics", "/health", "/"]:
            return await call_next(request)

        try:
            response = await call_next(request)

            if "/predictions" in request.url.path and request.method == "POST":
                request_status = "pending" if response.status_code == 202 else "error"
                model_id = "unknown"
                if hasattr(request.state, "model_id"):
                    model_id = str(request.state.model_id)

                prediction_requests_total.labels(status=request_status, model_id=model_id).inc()

                if request_status != "pending":
                    error_type = "api_error"
                    if response.status_code == 404:
                        error_type = "model_not_found"
                    elif response.status_code == 402:
                        error_type = "insufficient_credits"
                    prediction_errors_total.labels(error_type=error_type).inc()

            return response
        except Exception:
            if "/predictions" in request.url.path:
                model_id = "unknown"
                if hasattr(request.state, "model_id"):
                    model_id = str(request.state.model_id)
                prediction_requests_total.labels(status="error", model_id=model_id).inc()
                prediction_errors_total.labels(error_type="exception").inc()
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting."""

    def __init__(self, app):
        super().__init__(app)
        self._requests: dict[str, list] = defaultdict(list)
        self._cleanup_interval = 300
        self._last_cleanup = time.time()

    def _get_key(self, request: Request) -> tuple[str, bool]:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from backend.app.security import decode_token

                token = auth_header.split(" ")[1]
                payload = decode_token(token)
                if payload and payload.get("type") == "access":
                    user_id = payload.get("sub")
                    if user_id:
                        return f"user:{user_id}", True
            except Exception:
                pass

        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}", False

    def _cleanup_old_entries(self):
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        cutoff_time = current_time - 120
        keys_to_delete = []

        for key, timestamps in self._requests.items():
            self._requests[key] = [ts for ts in timestamps if ts > cutoff_time]
            if not self._requests[key]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._requests[key]

        self._last_cleanup = current_time

    def _check_rate_limit(self, key: str, limit: int, window: int = 60) -> tuple[bool, int]:
        current_time = time.time()
        cutoff_time = current_time - window

        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff_time]

        count = len(self._requests[key])
        if count >= limit:
            return False, 0

        self._requests[key].append(current_time)
        remaining = max(0, limit - count - 1)
        return True, remaining

    async def dispatch(self, request: Request, call_next):
        is_excluded = request.url.path in ["/metrics", "/health", "/", "/docs", "/openapi.json", "/redoc"]

        self._cleanup_old_entries()

        key, is_user = self._get_key(request)
        limit = settings.rate_limit_per_user_per_minute if is_user else settings.rate_limit_per_minute

        if is_excluded:
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(limit)
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
                    "Retry-After": "60",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
        return response
