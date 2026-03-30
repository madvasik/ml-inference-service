from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BalanceResponse(BaseModel):
    balance_credits: int


class CreditTransactionItem(BaseModel):
    id: int
    amount: int
    kind: str
    created_at: datetime
    reference: dict | None = None

    model_config = {"from_attributes": True}


class MockTopupRequest(BaseModel):
    amount_money: Decimal = Field(..., gt=0)
    credits_to_grant: int = Field(..., gt=0)
    secret: str = Field(..., min_length=1)


class TopupResponse(BaseModel):
    payment_id: int
    status: str
    credits_granted: int
