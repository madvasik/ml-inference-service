from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import Response

from backend.app.db import SessionLocal, database_connection_ok, database_schema_status, get_db
from backend.app.loyalty import refresh_loyalty_metrics
from backend.app.metrics import active_users
from backend.app.models import Prediction


logger = logging.getLogger(__name__)

router = APIRouter()
api_router = APIRouter()


def _refresh_runtime_metrics(db: Session) -> int:
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    unique_users = (
        db.query(func.count(func.distinct(Prediction.user_id)))
        .filter(Prediction.created_at >= cutoff_time)
        .scalar()
        or 0
    )
    active_users.set(unique_users)
    refresh_loyalty_metrics(db)
    return unique_users


@router.get("/")
def root():
    return {"message": "ML Inference Service API", "version": "1.0.0"}


@router.get("/health")
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

    return JSONResponse(status_code=status_code, content=content)


@router.get("/metrics")
def metrics():
    try:
        db: Session = SessionLocal()
        try:
            _refresh_runtime_metrics(db)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to update active_users metric: %s", exc)

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@api_router.post("/metrics/update-active-users")
def update_active_users_metric(db: Session = Depends(get_db)):
    unique_users = _refresh_runtime_metrics(db)
    return {"active_users": unique_users, "updated_at": datetime.now(timezone.utc).isoformat()}
