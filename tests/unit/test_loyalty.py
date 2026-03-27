from datetime import datetime, timezone

from backend.app.billing import build_prediction_cost_snapshot
from backend.app.loyalty import ensure_default_loyalty_rules, recalculate_loyalty_tiers
from backend.app.models import LoyaltyTier, Prediction, PredictionStatus


def test_default_loyalty_rules_are_seeded_once(db_session):
    first = ensure_default_loyalty_rules(db_session)
    second = ensure_default_loyalty_rules(db_session)

    assert len(first) == 3
    assert len(second) == 3


def test_monthly_loyalty_recalculation_uses_previous_month_activity(db_session, test_user, test_ml_model):
    ensure_default_loyalty_rules(db_session)
    completed_at = datetime(2026, 2, 20, tzinfo=timezone.utc)
    for idx in range(210):
        db_session.add(
            Prediction(
                user_id=test_user.id,
                model_id=test_ml_model.id,
                input_data={"feature": idx},
                status=PredictionStatus.COMPLETED,
                base_cost=10,
                discount_percent=0,
                discount_amount=0,
                credits_spent=10,
                completed_at=completed_at,
            )
        )
    db_session.commit()

    recalculate_loyalty_tiers(db_session, reference_time=datetime(2026, 3, 2, tzinfo=timezone.utc))
    db_session.refresh(test_user)

    assert test_user.loyalty_tier == LoyaltyTier.SILVER
    assert test_user.loyalty_discount_percent == 10


def test_prediction_cost_snapshot_applies_discount():
    discount_amount, final_cost = build_prediction_cost_snapshot(10, 20)

    assert discount_amount == 2
    assert final_cost == 8

