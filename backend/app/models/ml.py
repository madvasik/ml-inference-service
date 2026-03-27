import enum

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.app.db import Base


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    model_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    model_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner = relationship("User", backref="models")


class PredictionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
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
