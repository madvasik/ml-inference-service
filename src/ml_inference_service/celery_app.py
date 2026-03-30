from celery import Celery

from ml_inference_service.config import get_settings

settings = get_settings()
celery_app = Celery(
    "ml_inference_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["ml_inference_service.tasks.predict"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
)
