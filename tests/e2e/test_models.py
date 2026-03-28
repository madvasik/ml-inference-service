"""E2e tests for ML model upload, listing, detail, and deletion."""
from __future__ import annotations

import os

import pytest
import requests

from tests.helpers import auth_headers, temporary_model_file, unique_email


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")


def _request(method: str, path: str, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)


def _register(prefix: str) -> dict[str, str]:
    email = unique_email(prefix)
    reg = _request("POST", "/api/v1/auth/register", json={"email": email, "password": "password123"})
    assert reg.status_code == 201, reg.text
    return auth_headers(reg.json()["access_token"])


def _upload_model(headers: dict[str, str]) -> int:
    with temporary_model_file() as model_path:
        with open(model_path, "rb") as f:
            resp = _request(
                "POST",
                "/api/v1/models/upload",
                headers=headers,
                data={"model_name": "e2e-test-model"},
                files={"file": ("model.pkl", f, "application/octet-stream")},
            )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.e2e
def test_live_model_upload_list_get_delete():
    headers = _register("modelcrud")
    model_id = _upload_model(headers)

    listing = _request("GET", "/api/v1/models", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert any(m["id"] == model_id for m in listing.json()["models"])

    detail = _request("GET", f"/api/v1/models/{model_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["model_name"] == "e2e-test-model"
    assert detail.json()["model_type"] == "classification"

    delete = _request("DELETE", f"/api/v1/models/{model_id}", headers=headers)
    assert delete.status_code == 204

    gone = _request("GET", f"/api/v1/models/{model_id}", headers=headers)
    assert gone.status_code == 404


@pytest.mark.e2e
def test_live_model_upload_rejects_non_pkl():
    headers = _register("badpkl")
    resp = _request(
        "POST",
        "/api/v1/models/upload",
        headers=headers,
        data={"model_name": "bad"},
        files={"file": ("model.csv", b"a,b,c\n1,2,3", "text/csv")},
    )
    assert resp.status_code == 400


@pytest.mark.e2e
def test_live_model_upload_rejects_invalid_pkl():
    headers = _register("fakepkl")
    resp = _request(
        "POST",
        "/api/v1/models/upload",
        headers=headers,
        data={"model_name": "fake"},
        files={"file": ("model.pkl", b"not a pickle", "application/octet-stream")},
    )
    assert resp.status_code == 400


@pytest.mark.e2e
def test_live_model_upload_rejects_non_model_extension():
    headers = _register("badmodel")
    resp = _request(
        "POST",
        "/api/v1/models/upload",
        headers=headers,
        data={"model_name": "bad-model"},
        files={"file": ("model.txt", b"not-a-model", "text/plain")},
    )
    assert resp.status_code == 400
