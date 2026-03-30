from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ml_inference_service.database import get_db
from ml_inference_service.deps import get_current_user
from ml_inference_service.models.user import User
from ml_inference_service.schemas.user import UserPublic, UserUpdate
from ml_inference_service.security import get_password_hash

router = APIRouter()


@router.get("/me", response_model=UserPublic)
def read_me(current: Annotated[User, Depends(get_current_user)]) -> User:
    return current


@router.patch("/me", response_model=UserPublic)
def update_me(
    body: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> User:
    if body.email is not None:
        other = db.query(User).filter(User.email == body.email, User.id != current.id).first()
        if other:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email taken")
        current.email = body.email
    if body.password is not None:
        current.password_hash = get_password_hash(body.password)
    db.add(current)
    db.commit()
    db.refresh(current)
    return current
