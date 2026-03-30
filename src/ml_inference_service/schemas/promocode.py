from datetime import datetime

from pydantic import BaseModel, Field


class PromocodeActivateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)


class PromocodeActivateResponse(BaseModel):
    message: str
    credits_granted: int | None = None
    discount_percent_next_topup: int | None = None


class PromocodeCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    kind: str = Field(..., pattern="^(fixed_credits|percent_next_topup)$")
    value: int = Field(..., gt=0)
    expires_at: datetime | None = None
    max_activations: int | None = Field(default=None, gt=0)


class PromocodeCreateResponse(BaseModel):
    id: int
    code: str

    model_config = {"from_attributes": True}
