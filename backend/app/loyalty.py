from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.metrics import loyalty_users_total
from backend.app.models import LoyaltyTier, LoyaltyTierRule, Prediction, PredictionStatus, User


DEFAULT_TIER_RULES = (
    (LoyaltyTier.BRONZE, 50, 5, 1),
    (LoyaltyTier.SILVER, 200, 10, 2),
    (LoyaltyTier.GOLD, 500, 20, 3),
)


@dataclass
class LoyaltySnapshot:
    tier: LoyaltyTier
    discount_percent: int


def ensure_default_loyalty_rules(db: Session) -> list[LoyaltyTierRule]:
    rules = db.query(LoyaltyTierRule).order_by(LoyaltyTierRule.priority.asc()).all()
    if rules:
        return rules

    for tier, threshold, discount_percent, priority in DEFAULT_TIER_RULES:
        db.add(
            LoyaltyTierRule(
                tier=tier,
                monthly_threshold=threshold,
                discount_percent=discount_percent,
                priority=priority,
                is_active=True,
            )
        )
    db.commit()
    return db.query(LoyaltyTierRule).order_by(LoyaltyTierRule.priority.asc()).all()


def get_loyalty_snapshot(user: User) -> LoyaltySnapshot:
    return LoyaltySnapshot(
        tier=user.loyalty_tier or LoyaltyTier.NONE,
        discount_percent=user.loyalty_discount_percent or 0,
    )


def resolve_tier_for_count(rules: list[LoyaltyTierRule], prediction_count: int) -> LoyaltySnapshot:
    matched_rule = None
    for rule in sorted((rule for rule in rules if rule.is_active), key=lambda item: item.monthly_threshold):
        if prediction_count >= rule.monthly_threshold:
            matched_rule = rule
    if matched_rule is None:
        return LoyaltySnapshot(tier=LoyaltyTier.NONE, discount_percent=0)
    return LoyaltySnapshot(tier=matched_rule.tier, discount_percent=matched_rule.discount_percent)


def _previous_month_range(reference_time: datetime | None = None) -> tuple[datetime, datetime]:
    now = reference_time or datetime.now(timezone.utc)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_end = current_month_start
    previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    return previous_month_start, previous_month_end


def recalculate_loyalty_tiers(db: Session, reference_time: datetime | None = None) -> int:
    rules = ensure_default_loyalty_rules(db)
    period_start, period_end = _previous_month_range(reference_time)

    stats = dict(
        db.query(Prediction.user_id, func.count(Prediction.id))
        .filter(
            Prediction.status == PredictionStatus.COMPLETED,
            Prediction.completed_at >= period_start,
            Prediction.completed_at < period_end,
        )
        .group_by(Prediction.user_id)
        .all()
    )

    users = db.query(User).all()
    for user in users:
        snapshot = resolve_tier_for_count(rules, stats.get(user.id, 0))
        user.loyalty_tier = snapshot.tier
        user.loyalty_discount_percent = snapshot.discount_percent
        user.loyalty_updated_at = datetime.now(timezone.utc)

    db.commit()
    refresh_loyalty_metrics(db)
    return len(users)


def refresh_loyalty_metrics(db: Session) -> None:
    for tier in LoyaltyTier:
        count = db.query(func.count(User.id)).filter(User.loyalty_tier == tier).scalar() or 0
        loyalty_users_total.labels(tier=tier.value).set(count)
