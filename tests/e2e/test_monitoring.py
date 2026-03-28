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


@pytest.mark.e2e
def test_monitoring_stack_is_wired():
    backend_health = requests.get(f"{BASE_URL}/health", timeout=10)
    assert backend_health.status_code == 200, backend_health.text

    backend_metrics = requests.get(f"{BASE_URL}/metrics", timeout=10)
    assert backend_metrics.status_code == 200, backend_metrics.text
    assert "prediction_requests_total" in backend_metrics.text

    worker_metrics = requests.get("http://localhost:9091/metrics", timeout=10)
    assert worker_metrics.status_code == 200, worker_metrics.text

    prometheus_health = requests.get(f"{PROMETHEUS_URL}/-/healthy", timeout=10)
    assert prometheus_health.status_code == 200, prometheus_health.text

    up_query = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": 'up{job=~"ml-inference-service-backend|ml-inference-service-celery"}'},
        timeout=10,
    )
    assert up_query.status_code == 200, up_query.text
    results = up_query.json()["data"]["result"]
    assert len(results) == 2
    assert all(item["value"][1] == "1" for item in results)

    grafana_health = requests.get(f"{GRAFANA_URL}/api/health", timeout=10)
    assert grafana_health.status_code == 200, grafana_health.text

    datasources = requests.get(
        f"{GRAFANA_URL}/api/datasources",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=10,
    )
    assert datasources.status_code == 200, datasources.text
    prometheus_ds = next((item for item in datasources.json() if item.get("type") == "prometheus"), None)
    assert prometheus_ds is not None

    proxied_query = requests.get(
        f"{GRAFANA_URL}/api/datasources/proxy/{prometheus_ds['id']}/api/v1/query",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        params={"query": "up"},
        timeout=10,
    )
    assert proxied_query.status_code == 200, proxied_query.text
    assert proxied_query.json()["status"] == "success"


@pytest.mark.e2e
def test_dashboard_surfaces_are_available():
    docs_response = requests.get(f"{BASE_URL}/docs", timeout=10)
    assert docs_response.status_code == 200, docs_response.text
    assert "Swagger UI" in docs_response.text

    openapi_response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
    assert openapi_response.status_code == 200, openapi_response.text
    paths = openapi_response.json()["paths"]
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/predictions" in paths
    assert "/api/v1/billing/payments" in paths

    streamlit_response = requests.get(STREAMLIT_URL, timeout=10)
    assert streamlit_response.status_code == 200, streamlit_response.text
    assert "ModuleNotFoundError" not in streamlit_response.text


@pytest.mark.e2e
def test_grafana_has_provisioned_dashboard():
    dashboard_search = requests.get(
        f"{GRAFANA_URL}/api/search",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=10,
    )
    assert dashboard_search.status_code == 200, dashboard_search.text
    dashboards = dashboard_search.json()
    dashboard = next((item for item in dashboards if item.get("uid") == "ml-inference-service"), None)
    assert dashboard is not None, dashboards
    assert dashboard["title"] == "ML Inference Service Dashboard"

    dashboard_payload = requests.get(
        f"{GRAFANA_URL}/api/dashboards/uid/ml-inference-service",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=10,
    )
    assert dashboard_payload.status_code == 200, dashboard_payload.text
    assert dashboard_payload.json()["dashboard"]["title"] == "ML Inference Service Dashboard"
