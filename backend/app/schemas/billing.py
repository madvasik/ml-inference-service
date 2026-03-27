from datetime import datetime
from pydantic import BaseModel, ConfigDict
from backend.app.models.payment import PaymentStatus
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
    prediction_id: int | None
    payment_id: int | None
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionList(BaseModel):
    transactions: list[TransactionResponse]
    total: int


class PaymentCreate(BaseModel):
    amount: int


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    provider: str
    status: PaymentStatus
    external_id: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentIntentResponse(BaseModel):
    payment_id: int
    status: PaymentStatus
    provider: str
    amount: int


class PaymentConfirmResponse(BaseModel):
    payment: PaymentResponse
    credits: int
    message: str


class PaymentList(BaseModel):
    payments: list[PaymentResponse]
    total: int
