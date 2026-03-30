from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ML Inference API"
    debug: bool = False

    database_url: str = "postgresql://postgres:postgres@localhost:5432/ml_inference_service"
    jwt_secret_key: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    models_storage_dir: str = "/tmp/ml_models"
    max_upload_bytes: int = 50 * 1024 * 1024

    mock_topup_secret: str = "dev-mock-topup-secret"
    prediction_cost_credits: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
