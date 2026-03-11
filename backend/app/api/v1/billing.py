from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_current_user
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.billing.service import get_balance, add_credits
from backend.app.models.transaction import Transaction
from backend.app.schemas.billing import BalanceResponse, TopUpRequest, TopUpResponse, TransactionResponse, TransactionList

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
    
    add_credits(db, current_user.id, topup_data.amount, f"Top-up: {topup_data.amount} credits")
    new_balance = get_balance(db, current_user.id)
    
    return TopUpResponse(
        credits=new_balance,
        message=f"Successfully added {topup_data.amount} credits"
    )


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
