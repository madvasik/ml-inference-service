from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.app.api.deps import get_current_user
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.models.ml_model import MLModel
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.services.model_loader import load_model
from backend.app.services.ml_service import predict
from backend.app.billing.service import deduct_credits, get_balance
from backend.app.schemas.prediction import PredictionCreate, PredictionResponse, PredictionList, PredictionTaskResponse
from backend.app.tasks.prediction_tasks import execute_prediction
from backend.app.config import settings
from backend.app.monitoring.metrics import active_users

router = APIRouter()


@router.post("", response_model=PredictionTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def create_prediction(
    prediction_data: PredictionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание асинхронного предсказания"""
    # Проверка существования модели и прав доступа
    model = db.query(MLModel).filter(
        MLModel.id == prediction_data.model_id,
        MLModel.owner_id == current_user.id
    ).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Устанавливаем model_id в request.state для middleware
    request.state.model_id = str(prediction_data.model_id)
    
    # Проверка баланса
    balance = get_balance(db, current_user.id)
    if balance < settings.prediction_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Required: {settings.prediction_cost}, Available: {balance}"
        )
    
    # Метрика active_users будет обновляться через периодическую задачу или endpoint
    
    # Создание записи предсказания
    prediction = Prediction(
        user_id=current_user.id,
        model_id=prediction_data.model_id,
        input_data=prediction_data.input_data,
        status=PredictionStatus.PENDING,
        credits_spent=0
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    
    # Запуск асинхронной задачи
    task = execute_prediction.delay(
        prediction_id=prediction.id,
        model_id=prediction_data.model_id,
        user_id=current_user.id,
        input_data=prediction_data.input_data
    )
    
    return PredictionTaskResponse(
        task_id=task.id,
        prediction_id=prediction.id,
        status="pending",
        message="Prediction task created. Use GET /predictions/{prediction_id} to check status."
    )


@router.get("", response_model=PredictionList)
def list_predictions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Список предсказаний пользователя"""
    predictions = db.query(Prediction).filter(
        Prediction.user_id == current_user.id
    ).order_by(Prediction.created_at.desc()).all()
    
    return PredictionList(predictions=predictions, total=len(predictions))


@router.get("/{prediction_id}", response_model=PredictionResponse)
def get_prediction(
    prediction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение предсказания"""
    prediction = db.query(Prediction).filter(
        Prediction.id == prediction_id,
        Prediction.user_id == current_user.id
    ).first()
    
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    return prediction
