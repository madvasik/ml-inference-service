from typing import Any

from pydantic import BaseModel, Field


class MLModelCreateResponse(BaseModel):
    id: int
    name: str
    storage_path: str
    is_active: bool

    model_config = {"from_attributes": True}


class MLModelListItem(BaseModel):
    id: int
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class PredictRequest(BaseModel):
    """Input for sklearn predict: features as list of numbers (single row)."""

    model_id: int = Field(..., gt=0)
    features: list[float] = Field(..., min_length=1)


class PredictEnqueueResponse(BaseModel):
    job_id: int
    status: str


class JobStatusResponse(BaseModel):
    id: int
    status: str
    result: dict[str, Any] | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
