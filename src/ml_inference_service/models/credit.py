from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ml_inference_service.database import Base


class TransactionKind(str, enum.Enum):
    debit_prediction = "debit_prediction"
    credit_topup = "credit_topup"
    credit_promo = "credit_promo"
    adjustment = "adjustment"


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_credit_transactions_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[TransactionKind] = mapped_column(Enum(TransactionKind), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="credit_transactions")
