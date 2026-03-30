from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ml_inference_service.database import get_db
from ml_inference_service.models.user import User, UserRole
from ml_inference_service.schemas.auth import RegisterRequest, TokenResponse
from ml_inference_service.security import create_access_token, get_password_hash, verify_password

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=get_password_hash(body.password),
        role=UserRole.user,
        balance_credits=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, {"role": user.role.value})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(
    db: Annotated[Session, Depends(get_db)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(user.id, {"role": user.role.value})
    return TokenResponse(access_token=token)
