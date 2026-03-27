# Local Development

## Вариант 1: полный стек через Docker

```bash
cp .env.example .env
make stack-up
```

Остановка:

```bash
make stack-down
```

## Вариант 2: локальный backend без Docker

Установите зависимости:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
pip install -r streamlit_dashboard/requirements.txt
```

Примените миграции:

```bash
alembic -c backend/alembic.ini upgrade head
```

Запустите API:

```bash
uvicorn backend.app.main:app --reload
```

Запустите панель:

```bash
BASE_URL=http://localhost:8000 streamlit run streamlit_dashboard/main.py
```

## Локальный smoke без PostgreSQL и Redis

Основная команда:

```bash
make smoke
```

Что делает smoke:

- создает `var/smoke.db`,
- включает `CELERY_TASK_ALWAYS_EAGER=true`,
- поднимает backend на `SQLite`,
- поднимает Streamlit,
- выполняет сценарий: регистрация -> top-up -> upload модели -> prediction.

## Где лежат runtime-файлы

- модели: `var/ml_models/`
- локальный smoke: `var/smoke.db`, `var/smoke_models/`
- отчеты coverage при ручном запуске можно складывать в `var/reports/`
