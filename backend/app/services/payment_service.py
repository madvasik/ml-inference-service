from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.billing.service import add_credits, get_balance
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.monitoring.metrics import payment_intents_total


@dataclass
class PaymentConfirmationResult:
    payment: Payment
    credits: int


def create_payment_intent(db: Session, user_id: int, amount: int, provider: str = "mock") -> Payment:
    payment = Payment(
        user_id=user_id,
        amount=amount,
        provider=provider,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.flush()
    payment.external_id = f"{provider}:{payment.id}"
    db.commit()
    db.refresh(payment)
    payment_intents_total.labels(status="created", provider=provider).inc()
    return payment


def confirm_payment(db: Session, payment_id: int, user_id: int) -> PaymentConfirmationResult:
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == user_id).with_for_update().first()
    if payment is None:
        raise ValueError("Payment not found")

    if payment.status == PaymentStatus.CONFIRMED:
        return PaymentConfirmationResult(payment=payment, credits=get_balance(db, user_id))

    if payment.status == PaymentStatus.FAILED:
        raise ValueError("Payment already failed")

    payment.status = PaymentStatus.CONFIRMED
    payment.confirmed_at = datetime.now(timezone.utc)
    add_credits(
        db,
        user_id=user_id,
        amount=payment.amount,
        payment=payment,
        description=f"Mock payment confirmation #{payment.id}",
        commit=False,
    )
    db.commit()
    db.refresh(payment)
    payment_intents_total.labels(status="confirmed", provider=payment.provider).inc()
    return PaymentConfirmationResult(payment=payment, credits=get_balance(db, user_id))


def list_user_payments(db: Session, user_id: int) -> list[Payment]:
    return db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).all()
