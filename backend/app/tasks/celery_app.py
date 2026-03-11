from celery import Celery
from backend.app.config import settings

celery_app = Celery(
    "ml_inference_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.app.tasks.prediction_tasks"]
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_time_limit=300,  # 5 минут для предсказаний
    task_soft_time_limit=270,  # 4.5 минуты мягкий лимит
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=50,
)
