"""E2e tests for health, metrics, monitoring stack, and dashboard surfaces."""
from __future__ import annotations

import os

import pytest
import requests


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000").rstrip("/")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501").rstrip("/")


def _request(method: str, path: str, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)


@pytest.mark.e2e
def test_live_health_returns_healthy():
    resp = _request("GET", "/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["components"]["database"] == "ok"
    assert body["components"]["schema"] == "ok"


@pytest.mark.e2e
def test_live_root_endpoint():
    resp = _request("GET", "/")
    assert resp.status_code == 200
    assert resp.json()["version"] == "1.0.0"


@pytest.mark.e2e
def test_live_metrics_endpoint_exposes_counters():
    admin_email = os.getenv("E2E_ADMIN_EMAIL")
    admin_password = os.getenv("E2E_ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        pytest.skip("Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD to authenticate GET /metrics")
    login = _request(
        "POST",
        "/api/v1/auth/login",
        json={"email": admin_email, "password": admin_password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    resp = _request("GET", "/metrics", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.text
    assert "prediction_requests_total" in body
    assert "billing_transactions_total" in body
    assert "payments_total" in body
    assert "active_users" in body
    assert "loyalty_users_total" in body


@pytest.mark.e2e
def test_live_docs_and_openapi():
    docs_response = _request("GET", "/docs")
    assert docs_response.status_code == 200
    assert "Swagger UI" in docs_response.text

    openapi_response = _request("GET", "/openapi.json")
    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/predictions" in paths
    assert "/api/v1/billing/payments" in paths


@pytest.mark.e2e
def test_live_monitoring_stack_is_wired():
    admin_email = os.getenv("E2E_ADMIN_EMAIL")
    admin_password = os.getenv("E2E_ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        pytest.skip("Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD to authenticate GET /metrics")
    login = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": admin_email, "password": admin_password},
        timeout=10,
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    backend_metrics = requests.get(
        f"{BASE_URL}/metrics",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert backend_metrics.status_code == 200
    assert "prediction_requests_total" in backend_metrics.text

    worker_metrics = requests.get("http://localhost:9091/metrics", timeout=10)
    assert worker_metrics.status_code == 200

    prometheus_health = requests.get(f"{PROMETHEUS_URL}/-/healthy", timeout=10)
    assert prometheus_health.status_code == 200

    up_query = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": 'up{job=~"ml-inference-service-backend|ml-inference-service-celery"}'},
        timeout=10,
    )
    assert up_query.status_code == 200
    results = up_query.json()["data"]["result"]
    assert len(results) == 2
    assert all(item["value"][1] == "1" for item in results)


@pytest.mark.e2e
def test_live_grafana_health_and_datasource():
    grafana_health = requests.get(f"{GRAFANA_URL}/api/health", timeout=10)
    assert grafana_health.status_code == 200

    datasources = requests.get(
        f"{GRAFANA_URL}/api/datasources",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=10,
    )
    assert datasources.status_code == 200
    prometheus_ds = next((item for item in datasources.json() if item.get("type") == "prometheus"), None)
    assert prometheus_ds is not None

    proxied_query = requests.get(
        f"{GRAFANA_URL}/api/datasources/proxy/{prometheus_ds['id']}/api/v1/query",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        params={"query": "up"},
        timeout=10,
    )
    assert proxied_query.status_code == 200
    assert proxied_query.json()["status"] == "success"


@pytest.mark.e2e
def test_live_grafana_has_provisioned_dashboard():
    dashboard_search = requests.get(
        f"{GRAFANA_URL}/api/search",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=10,
    )
    assert dashboard_search.status_code == 200
    dashboards = dashboard_search.json()
    dashboard = next((item for item in dashboards if item.get("uid") == "ml-inference-service"), None)
    assert dashboard is not None, dashboards
    assert dashboard["title"] == "ML Inference Service Dashboard"

    dashboard_payload = requests.get(
        f"{GRAFANA_URL}/api/dashboards/uid/ml-inference-service",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=10,
    )
    assert dashboard_payload.status_code == 200
    assert dashboard_payload.json()["dashboard"]["title"] == "ML Inference Service Dashboard"


@pytest.mark.e2e
def test_live_streamlit_dashboard():
    streamlit_response = requests.get(STREAMLIT_URL, timeout=10)
    assert streamlit_response.status_code == 200
    assert "ModuleNotFoundError" not in streamlit_response.text
