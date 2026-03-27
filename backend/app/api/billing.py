from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.billing import create_payment, get_balance, list_user_payments
from backend.app.db import get_db
from backend.app.models import Transaction, User
from backend.app.schemas import BalanceResponse, PaymentCreate, PaymentCreateResponse, PaymentList, TransactionList
from backend.app.security import get_current_user


router = APIRouter()


@router.get("/balance", response_model=BalanceResponse)
def get_user_balance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return BalanceResponse(credits=get_balance(db, current_user.id))


@router.post("/payments", response_model=PaymentCreateResponse)
def create_user_payment(
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payment_data.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")

    payment_result = create_payment(db, current_user.id, payment_data.amount)
    return PaymentCreateResponse(
        payment=payment_result.payment,
        credits=payment_result.credits,
        message=f"Successfully added {payment_data.amount} credits",
    )


@router.get("/payments", response_model=PaymentList)
def list_payments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payments = list_user_payments(db, current_user.id)
    return PaymentList(payments=payments, total=len(payments))


@router.get("/transactions", response_model=TransactionList)
def list_transactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return TransactionList(transactions=transactions, total=len(transactions))
