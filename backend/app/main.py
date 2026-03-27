from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.routes import admin, auth, billing, models, predictions, system, users
from backend.app.config import settings
from backend.app.core.exceptions import (
    InsufficientCreditsError,
    InvalidModelError,
    MLServiceException,
    ModelNotFoundError,
    PredictionError,
)
from backend.app.core.logging import setup_logging
from backend.app.db import SessionLocal, database_connection_ok, database_schema_status
from backend.app.middleware import MetricsMiddleware, RateLimitMiddleware
from backend.app.bootstrap import ensure_initial_admin
from backend.app.loyalty import ensure_default_loyalty_rules, refresh_loyalty_metrics

setup_logging(debug=settings.debug, json_format=settings.log_json_format)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="ML Inference Service",
        description="ML prediction service with billing",
        version="1.0.0",
        lifespan=lifespan,
    )

    cors_origins = (
        settings.cors_origins.split(",")
        if "," in settings.cors_origins
        else (settings.cors_origins.split() if settings.cors_origins != "*" else ["*"])
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MetricsMiddleware)

    app.include_router(system.router)
    app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
    app.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])
    app.include_router(models.router, prefix=f"{settings.api_v1_prefix}/models", tags=["models"])
    app.include_router(predictions.router, prefix=f"{settings.api_v1_prefix}/predictions", tags=["predictions"])
    app.include_router(billing.router, prefix=f"{settings.api_v1_prefix}/billing", tags=["billing"])
    app.include_router(admin.router, prefix=f"{settings.api_v1_prefix}/admin", tags=["admin"])
    app.include_router(system.api_router, prefix=settings.api_v1_prefix, tags=["metrics"])
    app.add_exception_handler(MLServiceException, ml_service_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    return app


async def ml_service_exception_handler(request: Request, exc: MLServiceException):
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


async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error" if not settings.debug else str(exc)}
    )


app = create_app()
