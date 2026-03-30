from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ml_inference_service.config import get_settings
from ml_inference_service.database import get_db
from ml_inference_service.deps import get_current_user
from ml_inference_service.models.credit import CreditTransaction
from ml_inference_service.models.payment import Payment, PaymentStatus
from ml_inference_service.models.user import User
from ml_inference_service.schemas.billing import BalanceResponse, CreditTransactionItem, MockTopupRequest, TopupResponse
from ml_inference_service.services import billing as billing_service

router = APIRouter()
settings = get_settings()


@router.get("/balance", response_model=BalanceResponse)
def get_balance(current: Annotated[User, Depends(get_current_user)]) -> BalanceResponse:
    return BalanceResponse(balance_credits=current.balance_credits)


@router.get("/transactions", response_model=list[CreditTransactionItem])
def list_transactions(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    limit: int = 100,
) -> list[CreditTransaction]:
    q = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == current.id)
        .order_by(CreditTransaction.id.desc())
        .limit(min(limit, 500))
    )
    return list(q.all())


@router.post("/mock-topup", response_model=TopupResponse)
def mock_topup(
    body: MockTopupRequest,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> TopupResponse:
    if body.secret != settings.mock_topup_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")

    base_credits = body.credits_to_grant
    user = db.query(User).filter(User.id == current.id).with_for_update().one()
    bonus = 0
    if user.pending_topup_discount_percent:
        pct = user.pending_topup_discount_percent
        bonus = int(base_credits * pct / 100)
        user.pending_topup_discount_percent = None

    total_credits = base_credits + bonus
    payment = Payment(
        user_id=user.id,
        external_id=None,
        amount_money=Decimal(str(body.amount_money)),
        credits_granted=total_credits,
        status=PaymentStatus.completed,
    )
    db.add(payment)
    db.flush()

    idem = f"mock_payment:{payment.id}"
    billing_service.credit_topup(
        db,
        user_id=user.id,
        credits=total_credits,
        payment_id=payment.id,
        idempotency_key=idem,
    )
    db.commit()
    db.refresh(payment)
    return TopupResponse(
        payment_id=payment.id,
        status=payment.status.value,
        credits_granted=total_credits,
    )
