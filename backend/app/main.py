from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import logging
from backend.app.api.v1 import auth, users, models, predictions, billing, admin
from backend.app.config import settings
from backend.app.middleware.metrics_middleware import MetricsMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.exceptions import (
    MLServiceException,
    ModelNotFoundError,
    InsufficientCreditsError,
    InvalidModelError,
    PredictionError
)
from backend.app.logging_config import setup_logging

# Настройка логирования
setup_logging(debug=settings.debug, json_format=settings.log_json_format)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ML Inference Service",
    description="ML prediction service with billing",
    version="1.0.0"
)

# CORS middleware
cors_origins = settings.cors_origins.split(",") if "," in settings.cors_origins else (settings.cors_origins.split() if settings.cors_origins != "*" else ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# Rate limiting middleware (должен быть перед metrics для правильного подсчета)
app.add_middleware(RateLimitMiddleware)

# Metrics middleware
app.add_middleware(MetricsMiddleware)

# Подключение роутеров
app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])
app.include_router(models.router, prefix=f"{settings.api_v1_prefix}/models", tags=["models"])
app.include_router(predictions.router, prefix=f"{settings.api_v1_prefix}/predictions", tags=["predictions"])
app.include_router(billing.router, prefix=f"{settings.api_v1_prefix}/billing", tags=["billing"])
app.include_router(admin.router, prefix=f"{settings.api_v1_prefix}/admin", tags=["admin"])


@app.get("/")
def root():
    return {"message": "ML Inference Service API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Глобальные exception handlers
@app.exception_handler(MLServiceException)
async def ml_service_exception_handler(request: Request, exc: MLServiceException):
    """Обработчик кастомных исключений ML сервиса"""
    logger.error(f"ML Service Exception: {str(exc)}", exc_info=True)
    
    if isinstance(exc, ModelNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)}
        )
    elif isinstance(exc, InsufficientCreditsError):
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"detail": str(exc)}
        )
    elif isinstance(exc, InvalidModelError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
    elif isinstance(exc, PredictionError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик общих исключений"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error" if not settings.debug else str(exc)}
    )
