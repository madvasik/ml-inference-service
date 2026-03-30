from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import Response

import backend.app.db as db_module
from backend.app.db import get_db
from backend.app.loyalty import refresh_loyalty_metrics
from backend.app.metrics import active_users
from backend.app.models import Prediction, User
from backend.app.security import get_current_admin


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


def _health_payload() -> tuple[int, dict]:
    db_status, schema_status, missing_tables = db_module.probe_database_health()
    status_code = status.HTTP_200_OK if db_status == "ok" and schema_status == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    content = {
        "status": "healthy" if status_code == status.HTTP_200_OK else "unhealthy",
        "components": {"api": "ok", "database": db_status, "schema": schema_status},
    }
    if missing_tables:
        content["details"] = {"missing_tables": missing_tables}
    return status_code, content


@router.get("/")
def root():
    return {"message": "ML Inference Service API", "version": "1.0.0"}


@router.get("/health")
def health_check():
    status_code, content = _health_payload()
    return JSONResponse(status_code=status_code, content=content)


@router.get("/metrics")
def metrics():
    try:
        session = db_module.SessionLocal()
        try:
            _refresh_runtime_metrics(session)
        finally:
            session.close()
    except Exception as exc:
        logger.warning("Failed to update active_users metric: %s", exc)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@api_router.post("/metrics/update-active-users")
def update_active_users_metric(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    del current_user
    unique_users = _refresh_runtime_metrics(db)
    return {"active_users": unique_users, "updated_at": datetime.now(timezone.utc).isoformat()}
