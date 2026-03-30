import json
import os
from pathlib import Path
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import exists
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.ml import get_feature_names, get_model_type, load_model
from backend.app.models import MLModel, Prediction, User
from backend.app.schemas import MLModelList, MLModelResponse
from backend.app.security import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_feature_names(raw_feature_names: str | None) -> list[str] | None:
    if raw_feature_names is None:
        return None

    try:
        parsed = json.loads(raw_feature_names)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="feature_names must be a JSON array of strings",
        ) from exc

    if not isinstance(parsed, list) or not parsed or any(not isinstance(item, str) or not item.strip() for item in parsed):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="feature_names must be a non-empty JSON array of non-empty strings",
        )
    if len(set(parsed)) != len(parsed):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="feature_names must not contain duplicates",
        )
    return parsed


@router.post("/upload", response_model=MLModelResponse, status_code=status.HTTP_201_CREATED)
def upload_model(
    uploaded_model_name: str = Form(..., alias="model_name"),
    raw_feature_names: str | None = Form(None, alias="feature_names"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_filename = Path(file.filename or "").name
    if not safe_filename or not safe_filename.lower().endswith(".skops"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .skops files are supported")

    if not uploaded_model_name or not uploaded_model_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name cannot be empty")
    if len(uploaded_model_name) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name is too long (max 255 characters)")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.max_upload_size_mb}MB",
        )

    user_models_dir = Path(settings.ml_models_dir) / str(current_user.id)
    user_models_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = user_models_dir / f"upload_{uuid4().hex}.skops"
    stored_file_path = temp_file_path
    uploaded_feature_names = _parse_feature_names(raw_feature_names)

    try:
        with temp_file_path.open("wb") as output:
            output.write(file.file.read())

        ml_model = load_model(str(temp_file_path))
        model_feature_names = get_feature_names(ml_model)
        feature_names = model_feature_names or uploaded_feature_names
        if feature_names is None:
            temp_file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model must include embedded feature names or upload feature_names explicitly.",
            )
        if hasattr(ml_model, "n_features_in_") and len(feature_names) != int(ml_model.n_features_in_):
            temp_file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="feature_names must match the model feature count.",
            )

        model_type = get_model_type(ml_model)
        db_model = MLModel(
            owner_id=current_user.id,
            model_name=uploaded_model_name,
            file_path=str(temp_file_path),
            model_type=model_type,
            feature_names=feature_names,
        )
        db.add(db_model)
        db.flush()

        final_file_path = user_models_dir / f"{db_model.id}.skops"
        os.rename(temp_file_path, final_file_path)
        stored_file_path = final_file_path
        db_model.file_path = str(final_file_path)
        db.commit()
        db.refresh(db_model)
        return db_model
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        Path(stored_file_path).unlink(missing_ok=True)
        logger.exception("Failed to upload model for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload model",
        )


@router.get("", response_model=MLModelList)
def list_models(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    models = db.query(MLModel).filter(MLModel.owner_id == current_user.id).all()
    return MLModelList(models=models, total=len(models))


@router.get("/{model_id}", response_model=MLModelResponse)
def get_model(model_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    model = db.query(MLModel).filter(MLModel.id == model_id, MLModel.owner_id == current_user.id).first()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    model = db.query(MLModel).filter(MLModel.id == model_id, MLModel.owner_id == current_user.id).first()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    has_predictions = db.query(exists().where(Prediction.model_id == model.id)).scalar()
    if has_predictions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model cannot be deleted while predictions exist",
        )

    model_file_path = Path(model.file_path)

    try:
        db.delete(model)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to delete model %s for user %s", model_id, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete model",
        )

    model_file_path.unlink(missing_ok=True)
