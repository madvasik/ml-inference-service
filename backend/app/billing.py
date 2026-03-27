import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy.orm import Session

from backend.app.metrics import billing_transactions_total, payments_total
from backend.app.models import Balance, Payment, PaymentStatus, Prediction, Transaction, TransactionType


@dataclass
class PaymentResult:
    payment: Payment
    credits: int


def ensure_balance(db: Session, user_id: int) -> Tuple[Balance, bool]:
    balance = db.query(Balance).filter(Balance.user_id == user_id).first()
    created = False
    if not balance:
        balance = Balance(user_id=user_id, credits=0)
        db.add(balance)
        db.flush()
        created = True
    return balance, created


def get_balance(db: Session, user_id: int) -> int:
    balance, created = ensure_balance(db, user_id)
    if created:
        db.commit()
        db.refresh(balance)
    return balance.credits


def calculate_discount_amount(base_cost: int, discount_percent: int) -> int:
    if base_cost <= 0 or discount_percent <= 0:
        return 0
    raw_discount = math.ceil(base_cost * discount_percent / 100)
    return min(base_cost, raw_discount)


def build_prediction_cost_snapshot(base_cost: int, discount_percent: int) -> tuple[int, int]:
    discount_amount = calculate_discount_amount(base_cost, discount_percent)
    final_cost = max(0, base_cost - discount_amount)
    return discount_amount, final_cost


def get_prediction_debit_transaction(db: Session, prediction_id: int) -> Transaction | None:
    return db.query(Transaction).filter(Transaction.prediction_id == prediction_id).first()


def charge_prediction(
    db: Session,
    prediction: Prediction,
    description: str | None = None,
) -> tuple[bool, Transaction | None]:
    existing_transaction = get_prediction_debit_transaction(db, prediction.id)
    if existing_transaction is not None:
        return True, existing_transaction

    balance = db.query(Balance).filter(Balance.user_id == prediction.user_id).with_for_update().first()
    if not balance:
        balance = Balance(user_id=prediction.user_id, credits=0)
        db.add(balance)
        db.flush()

    if balance.credits < prediction.credits_spent:
        return False, None

    balance.credits -= prediction.credits_spent
    transaction = Transaction(
        user_id=prediction.user_id,
        amount=prediction.credits_spent,
        type=TransactionType.DEBIT,
        prediction_id=prediction.id,
        description=description or f"Prediction cost: {prediction.credits_spent} credits",
    )
    db.add(transaction)
    billing_transactions_total.labels(type="debit").inc()
    return True, transaction


def deduct_credits(db: Session, user_id: int, amount: int, description: str | None = None) -> bool:
    balance = db.query(Balance).filter(Balance.user_id == user_id).with_for_update().first()
    if not balance:
        balance = Balance(user_id=user_id, credits=0)
        db.add(balance)
        db.flush()

    if balance.credits < amount:
        return False

    balance.credits -= amount
    db.add(
        Transaction(
            user_id=user_id,
            amount=amount,
            type=TransactionType.DEBIT,
            description=description or f"Prediction cost: {amount} credits",
        )
    )
    db.commit()
    billing_transactions_total.labels(type="debit").inc()
    return True


def add_credits(
    db: Session,
    user_id: int,
    amount: int,
    description: str | None = None,
    payment: Payment | None = None,
    commit: bool = True,
) -> Transaction:
    balance = db.query(Balance).filter(Balance.user_id == user_id).with_for_update().first()
    if not balance:
        balance = Balance(user_id=user_id, credits=0)
        db.add(balance)
        db.flush()

    balance.credits += amount

    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        type=TransactionType.CREDIT,
        payment_id=payment.id if payment else None,
        description=description or f"Top-up: {amount} credits",
    )
    db.add(transaction)
    if commit:
        db.commit()
    billing_transactions_total.labels(type="credit").inc()
    return transaction


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
