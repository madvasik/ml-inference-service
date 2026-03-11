from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_current_user
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.models.ml_model import MLModel
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.services.model_loader import load_model
from backend.app.services.ml_service import predict
from backend.app.billing.service import deduct_credits, get_balance
from backend.app.schemas.prediction import PredictionCreate, PredictionResponse, PredictionList
from backend.app.config import settings

router = APIRouter()


@router.post("", response_model=PredictionResponse, status_code=status.HTTP_201_CREATED)
def create_prediction(
    prediction_data: PredictionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание предсказания"""
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
    
    # Проверка баланса
    balance = get_balance(db, current_user.id)
    if balance < settings.prediction_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Required: {settings.prediction_cost}, Available: {balance}"
        )
    
    # Создание записи предсказания
    prediction = Prediction(
        user_id=current_user.id,
        model_id=prediction_data.model_id,
        input_data=prediction_data.input_data,
        status=PredictionStatus.PENDING,
        credits_spent=0
    )
    db.add(prediction)
    db.flush()
    
    try:
        # Загрузка модели
        ml_model = load_model(model.file_path)
        
        # Выполнение предсказания
        result = predict(ml_model, prediction_data.input_data)
        
        # Списание кредитов (атомарно)
        if not deduct_credits(db, current_user.id, settings.prediction_cost, f"Prediction #{prediction.id}"):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Failed to deduct credits"
            )
        
        # Обновление предсказания
        prediction.result = result
        prediction.status = PredictionStatus.COMPLETED
        prediction.credits_spent = settings.prediction_cost
        db.commit()
        db.refresh(prediction)
        
        return prediction
        
    except Exception as e:
        # Обновление статуса на FAILED
        prediction.status = PredictionStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
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
