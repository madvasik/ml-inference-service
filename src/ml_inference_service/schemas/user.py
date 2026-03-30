from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    role: str
    balance_credits: int

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
