import asyncio
import logging
import json

from tests.helpers import auth_headers

from backend.app import db as db_module
from backend.app.config import Settings
from backend.app.main import general_exception_handler
from backend.app.log_config import JSONFormatter, setup_logging


def test_root_and_health_endpoints(client):
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert root_response.json()["message"] == "ML Inference Service API"

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "healthy"


def test_health_endpoint_reports_database_failure(client, monkeypatch):
    monkeypatch.setattr(db_module, "probe_database_health", lambda: ("error", "unknown", []))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["components"]["database"] == "error"


def test_metrics_endpoint_is_available(client, access_token_for, admin_user):
    response = client.get("/metrics", headers=auth_headers(access_token_for(admin_user)))

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "prediction_requests_total" in response.text


def test_openapi_schema_exposes_core_endpoints(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/models/upload" in paths
    assert "/api/v1/predictions" in paths
    assert "/api/v1/billing/payments" in paths


def test_setup_logging_reuses_single_project_handler():
    root_logger = logging.getLogger()
    before = len([handler for handler in root_logger.handlers if getattr(handler, "_ml_service_handler", False)])

    setup_logging(debug=False, json_format=False)
    setup_logging(debug=True, json_format=True)

    after = [handler for handler in root_logger.handlers if getattr(handler, "_ml_service_handler", False)]
    assert len(after) == max(1, before)


def test_json_formatter_outputs_expected_fields():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )

    payload = formatter.format(record)

    assert '"logger": "test.logger"' in payload
    assert '"message": "hello"' in payload


def test_debug_defaults_to_false():
    assert Settings.model_fields["debug"].default is False


def test_general_exception_handler_hides_exception_details():
    response = asyncio.run(
        general_exception_handler(
            request=None,
            exc=RuntimeError("database password leaked"),
        )
    )

    assert response.status_code == 500
    assert json.loads(response.body) == {"detail": "Internal server error"}
