"""
Unit-тесты отказных веток `tasks/predict.py` (моки сессии БД + точечные интеграции).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import joblib
import pytest
from sklearn.linear_model import LinearRegression
from sqlalchemy.orm import sessionmaker

from ml_inference_service.config import get_settings
from ml_inference_service.models.ml import MLModel, PredictionJob, PredictionJobStatus
from ml_inference_service.models.user import User
from ml_inference_service.tasks import predict as predict_module
from ml_inference_service.tasks.predict import _run_predict, run_prediction_job


def _session_factory(db_session):
    return sessionmaker(bind=db_session.bind, autocommit=False, autoflush=False)


def _query_chain(job_row, ml_row):
    def query(model):
        q = MagicMock()
        if model is PredictionJob:
            q.filter.return_value.first.return_value = job_row
        elif model is MLModel:
            q.filter.return_value.first.return_value = ml_row
        return q

    return query


def test_run_prediction_job_job_not_found():
    """Строки 33–35: задача не найдена."""
    mock_db = MagicMock()
    mock_db.query.side_effect = _query_chain(job_row=None, ml_row=None)

    with patch.object(predict_module, "SessionLocal", return_value=mock_db):
        out = run_prediction_job(999)

    assert out == {"ok": False, "error": "job not found"}
    mock_db.close.assert_called_once()


def test_run_prediction_job_model_unavailable_none():
    """Строки 40–45: модель отсутствует в БД."""
    job_row = MagicMock()
    job_row.id = 1
    job_row.user_id = 1
    job_row.ml_model_id = 42
    job_row.input_payload = {"features": [1.0]}

    mock_db = MagicMock()
    mock_db.query.side_effect = _query_chain(job_row=job_row, ml_row=None)

    with patch.object(predict_module, "SessionLocal", return_value=mock_db):
        out = run_prediction_job(1)

    assert out == {"ok": False, "error": "model unavailable"}
    assert job_row.status == PredictionJobStatus.failed
    assert job_row.error_message == "Model not available"
    mock_db.commit.assert_called()
    mock_db.close.assert_called_once()


def test_run_prediction_job_model_inactive():
    """Строки 40–45: модель есть, но is_active=False."""
    job_row = MagicMock()
    job_row.id = 2
    job_row.user_id = 1
    job_row.ml_model_id = 7
    job_row.input_payload = {"features": [1.0]}

    ml_row = MagicMock()
    ml_row.is_active = False

    mock_db = MagicMock()
    mock_db.query.side_effect = _query_chain(job_row=job_row, ml_row=ml_row)

    with patch.object(predict_module, "SessionLocal", return_value=mock_db):
        out = run_prediction_job(2)

    assert out == {"ok": False, "error": "model unavailable"}
    mock_db.close.assert_called_once()


def test_run_prediction_job_bad_input_not_list():
    """Строки 47–52: features не list."""
    job_row = MagicMock()
    job_row.id = 3
    job_row.user_id = 1
    job_row.ml_model_id = 7
    job_row.input_payload = {"features": {"x": 1}}

    ml_row = MagicMock()
    ml_row.is_active = True

    mock_db = MagicMock()
    mock_db.query.side_effect = _query_chain(job_row=job_row, ml_row=ml_row)

    with patch.object(predict_module, "SessionLocal", return_value=mock_db):
        out = run_prediction_job(3)

    assert out == {"ok": False, "error": "bad input"}
    assert job_row.status == PredictionJobStatus.failed
    assert "list" in (job_row.error_message or "")
    mock_db.close.assert_called_once()


def test_run_prediction_job_debit_unexpected_error_propagates():
    """Внешний except 76–78: дебет бросает не InsufficientCreditsError → rollback и проброс."""
    job_row = MagicMock()
    job_row.id = 4
    job_row.user_id = 1
    job_row.ml_model_id = 7
    job_row.input_payload = {"features": [1.0]}

    ml_row = MagicMock()
    ml_row.is_active = True
    ml_row.storage_path = "/tmp/fake.joblib"

    mock_db = MagicMock()
    mock_db.query.side_effect = _query_chain(job_row=job_row, ml_row=ml_row)

    with patch.object(predict_module, "SessionLocal", return_value=mock_db):
        with patch.object(predict_module, "_run_predict", return_value=[42.0]):
            with patch.object(
                predict_module,
                "debit_prediction_if_possible",
                side_effect=RuntimeError("unexpected debit failure"),
            ):
                with pytest.raises(RuntimeError, match="unexpected debit failure"):
                    run_prediction_job(4)

    mock_db.rollback.assert_called()
    mock_db.close.assert_called_once()


def test_run_prediction_job_model_inactive_real_db(client, db_session, tmp_path, monkeypatch):
    """Интеграция: реальная модель в БД с is_active=False."""
    monkeypatch.setenv("MODELS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    client.post("/api/auth/register", json={"email": "inactive@example.com", "password": "password12"})
    token = client.post(
        "/api/auth/login",
        data={"username": "inactive@example.com", "password": "password12"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    secret = get_settings().mock_topup_secret
    client.post(
        "/api/billing/mock-topup",
        headers=h,
        json={"amount_money": "1.00", "credits_to_grant": 5, "secret": secret},
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

    db_session.query(MLModel).filter(MLModel.id == mid).update({MLModel.is_active: False})
    db_session.commit()

    uid = db_session.query(User).filter(User.email == "inactive@example.com").one().id
    job = PredictionJob(
        user_id=uid,
        ml_model_id=mid,
        status=PredictionJobStatus.pending,
        input_payload={"features": [1.0]},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    factory = _session_factory(db_session)
    with patch.object(predict_module, "SessionLocal", side_effect=lambda: factory()):
        out = run_prediction_job(job.id)

    assert out == {"ok": False, "error": "model unavailable"}
    db_session.expire_all()
    row = db_session.query(PredictionJob).filter(PredictionJob.id == job.id).one()
    assert row.status == PredictionJobStatus.failed
    assert row.error_message == "Model not available"


class _TuplePredictModel:
    """Выход без tolist — покрывает ветку `return list(out)` в _run_predict."""

    def predict(self, X):
        return (1, 2, 3)


def test_run_predict_list_branch_without_tolist():
    """Ветка `return list(out)` в _run_predict (строка 26), если нет tolist."""
    with patch("ml_inference_service.tasks.predict.joblib.load", return_value=_TuplePredictModel()):
        out = _run_predict("/tmp/unused.joblib", [0.0])
    assert out == [1, 2, 3]
