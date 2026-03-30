from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ml_inference_service.database import get_db
from ml_inference_service.deps import get_current_user
from ml_inference_service.models.credit import CreditTransaction, TransactionKind
from ml_inference_service.models.ml import PredictionJob, PredictionJobStatus
from ml_inference_service.models.user import User

router = APIRouter()


class AnalyticsSummary(BaseModel):
    prediction_jobs_total: int
    prediction_jobs_success: int
    prediction_jobs_failed: int
    credits_spent: int


@router.get("/summary", response_model=AnalyticsSummary)
def summary(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> AnalyticsSummary:
    uid = current.id
    total = db.query(func.count(PredictionJob.id)).filter(PredictionJob.user_id == uid).scalar() or 0
    success = (
        db.query(func.count(PredictionJob.id))
        .filter(
            PredictionJob.user_id == uid,
            PredictionJob.status == PredictionJobStatus.success,
        )
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(PredictionJob.id))
        .filter(
            PredictionJob.user_id == uid,
            PredictionJob.status == PredictionJobStatus.failed,
        )
        .scalar()
        or 0
    )
    debit_sum = (
        db.query(func.coalesce(func.sum(CreditTransaction.amount), 0))
        .filter(
            CreditTransaction.user_id == uid,
            CreditTransaction.kind == TransactionKind.debit_prediction,
        )
        .scalar()
        or 0
    )
    spent_abs = max(0, -int(debit_sum))
    return AnalyticsSummary(
        prediction_jobs_total=int(total),
        prediction_jobs_success=int(success),
        prediction_jobs_failed=int(failed),
        credits_spent=spent_abs,
    )
