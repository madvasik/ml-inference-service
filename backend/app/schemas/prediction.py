from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel
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

    class Config:
        from_attributes = True


class PredictionList(BaseModel):
    predictions: list[PredictionResponse]
    total: int
