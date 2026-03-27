from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Balance(Base):
    __tablename__ = "balances"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    credits = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="balance", uselist=False)

    __table_args__ = (
        UniqueConstraint('user_id', name='uq_balances_user_id'),
    )
