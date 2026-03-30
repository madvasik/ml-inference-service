from fastapi import APIRouter

from ml_inference_service.api.routes import analytics, auth, billing, ml, promocodes, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(ml.router, prefix="", tags=["ml"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(promocodes.router, prefix="/promocodes", tags=["promocodes"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
