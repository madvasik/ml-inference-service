from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict
from backend.app.domain.models.user import LoyaltyTier, UserRole


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    role: UserRole
    loyalty_tier: LoyaltyTier
    loyalty_discount_percent: int
    loyalty_updated_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
