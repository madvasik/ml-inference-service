from pydantic_settings import BaseSettings, SettingsConfigDict
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
    
    # Redis
    redis_url: str = "redis://redis:6379/0"
    
    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    
    # Rate Limiting
    rate_limit_per_minute: int = 1000
    rate_limit_per_user_per_minute: int = 100
    
    # CORS
    cors_origins: str = "*"  # В production указать конкретные домены через запятую
    
    # File Upload
    max_upload_size_mb: int = 100  # Максимальный размер загружаемого файла в MB
    
    # Logging
    log_json_format: bool = False  # Использовать JSON формат для логирования
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )


settings = Settings()
