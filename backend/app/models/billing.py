import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.app.db import Base


class Balance(Base):
    __tablename__ = "balances"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    credits = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="balance", uselist=False)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_balances_user_id"),
    )


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


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


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"


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
