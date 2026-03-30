import os
import uuid
from typing import Annotated

import joblib
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ml_inference_service.config import get_settings
from ml_inference_service.database import get_db
from ml_inference_service.deps import get_current_user
from ml_inference_service.models.ml import MLModel, PredictionJob, PredictionJobStatus
from ml_inference_service.models.user import User
from ml_inference_service.schemas.ml import (
    JobStatusResponse,
    MLModelCreateResponse,
    MLModelListItem,
    PredictEnqueueResponse,
    PredictRequest,
)
from ml_inference_service.tasks.predict import run_prediction_job

router = APIRouter()
settings = get_settings()


def _ensure_storage_dir(user_id: int) -> str:
    path = os.path.join(settings.models_storage_dir, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def _validate_sklearn_file(path: str) -> None:
    try:
        m = joblib.load(path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not a valid joblib/sklearn artifact: {e}",
        )
    if not hasattr(m, "predict"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Loaded object has no predict()",
        )


@router.post("/models", response_model=MLModelCreateResponse)
async def upload_model(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
    file: UploadFile = File(...),
) -> MLModel:
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
    base = _ensure_storage_dir(current.id)
    fname = f"{uuid.uuid4().hex}.joblib"
    fpath = os.path.join(base, fname)
    with open(fpath, "wb") as f:
        f.write(raw)
    _validate_sklearn_file(fpath)
    row = MLModel(owner_id=current.id, name=name, storage_path=fpath, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/models", response_model=list[MLModelListItem])
def list_models(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> list[MLModel]:
    return (
        db.query(MLModel)
        .filter(MLModel.owner_id == current.id)
        .order_by(MLModel.id.desc())
        .all()
    )


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> None:
    row = db.query(MLModel).filter(MLModel.id == model_id, MLModel.owner_id == current.id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    row.is_active = False
    db.add(row)
    db.commit()


@router.post("/predict", response_model=PredictEnqueueResponse)
def enqueue_predict(
    body: PredictRequest,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> PredictEnqueueResponse:
    cost = settings.prediction_cost_credits
    user = db.query(User).filter(User.id == current.id).with_for_update().one()

    inflight = (
        db.query(func.count(PredictionJob.id))
        .filter(
            PredictionJob.user_id == user.id,
            PredictionJob.status.in_((PredictionJobStatus.pending, PredictionJobStatus.running)),
        )
        .scalar()
    ) or 0

    required = cost * (inflight + 1)
    if user.balance_credits < required:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Not enough credits for a prediction",
        )
    ml_model = (
        db.query(MLModel)
        .filter(MLModel.id == body.model_id, MLModel.owner_id == user.id, MLModel.is_active.is_(True))
        .first()
    )
    if ml_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    job = PredictionJob(
        user_id=user.id,
        ml_model_id=ml_model.id,
        status=PredictionJobStatus.pending,
        input_payload={"features": body.features},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    run_prediction_job.delay(job.id)
    return PredictEnqueueResponse(job_id=job.id, status=job.status.value)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> JobStatusResponse:
    job = (
        db.query(PredictionJob)
        .filter(PredictionJob.id == job_id, PredictionJob.user_id == current.id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(
        id=job.id,
        status=job.status.value,
        result=job.result_payload,
        error_message=job.error_message,
    )
