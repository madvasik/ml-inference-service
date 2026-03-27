from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_boolish(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
    return value


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
    celery_task_always_eager: bool = False
    
    # Rate Limiting
    rate_limit_per_minute: int = 1000
    rate_limit_per_user_per_minute: int = 100
    
    # CORS
    cors_origins: str = "*"  # В production указать конкретные домены через запятую
    
    # File Upload
    max_upload_size_mb: int = 100  # Максимальный размер загружаемого файла в MB
    
    # Logging
    log_json_format: bool = False  # Использовать JSON формат для логирования

    # Bootstrap admin
    initial_admin_email: Optional[str] = None
    initial_admin_password: Optional[str] = None
    initial_admin_credits: int = 10000
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("debug", "log_json_format", "celery_task_always_eager", mode="before")
    @classmethod
    def normalize_boolish(cls, value: Any) -> Any:
        return _parse_boolish(value)


settings = Settings()
