import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from backend.app.db import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class LoyaltyTier(str, enum.Enum):
    NONE = "none"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    loyalty_tier = Column(Enum(LoyaltyTier), default=LoyaltyTier.NONE, nullable=False)
    loyalty_discount_percent = Column(Integer, default=0, nullable=False)
    loyalty_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
