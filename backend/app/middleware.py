from __future__ import annotations

import logging
import time

from fastapi import Request, status
from redis import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.config import settings
from backend.app.metrics import prediction_errors_total, prediction_requests_total


logger = logging.getLogger(__name__)


class InMemoryRateLimitStore:
    def __init__(self):
        self._buckets: dict[str, tuple[int, int]] = {}

    def increment(self, key: str, limit: int, window: int) -> tuple[bool, int, int]:
        current_time = int(time.time())
        window_start = current_time - (current_time % window)
        reset_at = window_start + window
        bucket_key = f"{window_start}:{key}"
        count, _ = self._buckets.get(bucket_key, (0, reset_at))
        count += 1
        self._buckets = {
            existing_key: value
            for existing_key, value in self._buckets.items()
            if value[1] > current_time
        }
        self._buckets[bucket_key] = (count, reset_at)
        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining, reset_at


class RedisRateLimitStore:
    def __init__(self, redis_client: Redis | None = None, redis_url: str | None = None):
        self._redis = redis_client or Redis.from_url(
            redis_url or settings.rate_limit_storage_url or settings.celery_broker_url,
            decode_responses=True,
        )

    def increment(self, key: str, limit: int, window: int) -> tuple[bool, int, int]:
        current_time = int(time.time())
        window_start = current_time - (current_time % window)
        reset_at = window_start + window
        bucket_key = f"rate_limit:{window_start}:{key}"
        pipeline = self._redis.pipeline()
        pipeline.incr(bucket_key)
        pipeline.expire(bucket_key, window + 1)
        request_count, _ = pipeline.execute()
        count = int(request_count)
        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining, reset_at


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
    """Redis-backed rate limiting shared across app instances."""

    WINDOW_SECONDS = 60

    def __init__(self, app):
        super().__init__(app)
        self._store = RedisRateLimitStore()

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

    async def dispatch(self, request: Request, call_next):
        is_excluded = request.url.path in ["/metrics", "/health", "/", "/docs", "/openapi.json", "/redoc"]

        key, is_user = self._get_key(request)
        limit = settings.rate_limit_per_user_per_minute if is_user else settings.rate_limit_per_minute

        if is_excluded:
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(limit)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.WINDOW_SECONDS)
            return response

        try:
            allowed, remaining, reset_at = self._store.increment(key, limit, self.WINDOW_SECONDS)
        except RedisError:
            logger.exception("Rate limit storage is unavailable")
            return Response(
                content='{"detail": "Rate limit service unavailable. Please try again later."}',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json",
            )

        if not allowed:
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(max(1, reset_at - int(time.time()))),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response
