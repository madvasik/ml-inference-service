# ML Inference Service

Сервис для асинхронных ML-предсказаний на `FastAPI + Celery + PostgreSQL`.
Пользователь загружает `scikit-learn` модель, пополняет внутренний баланс, запускает prediction и получает результат позже через API. За успешные предсказания списываются кредиты.

## Что умеет проект

- регистрация и вход по JWT;
- загрузка `pkl` моделей `scikit-learn`;
- асинхронные предсказания через `Celery + Redis`;
- биллинг на внутренних кредитах;
- loyalty-уровни и скидки;
- аналитика в `Streamlit`;
- метрики в `Prometheus` и `Grafana`.

## Быстрый старт

```bash
cp .env.example .env
make stack-up
```

После запуска:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Streamlit: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Администратор создается автоматически из переменных:

- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`

## Самый короткий сценарий

1. Зарегистрировать пользователя через `/api/v1/auth/register`.
2. Пополнить баланс через `POST /api/v1/billing/payments`.
3. Загрузить модель через `POST /api/v1/models/upload`.
4. Создать prediction через `POST /api/v1/predictions`.
5. Проверять статус через `GET /api/v1/predictions/{prediction_id}`.

## Основные команды

```bash
make test
make test-unit
make smoke
make stack-up
make stack-down
make e2e
make clean
```

Что делают команды:

- `make test` — полный `pytest` с coverage;
- `make test-unit` — unit + integration тесты;
- `make smoke` — локальная быстрая проверка на `SQLite + eager Celery`;
- `make stack-up` — поднять весь docker-стек;
- `make e2e` — канонические end-to-end проверки поверх поднятого стека.

## Структура проекта

```text
backend/
  app/
  alembic/
  alembic.ini
streamlit_dashboard/
infra/
  docker/
  monitoring/
docs/
tools/
  e2e/
tests/
var/
docker-compose.yml
Makefile
```

Главные папки в `backend/app`:

- `api/routes/` — HTTP endpoints;
- `core/` — настройки, логирование, исключения;
- `db/` — подключение к БД и readiness helpers;
- `domain/models/` — ORM-модели;
- `domain/schemas/` — Pydantic-схемы;
- `services/` — бизнес-логика;
- `workers/` — Celery app и фоновые задачи;
- `observability/` — middleware и метрики.

## Что важно знать

- Баланс пополняется одним запросом: `POST /api/v1/billing/payments`.
- Кредиты списываются только после успешного завершения prediction.
- `/health` проверяет и соединение с БД, и готовность схемы. Если таблицы не инициализированы, вернется `503`.
- Runtime-данные и временные артефакты лежат в `var/`, а не в корне репозитория.

## Документация

- [Architecture](docs/architecture.md)
- [Local Development](docs/local-development.md)
- [Testing](docs/testing.md)
- [Billing and Loyalty](docs/billing-and-loyalty.md)
- [Business Plan](docs/business-plan.md)
