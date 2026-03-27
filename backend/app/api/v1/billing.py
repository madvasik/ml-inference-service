from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_current_user
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.billing.service import get_balance
from backend.app.services.payment_service import confirm_payment, create_payment_intent, list_user_payments
from backend.app.models.transaction import Transaction
from backend.app.schemas.billing import (
    BalanceResponse,
    PaymentConfirmResponse,
    PaymentCreate,
    PaymentIntentResponse,
    PaymentList,
    TopUpRequest,
    TopUpResponse,
    TransactionList,
)

router = APIRouter()


@router.get("/balance", response_model=BalanceResponse)
def get_user_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение баланса пользователя"""
    credits = get_balance(db, current_user.id)
    return BalanceResponse(credits=credits)


@router.post("/topup", response_model=TopUpResponse)
def top_up_balance(
    topup_data: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Пополнение баланса"""
    if topup_data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )

    payment = create_payment_intent(db, current_user.id, topup_data.amount)
    confirmation = confirm_payment(db, payment.id, current_user.id)
    
    return TopUpResponse(
        credits=confirmation.credits,
        message=f"Successfully added {topup_data.amount} credits"
    )


@router.post("/payments", response_model=PaymentIntentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payment_data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )

    payment = create_payment_intent(db, current_user.id, payment_data.amount)
    return PaymentIntentResponse(
        payment_id=payment.id,
        status=payment.status,
        provider=payment.provider,
        amount=payment.amount,
    )


@router.post("/payments/{payment_id}/confirm", response_model=PaymentConfirmResponse)
def confirm_user_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        confirmation = confirm_payment(db, payment_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return PaymentConfirmResponse(
        payment=confirmation.payment,
        credits=confirmation.credits,
        message=f"Payment #{confirmation.payment.id} confirmed",
    )


@router.get("/payments", response_model=PaymentList)
def list_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    payments = list_user_payments(db, current_user.id)
    return PaymentList(payments=payments, total=len(payments))


@router.get("/transactions", response_model=TransactionList)
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Список транзакций пользователя"""
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(Transaction.created_at.desc()).all()
    
    return TransactionList(transactions=transactions, total=len(transactions))
