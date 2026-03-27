import pytest

from backend.app.config import Settings


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("release", False),
        ("production", False),
        ("true", True),
        ("false", False),
        ("debug", True),
    ],
)
def test_settings_parses_boolish_values(raw_value, expected):
    settings = Settings(
        database_url="sqlite:///./test.db",
        secret_key="test-secret",
        debug=raw_value,
        log_json_format=raw_value,
    )

    assert settings.debug is expected
    assert settings.log_json_format is expected
