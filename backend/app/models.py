import enum

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
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


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class PredictionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


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


class Balance(Base):
    __tablename__ = "balances"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    credits = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="balance", uselist=False)

    __table_args__ = (UniqueConstraint("user_id", name="uq_balances_user_id"),)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    provider = Column(String, nullable=False, default="mock")
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    external_id = Column(String, nullable=True, unique=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="payments")


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    model_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    model_type = Column(String, nullable=True)
    feature_names = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner = relationship("User", backref="models")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False, index=True)
    input_data = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    status = Column(Enum(PredictionStatus), default=PredictionStatus.PENDING, nullable=False)
    task_id = Column(String, nullable=True, index=True)
    base_cost = Column(Integer, nullable=False, default=0)
    discount_percent = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)
    credits_spent = Column(Integer, nullable=False, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="predictions")
    model = relationship("MLModel", backref="predictions")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="transactions")
    prediction = relationship("Prediction", backref="transactions")
    payment = relationship("Payment", backref="transactions")

    __table_args__ = (
        UniqueConstraint("prediction_id", name="uq_transactions_prediction_id"),
        UniqueConstraint("payment_id", name="uq_transactions_payment_id"),
    )
