from typing import Any

from pydantic import field_validator, model_validator
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
    database_url: str

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    prediction_cost: int = 10

    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    ml_models_dir: str = "var/ml_models"

    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    celery_task_always_eager: bool = False
    rate_limit_storage_url: str | None = None

    rate_limit_per_minute: int = 1000
    rate_limit_per_user_per_minute: int = 100

    trusted_proxy_headers: bool = False

    prometheus_multiproc_dir: str | None = None

    prometheus_scrape_token: str | None = None

    cors_origins: str = "*"
    max_upload_size_mb: int = 100
    log_json_format: bool = False

    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
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

    @field_validator("initial_admin_email", "initial_admin_password", mode="before")
    @classmethod
    def normalize_optional_admin_credentials(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        insecure_values = {
            "your-secret-key-change-in-production",
            "changeme",
            "change-me",
            "secret",
            "default-secret-key",
        }
        if len(value) < 32 or value in insecure_values:
            raise ValueError("SECRET_KEY must be at least 32 characters long and must not use a known placeholder")
        return value

    @model_validator(mode="after")
    def validate_initial_admin_credentials(self) -> "Settings":
        if bool(self.initial_admin_email) != bool(self.initial_admin_password):
            raise ValueError("INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set together")
        pwd = self.initial_admin_password
        if pwd is None:
            return self
        if self.debug:
            if not pwd.strip():
                raise ValueError("INITIAL_ADMIN_PASSWORD cannot be empty")
            return self
        weak_passwords = {"admin123", "password", "admin", "changeme"}
        if len(pwd) < 12 or pwd in weak_passwords:
            raise ValueError(
                "INITIAL_ADMIN_PASSWORD must be at least 12 characters long and not use a common default "
                "(or set DEBUG=True for local weak passwords)"
            )
        return self


settings = Settings()
