from datetime import datetime
from pydantic import BaseModel, ConfigDict
from backend.app.models.transaction import TransactionType


class BalanceResponse(BaseModel):
    credits: int


class TopUpRequest(BaseModel):
    amount: int


class TopUpResponse(BaseModel):
    credits: int
    message: str


class TransactionResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    type: TransactionType
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionList(BaseModel):
    transactions: list[TransactionResponse]
    total: int
