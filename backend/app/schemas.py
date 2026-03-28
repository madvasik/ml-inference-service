from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr

from backend.app.models import LoyaltyTier, PaymentStatus, PredictionStatus, TransactionType, UserRole


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    loyalty_tier: LoyaltyTier
    loyalty_discount_percent: int
    loyalty_updated_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BalanceResponse(BaseModel):
    credits: int


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


class PaymentCreateResponse(BaseModel):
    payment: PaymentResponse
    credits: int
    message: str


class PaymentList(BaseModel):
    payments: list[PaymentResponse]
    total: int


class MLModelResponse(BaseModel):
    id: int
    owner_id: int
    model_name: str
    file_path: str
    model_type: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class MLModelList(BaseModel):
    models: list[MLModelResponse]
    total: int


class PredictionCreate(BaseModel):
    model_id: int
    input_data: dict[str, Any]

    model_config = ConfigDict(protected_namespaces=())


class PredictionResponse(BaseModel):
    id: int
    user_id: int
    model_id: int
    input_data: dict[str, Any]
    result: dict[str, Any] | None
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
