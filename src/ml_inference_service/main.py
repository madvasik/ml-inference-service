from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func
from starlette.requests import Request

from ml_inference_service.api.router import api_router
from ml_inference_service.config import get_settings
from ml_inference_service.database import SessionLocal
from ml_inference_service.models.ml import MLModel, PredictionJob, PredictionJobStatus
from ml_inference_service.models.user import User

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", docs_url="/docs", redoc_url="/redoc")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

users_total_gauge = Gauge(
    "ml_users_total",
    "Total number of registered user accounts",
)

predictions_success_total_gauge = Gauge(
    "ml_predictions_success_total",
    "Total number of successfully completed prediction jobs",
)

predictions_failed_total_gauge = Gauge(
    "ml_predictions_failed_total",
    "Total number of failed prediction jobs",
)

models_total_gauge = Gauge(
    "ml_models_total",
    "Total number of uploaded ML models (all users)",
)

Instrumentator().instrument(app).expose(app)


@app.middleware("http")
async def refresh_users_metric_for_prometheus(request: Request, call_next):
    if request.url.path == "/metrics":
        db = SessionLocal()
        try:
            n = db.query(func.count(User.id)).scalar()
            users_total_gauge.set(int(n or 0))
            pred_ok = (
                db.query(func.count(PredictionJob.id))
                .filter(PredictionJob.status == PredictionJobStatus.success)
                .scalar()
            )
            predictions_success_total_gauge.set(int(pred_ok or 0))
            pred_fail = (
                db.query(func.count(PredictionJob.id))
                .filter(PredictionJob.status == PredictionJobStatus.failed)
                .scalar()
            )
            predictions_failed_total_gauge.set(int(pred_fail or 0))
            n_models = db.query(func.count(MLModel.id)).scalar()
            models_total_gauge.set(int(n_models or 0))
        finally:
            db.close()
    return await call_next(request)

app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
