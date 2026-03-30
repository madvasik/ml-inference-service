from sqlalchemy.orm import Session

from ml_inference_service.config import get_settings
from ml_inference_service.models.credit import CreditTransaction, TransactionKind
from ml_inference_service.models.user import User

settings = get_settings()


class InsufficientCreditsError(Exception):
    pass


def debit_prediction_if_possible(
    db: Session,
    *,
    user_id: int,
    job_id: int,
    cost: int | None = None,
) -> CreditTransaction:
    """Idempotent debit for a successful prediction job. Raises InsufficientCreditsError."""
    cost = cost if cost is not None else settings.prediction_cost_credits
    idempotency_key = f"prediction_job:{job_id}:debit"
    existing = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing is not None:
        return existing

    user = db.query(User).filter(User.id == user_id).with_for_update().one()
    if user.balance_credits < cost:
        raise InsufficientCreditsError()
    user.balance_credits -= cost
    tx = CreditTransaction(
        user_id=user_id,
        amount=-cost,
        kind=TransactionKind.debit_prediction,
        idempotency_key=idempotency_key,
        reference={"job_id": job_id},
    )
    db.add(tx)
    db.flush()
    return tx


def credit_topup(
    db: Session,
    *,
    user_id: int,
    credits: int,
    payment_id: int | None = None,
    idempotency_key: str | None = None,
) -> CreditTransaction:
    if idempotency_key:
        existing = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.idempotency_key == idempotency_key)
            .first()
        )
        if existing is not None:
            return existing

    user = db.query(User).filter(User.id == user_id).with_for_update().one()
    user.balance_credits += credits
    ref: dict = {}
    if payment_id is not None:
        ref["payment_id"] = payment_id
    tx = CreditTransaction(
        user_id=user_id,
        amount=credits,
        kind=TransactionKind.credit_topup,
        idempotency_key=idempotency_key,
        reference=ref or None,
    )
    db.add(tx)
    db.flush()
    return tx


def credit_promo(
    db: Session,
    *,
    user_id: int,
    credits: int,
    promocode_id: int,
    idempotency_key: str,
) -> CreditTransaction:
    existing = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing is not None:
        return existing

    user = db.query(User).filter(User.id == user_id).with_for_update().one()
    user.balance_credits += credits
    tx = CreditTransaction(
        user_id=user_id,
        amount=credits,
        kind=TransactionKind.credit_promo,
        idempotency_key=idempotency_key,
        reference={"promocode_id": promocode_id},
    )
    db.add(tx)
    db.flush()
    return tx
