from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MLModelBase(BaseModel):
    model_name: str

    model_config = ConfigDict(protected_namespaces=())


class MLModelCreate(MLModelBase):
    pass


class MLModelResponse(MLModelBase):
    id: int
    owner_id: int
    file_path: str
    model_type: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class MLModelList(BaseModel):
    models: list[MLModelResponse]
    total: int
