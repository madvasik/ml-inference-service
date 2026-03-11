import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from backend.app.api.deps import get_current_user
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.models.ml_model import MLModel
from backend.app.services.model_loader import validate_model_file, load_model, save_model, get_model_type
from backend.app.schemas.model import MLModelResponse, MLModelList
from backend.app.config import settings

router = APIRouter()


@router.post("/upload", response_model=MLModelResponse, status_code=status.HTTP_201_CREATED)
def upload_model(
    model_name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Загрузка ML модели"""
    # Проверка расширения файла
    if not file.filename or not file.filename.endswith('.pkl'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pkl files are supported"
        )
    
    # Проверка размера файла
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    file.file.seek(0, 2)  # Переход в конец файла
    file_size = file.file.tell()
    file.file.seek(0)  # Возврат в начало
    
    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.max_upload_size_mb}MB"
        )
    
    # Валидация имени модели
    if not model_name or len(model_name.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model name cannot be empty"
        )
    
    if len(model_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model name is too long (max 255 characters)"
        )
    
    # Создание директории для пользователя
    user_models_dir = os.path.join(settings.ml_models_dir, str(current_user.id))
    os.makedirs(user_models_dir, exist_ok=True)
    
    # Сохранение временного файла
    temp_file_path = os.path.join(user_models_dir, f"temp_{file.filename}")
    try:
        with open(temp_file_path, 'wb') as f:
            content = file.file.read()
            f.write(content)
        
        # Валидация модели
        if not validate_model_file(temp_file_path):
            os.remove(temp_file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid model file. Must be a scikit-learn model."
            )
        
        # Загрузка модели для определения типа
        model = load_model(temp_file_path)
        model_type = get_model_type(model)
        
        # Создание записи в БД
        db_model = MLModel(
            owner_id=current_user.id,
            model_name=model_name,
            file_path=temp_file_path,
            model_type=model_type
        )
        db.add(db_model)
        db.flush()
        
        # Переименование файла с ID модели
        final_file_path = os.path.join(user_models_dir, f"{db_model.id}.pkl")
        os.rename(temp_file_path, final_file_path)
        db_model.file_path = final_file_path
        db.commit()
        db.refresh(db_model)
        
        return db_model
        
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload model: {str(e)}"
        )


@router.get("", response_model=MLModelList)
def list_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Список моделей пользователя"""
    models = db.query(MLModel).filter(MLModel.owner_id == current_user.id).all()
    return MLModelList(models=models, total=len(models))


@router.get("/{model_id}", response_model=MLModelResponse)
def get_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение информации о модели"""
    model = db.query(MLModel).filter(
        MLModel.id == model_id,
        MLModel.owner_id == current_user.id
    ).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удаление модели"""
    model = db.query(MLModel).filter(
        MLModel.id == model_id,
        MLModel.owner_id == current_user.id
    ).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Удаление файла модели
    if os.path.exists(model.file_path):
        os.remove(model.file_path)
    
    db.delete(model)
    db.commit()
    
    return None
