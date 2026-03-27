import math
from typing import Tuple

from sqlalchemy.orm import Session

from backend.app.models.balance import Balance
from backend.app.models.payment import Payment
from backend.app.models.prediction import Prediction
from backend.app.models.transaction import Transaction, TransactionType
from backend.app.monitoring.metrics import billing_transactions_total


def ensure_balance(db: Session, user_id: int) -> Tuple[Balance, bool]:
    """Возвращает баланс пользователя и флаг его создания."""
    balance = db.query(Balance).filter(Balance.user_id == user_id).first()
    created = False
    if not balance:
        balance = Balance(user_id=user_id, credits=0)
        db.add(balance)
        db.flush()
        created = True
    return balance, created


def get_balance(db: Session, user_id: int) -> int:
    """Получение текущего баланса пользователя."""
    balance, created = ensure_balance(db, user_id)
    if created:
        db.commit()
        db.refresh(balance)
    return balance.credits


def calculate_discount_amount(base_cost: int, discount_percent: int) -> int:
    """Расчет скидки в кредитах с округлением в пользу пользователя."""
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
    """Списание кредитов за предсказание без коммита."""
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
        description=description or f"Prediction cost: {prediction.credits_spent} credits"
    )
    db.add(transaction)
    billing_transactions_total.labels(type="debit").inc()
    return True, transaction


def deduct_credits(db: Session, user_id: int, amount: int, description: str | None = None) -> bool:
    """Совместимый helper для точечного списания кредитов с commit."""
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
    """Пополнение баланса без коммита."""
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
        description=description or f"Top-up: {amount} credits"
    )
    db.add(transaction)
    if commit:
        db.commit()
    billing_transactions_total.labels(type="credit").inc()
    return transaction
