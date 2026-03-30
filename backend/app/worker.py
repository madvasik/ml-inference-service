from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from celery import Celery, Task
from celery.schedules import crontab
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
    Path(os.environ["PROMETHEUS_MULTIPROC_DIR"]).mkdir(parents=True, exist_ok=True)

from backend.app.billing import charge_prediction
from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.loyalty import recalculate_loyalty_tiers
from backend.app.metrics import (
    prediction_discount_credits_total,
    prediction_errors_total,
    prediction_latency_seconds,
    prediction_requests_total,
)
from backend.app.ml import load_model, predict
from backend.app.models import MLModel, Prediction, PredictionStatus


logger = logging.getLogger(__name__)

celery_app = Celery(
    "ml_inference_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
    task_store_eager_result=settings.celery_task_always_eager,
    task_time_limit=300,
    task_soft_time_limit=270,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "recalculate-loyalty-monthly": {
            "task": "loyalty.recalculate_monthly",
            "schedule": crontab(day_of_month=1, hour=0, minute=5),
        }
    },
)


class DatabaseTask(Task):
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
            return {"status": "completed", "prediction_id": prediction.id, "result": prediction.result}

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
        result = predict(ml_model, prediction.input_data, feature_names=model.feature_names)
        prediction_latency_seconds.labels(model_id=model_id_str).observe(time.time() - start_time)

        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).with_for_update().first()
        if prediction is None:
            return {"status": "failed", "error": "Prediction not found"}

        if prediction.status == PredictionStatus.COMPLETED:
            return {"status": "completed", "prediction_id": prediction.id, "result": prediction.result}

        success, _ = charge_prediction(db, prediction, description=f"Prediction #{prediction.id}")
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
        return {"status": "completed", "prediction_id": prediction_id, "result": result}

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


@celery_app.task(name="loyalty.recalculate_monthly")
def recalculate_monthly_loyalty():
    db = SessionLocal()
    try:
        updated_users = recalculate_loyalty_tiers(db)
        logger.info("Recalculated loyalty tiers for %s users", updated_users)
        return {"updated_users": updated_users}
    finally:
        db.close()


def prepare_multiprocess_dir() -> None:
    metrics_dir = Path(os.environ["PROMETHEUS_MULTIPROC_DIR"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    for entry in metrics_dir.iterdir():
        if entry.is_file():
            entry.unlink()


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        try:
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            output = generate_latest(registry)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(output)
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {exc}".encode())

    def log_message(self, format, *args):
        return


def start_metrics_server():
    metrics_port = int(os.getenv("METRICS_PORT", "9091"))
    server = HTTPServer(("0.0.0.0", metrics_port), MetricsHandler)
    logger.info("Prometheus metrics server started on port %s", metrics_port)
    server.serve_forever()


def run_worker() -> int:
    os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc_dir")
    prepare_multiprocess_dir()

    if os.getenv("ENABLE_METRICS_SERVER", "false").lower() == "true":
        metrics_thread = threading.Thread(target=start_metrics_server, daemon=True)
        metrics_thread.start()
        logger.info("Metrics server thread started")

    cmd = ["celery", "-A", "backend.app.worker:celery_app", "worker", "--loglevel=info"]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(run_worker())
