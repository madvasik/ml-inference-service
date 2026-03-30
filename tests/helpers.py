from __future__ import annotations

import tempfile
import time
from contextlib import contextmanager
from uuid import uuid4

import numpy as np
from skops.io import dump as skops_dump
from sklearn.ensemble import RandomForestClassifier


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}_{uuid4().hex[:10]}@example.com"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def temporary_model_file():
    features = np.array([[1, 2], [2, 3], [3, 4], [4, 5]])
    labels = np.array([0, 0, 1, 1])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(features, labels)

    with tempfile.NamedTemporaryFile(suffix=".skops") as temp_file:
        skops_dump(model, temp_file.name)
        temp_file.flush()
        yield temp_file.name


def wait_for_prediction(fetch_prediction, prediction_id: int, timeout_seconds: int = 20) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = fetch_prediction(prediction_id)
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.5)
    raise TimeoutError(f"Prediction {prediction_id} did not finish in time")
