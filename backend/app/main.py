from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import backend.app.db as db_module
from backend.app.api import admin, auth, billing, models, predictions, system, users
from backend.app.billing import add_credits, ensure_balance
from backend.app.config import settings
from backend.app.db import database_connection_ok, database_schema_status
from backend.app.log_config import setup_logging
from backend.app.loyalty import ensure_default_loyalty_rules, refresh_loyalty_metrics
from backend.app.middleware import MetricsMiddleware, RateLimitMiddleware
from backend.app.models import LoyaltyTier, User, UserRole
from backend.app.security import get_password_hash


setup_logging(debug=settings.debug, json_format=settings.log_json_format)
logger = logging.getLogger(__name__)


def ensure_initial_admin(db: Session) -> User | None:
    if not settings.initial_admin_email or not settings.initial_admin_password:
        return None

    admin_user = db.query(User).filter(User.email == settings.initial_admin_email).first()
    if admin_user is not None:
        return admin_user

    admin_user = User(
        email=settings.initial_admin_email,
        password_hash=get_password_hash(settings.initial_admin_password),
        role=UserRole.ADMIN,
        loyalty_tier=LoyaltyTier.NONE,
        loyalty_discount_percent=0,
    )
    db.add(admin_user)
    db.flush()
    ensure_balance(db, admin_user.id)
    add_credits(db, admin_user.id, settings.initial_admin_credits, "Initial admin credits")
    db.commit()
    db.refresh(admin_user)
    return admin_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    db: Session | None = None
    try:
        db = db_module.SessionLocal()
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
            if admin_user is not None:
                logger.info("Initial admin ensured: %s", admin_user.email)
    except Exception as exc:
        logger.error("Startup bootstrap failed: %s", exc, exc_info=True)
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
    # Browsers reject credentialed requests when Allow-Origin is '*' — disable credentials only in that case.
    cors_allow_credentials = cors_origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
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
    app.add_exception_handler(Exception, general_exception_handler)
    return app


async def general_exception_handler(request: Request, exc: Exception):
    del request
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


app = create_app()
