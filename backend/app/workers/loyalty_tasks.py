import logging

from backend.app.db.session import SessionLocal
from backend.app.services.loyalty_service import recalculate_loyalty_tiers
from backend.app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="loyalty.recalculate_monthly")
def recalculate_monthly_loyalty():
    db = SessionLocal()
    try:
        updated_users = recalculate_loyalty_tiers(db)
        logger.info("Recalculated loyalty tiers for %s users", updated_users)
        return {"updated_users": updated_users}
    finally:
        db.close()
