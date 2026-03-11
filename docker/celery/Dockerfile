FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY backend/ /app/backend/
COPY alembic.ini /app/
COPY alembic/ /app/alembic/

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Команда запуска Celery worker
CMD ["celery", "-A", "backend.app.tasks.celery_app", "worker", "--loglevel=info"]
