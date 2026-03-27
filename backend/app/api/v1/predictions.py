from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.billing.service import build_prediction_cost_snapshot, get_balance
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.models.ml_model import MLModel
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.services.loyalty_service import get_loyalty_snapshot
from backend.app.schemas.prediction import PredictionCreate, PredictionResponse, PredictionList, PredictionTaskResponse
from backend.app.tasks.prediction_tasks import execute_prediction
from backend.app.config import settings

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
    loyalty_snapshot = get_loyalty_snapshot(current_user)
    discount_amount, final_cost = build_prediction_cost_snapshot(
        settings.prediction_cost,
        loyalty_snapshot.discount_percent,
    )
    balance = get_balance(db, current_user.id)
    if balance < final_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Required: {final_cost}, Available: {balance}"
        )

    # Создание записи предсказания
    prediction = Prediction(
        user_id=current_user.id,
        model_id=prediction_data.model_id,
        input_data=prediction_data.input_data,
        status=PredictionStatus.PENDING,
        base_cost=settings.prediction_cost,
        discount_percent=loyalty_snapshot.discount_percent,
        discount_amount=discount_amount,
        credits_spent=final_cost,
        failure_reason=None,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    try:
        task = execute_prediction.delay(prediction_id=prediction.id)
        prediction.task_id = task.id
        db.commit()
        db.refresh(prediction)
    except Exception:
        prediction.status = PredictionStatus.FAILED
        prediction.failure_reason = "queue_unavailable"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction queue is unavailable. Please try again later.",
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
