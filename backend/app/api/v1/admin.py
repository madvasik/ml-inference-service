from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from backend.app.api.deps import get_current_admin
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.models.prediction import Prediction
from backend.app.schemas.user import UserResponse
from backend.app.schemas.prediction import PredictionResponse, PredictionList

router = APIRouter()


@router.get("/users", response_model=list[UserResponse])
def list_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение списка всех пользователей (только для администраторов)"""
    users = db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение информации о пользователе по ID (только для администраторов)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get("/predictions", response_model=PredictionList)
def list_all_predictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = Query(None, description="Фильтр по user_id"),
    model_id: Optional[int] = Query(None, description="Фильтр по model_id"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение списка всех предсказаний (только для администраторов)"""
    query = db.query(Prediction)
    
    if user_id:
        query = query.filter(Prediction.user_id == user_id)
    if model_id:
        query = query.filter(Prediction.model_id == model_id)
    
    total = query.count()
    predictions = query.order_by(desc(Prediction.created_at)).offset(skip).limit(limit).all()
    
    return PredictionList(predictions=predictions, total=total)


@router.get("/predictions/{prediction_id}", response_model=PredictionResponse)
def get_prediction(
    prediction_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение информации о предсказании по ID (только для администраторов)"""
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    return prediction
