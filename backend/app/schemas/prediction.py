from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, ConfigDict
from backend.app.models.prediction import PredictionStatus


class PredictionCreate(BaseModel):
    model_id: int
    input_data: Dict[str, Any]


class PredictionResponse(BaseModel):
    id: int
    user_id: int
    model_id: int
    input_data: Dict[str, Any]
    result: Dict[str, Any] | None
    status: PredictionStatus
    credits_spent: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionList(BaseModel):
    predictions: list[PredictionResponse]
    total: int


class PredictionTaskResponse(BaseModel):
    """Ответ при создании асинхронного предсказания"""
    task_id: str
    prediction_id: int
    status: str
    message: str
