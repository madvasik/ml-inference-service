from sqlalchemy import Boolean, Column, DateTime, Enum, Integer
from sqlalchemy.sql import func

from backend.app.db.base import Base
from backend.app.domain.models.user import LoyaltyTier


class LoyaltyTierRule(Base):
    __tablename__ = "loyalty_tier_rules"

    id = Column(Integer, primary_key=True, index=True)
    tier = Column(Enum(LoyaltyTier), nullable=False, unique=True)
    monthly_threshold = Column(Integer, nullable=False)
    discount_percent = Column(Integer, nullable=False)
    priority = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
