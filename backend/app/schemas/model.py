from datetime import datetime
from pydantic import BaseModel


class MLModelBase(BaseModel):
    model_name: str


class MLModelCreate(MLModelBase):
    pass


class MLModelResponse(MLModelBase):
    id: int
    owner_id: int
    file_path: str
    model_type: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class MLModelList(BaseModel):
    models: list[MLModelResponse]
    total: int
