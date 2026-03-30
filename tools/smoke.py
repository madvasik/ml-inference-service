from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import requests
from sklearn.ensemble import RandomForestClassifier
from skops.io import dump as skops_dump


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAR_DIR = PROJECT_ROOT / "var"
SMOKE_DB = VAR_DIR / "smoke.db"
SMOKE_MODELS_DIR = VAR_DIR / "smoke_models"
BACKEND_URL = "http://127.0.0.1:18000"
STREAMLIT_URL = "http://127.0.0.1:18501"


def _wait_for_http(url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}")


def _read_process_output(process: subprocess.Popen[str]) -> str:
    if process.stdout is None:
        return ""
    try:
        return process.stdout.read()
    except Exception:
        return ""


def _start_process(command: list[str], env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{SMOKE_DB}",
            # Must satisfy backend Settings (min 32 chars, not a known placeholder).
            "SECRET_KEY": "smoke-test-secret-key-minimum-32-chars-long!",
            "DEBUG": "false",
            "CELERY_TASK_ALWAYS_EAGER": "true",
            "CELERY_BROKER_URL": "memory://",
            "CELERY_RESULT_BACKEND": "cache+memory://",
            "ML_MODELS_DIR": str(SMOKE_MODELS_DIR.relative_to(PROJECT_ROOT)),
            "BASE_URL": BACKEND_URL,
        }
    )
    return env


def _prepare_runtime() -> None:
    VAR_DIR.mkdir(exist_ok=True)
    if SMOKE_DB.exists():
        SMOKE_DB.unlink()
    if SMOKE_MODELS_DIR.exists():
        shutil.rmtree(SMOKE_MODELS_DIR)
    SMOKE_MODELS_DIR.mkdir(parents=True, exist_ok=True)


def _init_schema(env: dict[str, str]) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.app.db import Base, get_engine; Base.metadata.create_all(bind=get_engine())",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def _exercise_backend() -> None:
    email = f"smoke-{int(time.time())}@example.com"
    password = "testpassword123"

    register_response = requests.post(
        f"{BACKEND_URL}/api/v1/auth/register",
        json={"email": email, "password": password},
        timeout=10,
    )
    register_response.raise_for_status()
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payment_response = requests.post(
        f"{BACKEND_URL}/api/v1/billing/payments",
        json={"amount": 50},
        headers=headers,
        timeout=10,
    )
    payment_response.raise_for_status()

    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([0, 1, 0, 1])
    model = RandomForestClassifier(n_estimators=5, random_state=42)
    model.fit(X, y)

    with tempfile.NamedTemporaryFile(suffix=".skops") as temp_file:
        skops_dump(model, temp_file.name)
        temp_file.flush()
        with open(temp_file.name, "rb") as model_file:
            upload_response = requests.post(
                f"{BACKEND_URL}/api/v1/models/upload",
                headers=headers,
                data={
                    "model_name": "smoke-model",
                    "feature_names": '["feature1", "feature2"]',
                },
                files={"file": ("smoke.skops", model_file, "application/octet-stream")},
                timeout=20,
            )
        upload_response.raise_for_status()
        model_id = upload_response.json()["id"]

    prediction_response = requests.post(
        f"{BACKEND_URL}/api/v1/predictions",
        json={"model_id": model_id, "input_data": {"feature1": 1, "feature2": 2}},
        headers=headers,
        timeout=20,
    )
    prediction_response.raise_for_status()
    prediction_id = prediction_response.json()["prediction_id"]

    deadline = time.time() + 10
    while time.time() < deadline:
        result_response = requests.get(
            f"{BACKEND_URL}/api/v1/predictions/{prediction_id}",
            headers=headers,
            timeout=10,
        )
        result_response.raise_for_status()
        payload = result_response.json()
        if payload["status"] == "completed":
            return
        if payload["status"] == "failed":
            raise RuntimeError(f"Smoke prediction failed: {payload}")
        time.sleep(0.5)
    raise RuntimeError("Smoke prediction did not complete in time")


def main() -> int:
    _prepare_runtime()
    env = _build_env()
    _init_schema(env)

    backend_process: subprocess.Popen[str] | None = None
    streamlit_process: subprocess.Popen[str] | None = None

    try:
        backend_process = _start_process(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "18000",
            ],
            env,
        )
        _wait_for_http(f"{BACKEND_URL}/health")

        streamlit_process = _start_process(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "dashboard/main.py",
                "--server.headless=true",
                "--server.port=18501",
                "--server.address=127.0.0.1",
            ],
            env,
        )
        _wait_for_http(STREAMLIT_URL)

        _exercise_backend()
        print("Smoke check passed")
        return 0
    except Exception as exc:
        if backend_process and backend_process.poll() is not None:
            print(_read_process_output(backend_process))
        if streamlit_process and streamlit_process.poll() is not None:
            print(_read_process_output(streamlit_process))
        print(f"Smoke check failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if streamlit_process is not None:
            _stop_process(streamlit_process)
        if backend_process is not None:
            _stop_process(backend_process)


if __name__ == "__main__":
    raise SystemExit(main())
