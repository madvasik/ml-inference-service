from __future__ import annotations

import logging
from typing import Any

import joblib
import numpy as np
from sqlalchemy.orm import Session

from ml_inference_service.celery_app import celery_app
from ml_inference_service.config import get_settings
from ml_inference_service.database import SessionLocal
from ml_inference_service.models.ml import MLModel, PredictionJob, PredictionJobStatus
from ml_inference_service.services.billing import InsufficientCreditsError, debit_prediction_if_possible

logger = logging.getLogger(__name__)
settings = get_settings()


def _run_predict(storage_path: str, features: list[float]) -> Any:
    model = joblib.load(storage_path)
    X = np.asarray(features, dtype=float).reshape(1, -1)
    out = model.predict(X)
    if hasattr(out, "tolist"):
        return out.tolist()
    return list(out)


@celery_app.task(name="predict.run_prediction_job")
def run_prediction_job(job_id: int) -> dict[str, Any]:
    db: Session = SessionLocal()
    try:
        job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
        if job is None:
            return {"ok": False, "error": "job not found"}

        job.status = PredictionJobStatus.running
        db.flush()

        ml_model = db.query(MLModel).filter(MLModel.id == job.ml_model_id).first()
        if ml_model is None or not ml_model.is_active:
            job.status = PredictionJobStatus.failed
            job.error_message = "Model not available"
            db.commit()
            return {"ok": False, "error": "model unavailable"}

        features = job.input_payload.get("features")
        if not isinstance(features, list):
            job.status = PredictionJobStatus.failed
            job.error_message = "Invalid input: features must be a list"
            db.commit()
            return {"ok": False, "error": "bad input"}

        try:
            pred = _run_predict(ml_model.storage_path, [float(x) for x in features])
        except Exception as e:  # noqa: BLE001
            logger.exception("predict failed")
            job.status = PredictionJobStatus.failed
            job.error_message = str(e)
            db.commit()
            return {"ok": False, "error": str(e)}

        job.result_payload = {"prediction": pred}
        job.status = PredictionJobStatus.success
        try:
            debit_prediction_if_possible(db, user_id=job.user_id, job_id=job.id)
        except InsufficientCreditsError:
            job.status = PredictionJobStatus.failed
            job.error_message = "Insufficient credits to complete prediction"
            job.result_payload = None
            db.commit()
            return {"ok": False, "error": "insufficient credits"}

        db.commit()
        return {"ok": True, "job_id": job_id}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
