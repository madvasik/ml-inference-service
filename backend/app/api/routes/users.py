from fastapi import APIRouter, Depends
from backend.app.models import User
from backend.app.schemas.user import UserResponse
from backend.app.security import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return current_user
