from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict

from backend.app.models import PredictionStatus


class PredictionCreate(BaseModel):
    model_id: int
    input_data: Dict[str, Any]

    model_config = ConfigDict(protected_namespaces=())


class PredictionResponse(BaseModel):
    id: int
    user_id: int
    model_id: int
    input_data: Dict[str, Any]
    result: Dict[str, Any] | None
    status: PredictionStatus
    task_id: str | None
    base_cost: int
    discount_percent: int
    discount_amount: int
    credits_spent: int
    completed_at: datetime | None
    failure_reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class PredictionList(BaseModel):
    predictions: list[PredictionResponse]
    total: int


class PredictionTaskResponse(BaseModel):
    task_id: str
    prediction_id: int
    status: str
    message: str

    model_config = ConfigDict(protected_namespaces=())
