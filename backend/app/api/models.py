import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.ml import get_model_type, load_model, validate_model_file
from backend.app.models import MLModel, User
from backend.app.schemas import MLModelList, MLModelResponse
from backend.app.security import get_current_user


router = APIRouter()


@router.post("/upload", response_model=MLModelResponse, status_code=status.HTTP_201_CREATED)
def upload_model(
    uploaded_model_name: str = Form(..., alias="model_name"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_filename = Path(file.filename or "").name
    if not safe_filename or not safe_filename.lower().endswith(".pkl"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .pkl files are supported")

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
    temp_file_path = user_models_dir / f"upload_{uuid4().hex}.pkl"
    stored_file_path = temp_file_path

    try:
        with temp_file_path.open("wb") as output:
            output.write(file.file.read())

        if not validate_model_file(str(temp_file_path)):
            temp_file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid model file. Must be a scikit-learn model.",
            )

        model_type = get_model_type(load_model(str(temp_file_path)))
        db_model = MLModel(
            owner_id=current_user.id,
            model_name=uploaded_model_name,
            file_path=str(temp_file_path),
            model_type=model_type,
        )
        db.add(db_model)
        db.flush()

        final_file_path = user_models_dir / f"{db_model.id}.pkl"
        os.rename(temp_file_path, final_file_path)
        stored_file_path = final_file_path
        db_model.file_path = str(final_file_path)
        db.commit()
        db.refresh(db_model)
        return db_model
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        Path(stored_file_path).unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload model: {exc}")


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

    Path(model.file_path).unlink(missing_ok=True)
    db.delete(model)
    db.commit()
