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
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/alembic/ /app/backend/alembic/

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Команда запуска Celery worker (с поддержкой метрик если нужно)
CMD ["python", "-m", "backend.app.workers.start_celery_with_metrics"]
