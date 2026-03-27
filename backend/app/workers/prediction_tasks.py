from datetime import datetime, timezone
import logging
import time

from celery import Task
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.billing.service import charge_prediction
from backend.app.db.session import SessionLocal
from backend.app.domain.models.ml_model import MLModel
from backend.app.domain.models.prediction import Prediction, PredictionStatus
from backend.app.observability.metrics import (
    prediction_discount_credits_total,
    prediction_errors_total,
    prediction_latency_seconds,
    prediction_requests_total,
)
from backend.app.services.ml_service import predict
from backend.app.services.model_loader import load_model
from backend.app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Базовый класс для задач с доступом к БД."""

    _db: Session = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


def _mark_prediction_failed(db: Session, prediction_id: int, reason: str) -> Prediction | None:
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if prediction is None:
        return None
    prediction.status = PredictionStatus.FAILED
    prediction.failure_reason = reason
    prediction.completed_at = None
    db.commit()
    return prediction


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="predictions.execute_prediction",
    max_retries=3,
    default_retry_delay=60,
)
def execute_prediction(self, prediction_id: int):
    """Выполнение предсказания в фоновом режиме с идемпотентным биллингом."""
    db = self.db
    start_time = time.time()
    model_id_str = "unknown"

    try:
        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).with_for_update().first()
        if not prediction:
            logger.error("Prediction %s not found", prediction_id)
            return {"status": "failed", "error": "Prediction not found"}

        model_id_str = str(prediction.model_id)

        if prediction.status == PredictionStatus.COMPLETED:
            return {
                "status": "completed",
                "prediction_id": prediction.id,
                "result": prediction.result,
            }

        prediction.status = PredictionStatus.PROCESSING
        prediction.failure_reason = None
        db.commit()
        db.refresh(prediction)

        model = db.query(MLModel).filter(MLModel.id == prediction.model_id).first()
        if model is None:
            _mark_prediction_failed(db, prediction_id, "model_not_found")
            prediction_requests_total.labels(status="failed", model_id=model_id_str).inc()
            prediction_errors_total.labels(error_type="model_not_found").inc()
            return {"status": "failed", "error": "Model not found"}

        ml_model = load_model(model.file_path)
        result = predict(ml_model, prediction.input_data)
        prediction_latency_seconds.labels(model_id=model_id_str).observe(time.time() - start_time)

        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).with_for_update().first()
        if prediction is None:
            return {"status": "failed", "error": "Prediction not found"}

        if prediction.status == PredictionStatus.COMPLETED:
            return {
                "status": "completed",
                "prediction_id": prediction.id,
                "result": prediction.result,
            }

        success, _ = charge_prediction(
            db,
            prediction,
            description=f"Prediction #{prediction.id}",
        )
        if not success:
            prediction.status = PredictionStatus.FAILED
            prediction.failure_reason = "insufficient_credits"
            prediction.result = None
            prediction.completed_at = None
            db.commit()
            prediction_requests_total.labels(status="failed", model_id=model_id_str).inc()
            prediction_errors_total.labels(error_type="insufficient_credits").inc()
            return {"status": "failed", "error": "Failed to deduct credits"}

        prediction.result = result
        prediction.status = PredictionStatus.COMPLETED
        prediction.failure_reason = None
        prediction.completed_at = datetime.now(timezone.utc)
        db.commit()

        if prediction.discount_amount > 0:
            prediction_discount_credits_total.inc(prediction.discount_amount)
        prediction_requests_total.labels(status="completed", model_id=model_id_str).inc()

        logger.info("Prediction %s completed successfully", prediction_id)
        return {
            "status": "completed",
            "prediction_id": prediction_id,
            "result": result,
        }

    except OperationalError as exc:
        db.rollback()
        logger.error("Operational error executing prediction %s: %s", prediction_id, exc, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        _mark_prediction_failed(db, prediction_id, "database_error")
        prediction_requests_total.labels(status="failed", model_id=model_id_str).inc()
        prediction_errors_total.labels(error_type="database_error").inc()
        return {"status": "failed", "error": "Database error"}
    except Exception as exc:
        db.rollback()
        logger.error("Error executing prediction %s: %s", prediction_id, exc, exc_info=True)
        _mark_prediction_failed(db, prediction_id, str(exc))
        prediction_requests_total.labels(status="failed", model_id=model_id_str).inc()
        prediction_errors_total.labels(error_type="execution_error").inc()
        return {"status": "failed", "error": str(exc)}
