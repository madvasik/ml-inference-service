#!/bin/sh
set -e
alembic upgrade head
exec uvicorn ml_inference_service.main:app --host 0.0.0.0 --port 8000
