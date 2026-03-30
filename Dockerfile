FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src src
COPY alembic alembic
COPY alembic.ini ./
COPY docker/entrypoint-api.sh /entrypoint-api.sh
RUN chmod +x /entrypoint-api.sh

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

ENTRYPOINT ["/entrypoint-api.sh"]
