from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ml_inference_service.models.promocode import Promocode, PromocodeRedemption, PromocodeType
from ml_inference_service.models.user import User
from ml_inference_service.services import billing


class PromocodeInvalidError(Exception):
    pass


class PromocodeAlreadyUsedError(Exception):
    pass


def activate_promocode(db: Session, *, user_id: int, code: str) -> tuple[str, int | None, int | None]:
    """
    Apply promocode for user. Returns (message, credits_granted, discount_percent).
    Raises PromocodeInvalidError or PromocodeAlreadyUsedError.
    """
    normalized = code.strip().upper()
    promo = db.query(Promocode).filter(func.upper(Promocode.code) == normalized).with_for_update().first()
    if promo is None:
        raise PromocodeInvalidError("Unknown promocode")

    now = datetime.now(timezone.utc)
    if promo.expires_at is not None:
        exp = promo.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            raise PromocodeInvalidError("Promocode expired")

    if promo.max_activations is not None and promo.activations_count >= promo.max_activations:
        raise PromocodeInvalidError("Promocode activation limit reached")

    redemption = PromocodeRedemption(user_id=user_id, promocode_id=promo.id)
    db.add(redemption)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise PromocodeAlreadyUsedError("You have already activated this promocode") from e  # noqa: TRY003

    promo.activations_count += 1

    credits_granted: int | None = None
    discount_percent: int | None = None

    if promo.kind == PromocodeType.fixed_credits:
        idem = f"promo:{promo.id}:user:{user_id}"
        billing.credit_promo(
            db,
            user_id=user_id,
            credits=promo.value,
            promocode_id=promo.id,
            idempotency_key=idem,
        )
        credits_granted = promo.value
        msg = f"Granted {promo.value} credits"
    else:
        user = db.query(User).filter(User.id == user_id).with_for_update().one()
        user.pending_topup_discount_percent = promo.value
        discount_percent = promo.value
        msg = f"Next top-up will receive {promo.value}% bonus credits"

    return msg, credits_granted, discount_percent
