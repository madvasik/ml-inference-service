from sqlalchemy.orm import Session

from backend.app.auth.security import get_password_hash
from backend.app.billing.service import add_credits, ensure_balance
from backend.app.core.config import settings
from backend.app.domain.models.user import LoyaltyTier, User, UserRole


def ensure_initial_admin(db: Session) -> User | None:
    if not settings.initial_admin_email or not settings.initial_admin_password:
        return None

    admin = db.query(User).filter(User.email == settings.initial_admin_email).first()
    if admin is not None:
        return admin

    admin = User(
        email=settings.initial_admin_email,
        password_hash=get_password_hash(settings.initial_admin_password),
        role=UserRole.ADMIN,
        loyalty_tier=LoyaltyTier.NONE,
        loyalty_discount_percent=0,
    )
    db.add(admin)
    db.flush()
    ensure_balance(db, admin.id)
    add_credits(db, admin.id, settings.initial_admin_credits, "Initial admin credits")
    db.commit()
    db.refresh(admin)
    return admin
