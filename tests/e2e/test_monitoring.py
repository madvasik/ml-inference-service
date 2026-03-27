from __future__ import annotations

import os

import pytest
import requests


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000").rstrip("/")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")


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
