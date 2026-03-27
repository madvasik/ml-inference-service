"""FastAPI route modules."""

from backend.app.api import admin, auth, billing, models, predictions, system, users

__all__ = [
    "admin",
    "auth",
    "billing",
    "models",
    "predictions",
    "system",
    "users",
]
