from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from backend.app.database.session import get_db
from backend.app.models.prediction import Prediction
from backend.app.monitoring.metrics import active_users

router = APIRouter()


@router.post("/update-active-users")
def update_active_users_metric(db: Session = Depends(get_db)):
    """
    Обновление метрики активных пользователей
    Считает количество уникальных пользователей, создавших предсказания за последние 15 минут
    """
    # Время 15 минут назад
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    
    # Подсчет уникальных пользователей с предсказаниями за последние 15 минут
    unique_users = db.query(func.count(func.distinct(Prediction.user_id))).filter(
        Prediction.created_at >= cutoff_time
    ).scalar() or 0
    
    # Обновляем метрику
    active_users.set(unique_users)
    
    return {"active_users": unique_users, "updated_at": datetime.now(timezone.utc).isoformat()}
