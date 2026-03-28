from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.billing import ensure_balance
from backend.app.db import get_db
from backend.app.models import LoyaltyTier, User, UserRole
from backend.app.schemas import RefreshTokenRequest, Token, UserLogin, UserRegister
from backend.app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role=UserRole.USER,
        loyalty_tier=LoyaltyTier.NONE,
        loyalty_discount_percent=0,
    )
    db.add(user)
    db.flush()
    ensure_balance(db, user.id)
    db.commit()
    db.refresh(user)

    return Token(
        access_token=create_access_token(data={"sub": str(user.id), "email": user.email}),
        refresh_token=create_refresh_token(data={"sub": str(user.id), "email": user.email}),
        token_type="bearer",
    )


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if user is None or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(
        access_token=create_access_token(data={"sub": str(user.id), "email": user.email}),
        refresh_token=create_refresh_token(data={"sub": str(user.id), "email": user.email}),
        token_type="bearer",
    )


@router.post("/refresh", response_model=Token)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    payload = decode_token(request.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_type: str | None = payload.get("type")
    user_id: str | None = payload.get("sub")
    if token_type != "refresh" or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == parsed_user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(
        access_token=create_access_token(data={"sub": str(user.id), "email": user.email}),
        refresh_token=create_refresh_token(data={"sub": str(user.id), "email": user.email}),
        token_type="bearer",
    )
