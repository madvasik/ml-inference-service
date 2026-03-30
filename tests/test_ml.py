from unittest.mock import MagicMock, patch

import joblib
from sklearn.linear_model import LinearRegression
from sqlalchemy.orm import sessionmaker

from ml_inference_service.config import get_settings
from ml_inference_service.models.ml import PredictionJob, PredictionJobStatus
from ml_inference_service.models.user import User
from ml_inference_service.tasks.predict import run_prediction_job


def _session_factory(db_session):
    return sessionmaker(bind=db_session.bind, autocommit=False, autoflush=False)


def test_predict_job_debits(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("MODELS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    reg = client.post("/api/auth/register", json={"email": "u@example.com", "password": "password12"})
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    secret = get_settings().mock_topup_secret
    client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "1.00", "credits_to_grant": 10, "secret": secret},
    )

    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    p = tmp_path / "m.joblib"
    joblib.dump(model, p)

    up = client.post(
        "/api/models",
        headers=h,
        data={"name": "lin"},
        files={"file": ("m.joblib", p.read_bytes(), "application/octet-stream")},
    )
    assert up.status_code == 200
    mid = up.json()["id"]

    factory = _session_factory(db_session)

    with patch("ml_inference_service.tasks.predict.SessionLocal", side_effect=lambda: factory()):
        with patch("ml_inference_service.api.routes.ml.run_prediction_job") as task:
            task.delay.side_effect = lambda jid: run_prediction_job(jid)

            pr = client.post(
                "/api/predict",
                headers=h,
                json={"model_id": mid, "features": [3.0]},
            )
    assert pr.status_code == 200
    jid = pr.json()["job_id"]
    st = client.get(f"/api/jobs/{jid}", headers=h)
    assert st.status_code == 200
    body = st.json()
    assert body["status"] == "success"
    assert "prediction" in (body.get("result") or {})

    bal = client.get("/api/billing/balance", headers=h)
    assert bal.json()["balance_credits"] == 9


def test_enqueue_predict_inflight_cap_blocks_overbooking(client, db_session, tmp_path, monkeypatch):
    """Блокировка пользователя + учёт pending/running: нельзя поставить в очередь больше слотов, чем хватит баланса."""
    monkeypatch.setenv("MODELS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    client.post("/api/auth/register", json={"email": "cap@example.com", "password": "password12"})
    token = client.post(
        "/api/auth/login",
        data={"username": "cap@example.com", "password": "password12"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    secret = get_settings().mock_topup_secret
    client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "1.00", "credits_to_grant": 3, "secret": secret},
    )

    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    p = tmp_path / "m.joblib"
    joblib.dump(model, p)

    up = client.post(
        "/api/models",
        headers=h,
        data={"name": "lin"},
        files={"file": ("m.joblib", p.read_bytes(), "application/octet-stream")},
    )
    mid = up.json()["id"]

    with patch("ml_inference_service.api.routes.ml.run_prediction_job") as task:
        task.delay = MagicMock()
        for _ in range(3):
            r = client.post(
                "/api/predict",
                headers=h,
                json={"model_id": mid, "features": [1.0]},
            )
            assert r.status_code == 200
        blocked = client.post(
            "/api/predict",
            headers=h,
            json={"model_id": mid, "features": [1.0]},
        )
        assert blocked.status_code == 402


def test_predict_job_invalid_features_no_debit(client, db_session, tmp_path, monkeypatch):
    """Валидация входа в воркере: не list → failed, дебет не выполняется."""
    monkeypatch.setenv("MODELS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    reg = client.post("/api/auth/register", json={"email": "badfeat@example.com", "password": "password12"})
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    secret = get_settings().mock_topup_secret
    client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "1.00", "credits_to_grant": 10, "secret": secret},
    )

    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    p = tmp_path / "m.joblib"
    joblib.dump(model, p)

    up = client.post(
        "/api/models",
        headers=h,
        data={"name": "lin"},
        files={"file": ("m.joblib", p.read_bytes(), "application/octet-stream")},
    )
    assert up.status_code == 200
    mid = up.json()["id"]

    uid = db_session.query(User).filter(User.email == "badfeat@example.com").one().id
    job = PredictionJob(
        user_id=uid,
        ml_model_id=mid,
        status=PredictionJobStatus.pending,
        input_payload={"features": "not-a-list"},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    factory = _session_factory(db_session)
    with patch("ml_inference_service.tasks.predict.SessionLocal", side_effect=lambda: factory()):
        run_prediction_job(job.id)

    db_session.expire_all()
    st = client.get(f"/api/jobs/{job.id}", headers=h)
    assert st.json()["status"] == "failed"
    assert client.get("/api/billing/balance", headers=h).json()["balance_credits"] == 10


def test_predict_job_model_raises_no_debit(client, db_session, tmp_path, monkeypatch):
    """Ошибка внутри predict (модель/инференс) → failed, без списания."""
    monkeypatch.setenv("MODELS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    reg = client.post("/api/auth/register", json={"email": "boom@example.com", "password": "password12"})
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    secret = get_settings().mock_topup_secret
    client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "1.00", "credits_to_grant": 10, "secret": secret},
    )

    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    p = tmp_path / "m.joblib"
    joblib.dump(model, p)

    up = client.post(
        "/api/models",
        headers=h,
        data={"name": "lin"},
        files={"file": ("m.joblib", p.read_bytes(), "application/octet-stream")},
    )
    mid = up.json()["id"]

    factory = _session_factory(db_session)
    with patch("ml_inference_service.tasks.predict.SessionLocal", side_effect=lambda: factory()):
        with patch("ml_inference_service.tasks.predict._run_predict", side_effect=RuntimeError("model exploded")):
            with patch("ml_inference_service.api.routes.ml.run_prediction_job") as task:
                task.delay.side_effect = lambda jid: run_prediction_job(jid)
                pr = client.post(
                    "/api/predict",
                    headers=h,
                    json={"model_id": mid, "features": [1.0]},
                )
    assert pr.status_code == 200
    jid = pr.json()["job_id"]
    db_session.expire_all()
    assert client.get(f"/api/jobs/{jid}", headers=h).json()["status"] == "failed"
    assert client.get("/api/billing/balance", headers=h).json()["balance_credits"] == 10


def test_predict_job_insufficient_credits_at_debit(client, db_session, tmp_path, monkeypatch):
    """Инференс успешен, но на дебете баланс уже 0 → failed, списания нет."""
    monkeypatch.setenv("MODELS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    reg = client.post("/api/auth/register", json={"email": "nodebit@example.com", "password": "password12"})
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    secret = get_settings().mock_topup_secret
    client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "1.00", "credits_to_grant": 1, "secret": secret},
    )

    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    p = tmp_path / "m.joblib"
    joblib.dump(model, p)

    up = client.post(
        "/api/models",
        headers=h,
        data={"name": "lin"},
        files={"file": ("m.joblib", p.read_bytes(), "application/octet-stream")},
    )
    mid = up.json()["id"]

    factory = _session_factory(db_session)
    with patch("ml_inference_service.tasks.predict.SessionLocal", side_effect=lambda: factory()):
        with patch("ml_inference_service.api.routes.ml.run_prediction_job") as task:
            task.delay = MagicMock()
            pr = client.post(
                "/api/predict",
                headers=h,
                json={"model_id": mid, "features": [3.0]},
            )
    assert pr.status_code == 200
    jid = pr.json()["job_id"]

    uid = db_session.query(User).filter(User.email == "nodebit@example.com").one().id
    db_session.query(User).filter(User.id == uid).update({User.balance_credits: 0})
    db_session.commit()

    with patch("ml_inference_service.tasks.predict.SessionLocal", side_effect=lambda: factory()):
        run_prediction_job(jid)

    db_session.expire_all()
    body = client.get(f"/api/jobs/{jid}", headers=h).json()
    assert body["status"] == "failed"
    assert "Insufficient credits" in (body.get("error_message") or "")
    assert client.get("/api/billing/balance", headers=h).json()["balance_credits"] == 0
