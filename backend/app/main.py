from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import Response

from backend.app.api.routes import admin, auth, billing, metrics, models, predictions, users
from backend.app.core.config import settings
from backend.app.core.exceptions import (
    InsufficientCreditsError,
    InvalidModelError,
    MLServiceException,
    ModelNotFoundError,
    PredictionError,
)
from backend.app.core.logging import setup_logging
from backend.app.db.readiness import database_schema_status
from backend.app.db.session import SessionLocal, database_connection_ok
from backend.app.domain.models.prediction import Prediction
from backend.app.observability.metrics import active_users
from backend.app.observability.middleware.metrics_middleware import MetricsMiddleware
from backend.app.observability.middleware.rate_limit import RateLimitMiddleware
from backend.app.services.bootstrap_service import ensure_initial_admin
from backend.app.services.loyalty_service import ensure_default_loyalty_rules, refresh_loyalty_metrics

# Настройка логирования
setup_logging(debug=settings.debug, json_format=settings.log_json_format)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация данных приложения при старте."""
    db: Session | None = None
    try:
        db = SessionLocal()
        database_connection_ok(db)
        schema_ready, schema_status, missing_tables = database_schema_status(db)
        if not schema_ready:
            if schema_status == "missing_tables":
                logger.warning(
                    "Startup bootstrap skipped: database schema is not initialized. Missing tables: %s",
                    ", ".join(missing_tables),
                )
            else:
                logger.warning("Startup bootstrap skipped: schema probe failed (%s)", schema_status)
        else:
            ensure_default_loyalty_rules(db)
            admin_user = ensure_initial_admin(db)
            refresh_loyalty_metrics(db)
            if admin_user:
                logger.info("Initial admin ensured: %s", admin_user.email)
    except Exception as exc:
        logger.warning("Startup bootstrap failed: %s", exc)
    finally:
        if db is not None:
            db.close()
    yield


app = FastAPI(
    title="ML Inference Service",
    description="ML prediction service with billing",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(metrics.router, prefix=f"{settings.api_v1_prefix}/metrics", tags=["metrics"])


@app.get("/")
def root():
    return {"message": "ML Inference Service API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    db_status = "unknown"
    schema_status = "unknown"
    missing_tables: list[str] = []
    schema_ready = False

    try:
        db: Session = SessionLocal()
        try:
            database_connection_ok(db)
            db_status = "ok"
            schema_ready, schema_status, missing_tables = database_schema_status(db)
        finally:
            db.close()
    except Exception as exc:
        db_status = "error"
        schema_status = "unknown"
        logger.warning("Health check database probe failed: %s", exc)

    overall_status = "healthy" if db_status == "ok" and schema_ready else "unhealthy"
    status_code = status.HTTP_200_OK if overall_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    content = {
        "status": overall_status,
        "components": {
            "api": "ok",
            "database": db_status,
            "schema": schema_status,
        },
    }
    if missing_tables:
        content["details"] = {"missing_tables": missing_tables}

    return JSONResponse(
        status_code=status_code,
        content=content,
    )


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    # Обновляем метрику активных пользователей перед возвратом метрик
    try:
        db: Session = SessionLocal()
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=15)
            unique_users = db.query(func.count(func.distinct(Prediction.user_id))).filter(
                Prediction.created_at >= cutoff_time
            ).scalar() or 0
            active_users.set(unique_users)
            refresh_loyalty_metrics(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to update active_users metric: {str(e)}")
    
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
