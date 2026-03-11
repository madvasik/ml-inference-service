from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1 import auth, users, models, predictions, billing, admin
from backend.app.config import settings

app = FastAPI(
    title="ML Inference Service",
    description="ML prediction service with billing",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])
app.include_router(models.router, prefix=f"{settings.api_v1_prefix}/models", tags=["models"])
app.include_router(predictions.router, prefix=f"{settings.api_v1_prefix}/predictions", tags=["predictions"])
app.include_router(billing.router, prefix=f"{settings.api_v1_prefix}/billing", tags=["billing"])
app.include_router(admin.router, prefix=f"{settings.api_v1_prefix}/admin", tags=["admin"])


@app.get("/")
def root():
    return {"message": "ML Inference Service API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
