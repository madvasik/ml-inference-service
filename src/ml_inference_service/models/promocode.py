import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ml_inference_service.database import Base


class PromocodeType(str, enum.Enum):
    fixed_credits = "fixed_credits"
    percent_next_topup = "percent_next_topup"


class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    kind: Mapped[PromocodeType] = mapped_column(Enum(PromocodeType), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_activations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromocodeRedemption(Base):
    __tablename__ = "promocode_redemptions"
    __table_args__ = (UniqueConstraint("user_id", "promocode_id", name="uq_user_promocode"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    promocode_id: Mapped[int] = mapped_column(ForeignKey("promocodes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    promocode: Mapped["Promocode"] = relationship()
