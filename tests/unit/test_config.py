import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_settings_rejects_placeholder_secret_key():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(database_url="sqlite:///tmp/test.db", secret_key="your-secret-key-change-in-production")


def test_settings_rejects_weak_initial_admin_password_when_debug_off():
    with pytest.raises(ValidationError, match="INITIAL_ADMIN_PASSWORD"):
        Settings(
            database_url="sqlite:///tmp/test.db",
            secret_key="this-is-a-secure-secret-key-for-tests",
            debug=False,
            initial_admin_email="admin@example.com",
            initial_admin_password="admin123",
        )


def test_settings_allows_weak_initial_admin_password_when_debug_on():
    settings = Settings(
        database_url="sqlite:///tmp/test.db",
        secret_key="this-is-a-secure-secret-key-for-tests",
        debug=True,
        initial_admin_email="admin@example.com",
        initial_admin_password="admin",
    )
    assert settings.initial_admin_password == "admin"


def test_settings_requires_complete_initial_admin_credentials():
    with pytest.raises(ValidationError, match="set together"):
        Settings(
            database_url="sqlite:///tmp/test.db",
            secret_key="this-is-a-secure-secret-key-for-tests",
            initial_admin_email="admin@example.com",
            initial_admin_password=None,
        )
