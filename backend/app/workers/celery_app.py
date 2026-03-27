from celery import Celery
from celery.schedules import crontab

from backend.app.core.config import settings

celery_app = Celery(
    "ml_inference_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.app.workers.prediction_tasks", "backend.app.workers.loyalty_tasks"]
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
    task_store_eager_result=settings.celery_task_always_eager,
    task_time_limit=300,  # 5 минут для предсказаний
    task_soft_time_limit=270,  # 4.5 минуты мягкий лимит
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
