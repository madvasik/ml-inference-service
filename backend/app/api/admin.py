from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Payment, Prediction, Transaction, User
from backend.app.schemas import PaymentList, PredictionList, PredictionResponse, TransactionList, UserResponse
from backend.app.security import get_current_admin


router = APIRouter()


@router.get("/users", response_model=list[UserResponse])
def list_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    del current_user
    return db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, current_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    del current_user
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/predictions", response_model=PredictionList)
def list_all_predictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = Query(None),
    model_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    del current_user
    query = db.query(Prediction)
    if user_id is not None:
        query = query.filter(Prediction.user_id == user_id)
    if model_id is not None:
        query = query.filter(Prediction.model_id == model_id)
    total = query.count()
    predictions = query.order_by(desc(Prediction.created_at)).offset(skip).limit(limit).all()
    return PredictionList(predictions=predictions, total=total)


@router.get("/predictions/{prediction_id}", response_model=PredictionResponse)
def get_prediction(
    prediction_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    del current_user
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    return prediction


@router.get("/transactions", response_model=TransactionList)
def list_all_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    del current_user
    query = db.query(Transaction)
    if user_id is not None:
        query = query.filter(Transaction.user_id == user_id)
    total = query.count()
    transactions = query.order_by(desc(Transaction.created_at)).offset(skip).limit(limit).all()
    return TransactionList(transactions=transactions, total=total)


@router.get("/payments", response_model=PaymentList)
def list_all_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    del current_user
    query = db.query(Payment)
    if user_id is not None:
        query = query.filter(Payment.user_id == user_id)
    total = query.count()
    payments = query.order_by(desc(Payment.created_at)).offset(skip).limit(limit).all()
    return PaymentList(payments=payments, total=total)
