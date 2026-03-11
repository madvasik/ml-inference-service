from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base
import enum


class PredictionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False, index=True)
    input_data = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    status = Column(Enum(PredictionStatus), default=PredictionStatus.PENDING, nullable=False)
    credits_spent = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="predictions")
    model = relationship("MLModel", backref="predictions")
