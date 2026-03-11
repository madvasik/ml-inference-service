from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Billing
    prediction_cost: int = 10
    
    # Application
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    
    # ML Models
    ml_models_dir: str = "ml_models"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
