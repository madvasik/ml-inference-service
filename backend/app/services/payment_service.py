from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.billing.service import add_credits, get_balance
from backend.app.domain.models.payment import Payment, PaymentStatus
from backend.app.observability.metrics import payments_total


@dataclass
class PaymentResult:
    payment: Payment
    credits: int


def create_payment(db: Session, user_id: int, amount: int, provider: str = "mock") -> PaymentResult:
    payment = Payment(
        user_id=user_id,
        amount=amount,
        provider=provider,
        status=PaymentStatus.CONFIRMED,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.flush()
    payment.external_id = f"{provider}:{payment.id}"
    add_credits(
        db,
        user_id=user_id,
        amount=payment.amount,
        payment=payment,
        description=f"Mock payment #{payment.id}",
        commit=False,
    )
    db.commit()
    db.refresh(payment)
    payments_total.labels(status=payment.status.value, provider=payment.provider).inc()
    return PaymentResult(payment=payment, credits=get_balance(db, user_id))


def list_user_payments(db: Session, user_id: int) -> list[Payment]:
    return db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).all()
