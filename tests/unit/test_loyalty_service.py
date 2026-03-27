from datetime import datetime, timezone

from backend.app.domain.models.prediction import Prediction, PredictionStatus
from backend.app.domain.models.user import LoyaltyTier
from backend.app.services.loyalty_service import ensure_default_loyalty_rules, recalculate_loyalty_tiers


def test_ensure_default_loyalty_rules_creates_seed_data(db_session):
    rules = ensure_default_loyalty_rules(db_session)

    assert len(rules) == 3
    assert {rule.tier for rule in rules} == {LoyaltyTier.BRONZE, LoyaltyTier.SILVER, LoyaltyTier.GOLD}


def test_recalculate_loyalty_tiers_updates_user_status(db_session, test_user, test_ml_model):
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
