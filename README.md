# ML Inference Service

Масштабируемый ML-сервис для асинхронных предсказаний по пользовательским `scikit-learn` моделям. Сервис включает JWT-аутентификацию, биллинг во внутренних кредитах, loyalty-скидки, Streamlit dashboard, Prometheus/Grafana и запуск всего стека одной командой через Docker Compose.

## Цель и задачи

Цель проекта: дать пользователю API, через который он может загрузить свою модель, отправить асинхронный inference-запрос и заплатить кредитами только за успешный результат.

Задачи проекта:

- регистрация, аутентификация и роли пользователей (JWT);
- загрузка `pkl`-моделей и запуск предсказаний через REST API;
- асинхронная обработка запросов через Celery + Redis;
- биллинг с атомарными транзакциями и историей операций;
- loyalty/discount механика с ежемесячным пересчётом;
- аналитический dashboard для администратора (Streamlit);
- мониторинг через Prometheus и Grafana;
- автодокументация Swagger/OpenAPI;
- тестовое покрытие выше 70%.

## Архитектура

Компоненты:

| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| backend | FastAPI | REST API, бизнес-логика, JWT, Swagger |
| postgres | PostgreSQL 15 | Основная БД |
| redis | Redis 7 | Брокер и result backend Celery |
| celery | Celery worker | Асинхронное выполнение предсказаний |
| celery-beat | Celery beat | Ежемесячный пересчёт loyalty tiers |
| dashboard | Streamlit | Админ-панель с аналитикой |
| prometheus | Prometheus | Сбор метрик |
| grafana | Grafana | Визуализация метрик |

Принципы архитектуры:

- все ORM-модели в одном файле `backend/app/models.py`;
- все Pydantic-схемы в одном файле `backend/app/schemas.py`;
- HTTP-роуты в `backend/app/api/*.py` (один файл на домен);
- биллинг сосредоточен в `backend/app/billing.py`;
- асинхронная логика в `backend/app/worker.py`.

## Используемые технологии

- Python 3.11+, FastAPI, SQLAlchemy, Alembic
- PostgreSQL, Redis, Celery
- Scikit-learn
- Streamlit
- Prometheus, Grafana
- Docker / Docker Compose
- Pytest / pytest-cov

## Структура проекта

```text
backend/
  alembic/                    # миграции БД
  app/
    api/                      # HTTP endpoints
      admin.py                  # /admin (только для ADMIN)
      auth.py                   # /auth (register, login, refresh)
      billing.py                # /billing (balance, payments, transactions)
      models.py                 # /models (upload, list, get, delete)
      predictions.py            # /predictions (create, list, get)
      system.py                 # /, /health, /metrics
      users.py                  # /users/me
    billing.py                # кредиты, платежи, атомарные транзакции
    config.py                 # env-настройки (pydantic-settings)
    db.py                     # SQLAlchemy engine, SessionLocal, health probes
    log_config.py             # логирование (text / JSON)
    loyalty.py                # tiers, скидки, monthly recalculation
    main.py                   # точка входа FastAPI
    metrics.py                # Prometheus-метрики
    middleware.py             # rate limiting и request-метрики
    ml.py                     # загрузка, валидация и inference моделей
    models.py                 # все SQLAlchemy модели (7 таблиц)
    schemas.py                # все Pydantic схемы
    security.py               # JWT, bcrypt, get_current_user/admin
    worker.py                 # Celery app, задачи, beat schedule
dashboard/
  api_client.py               # HTTP клиент к backend API
  config.py                   # настройки dashboard
  main.py                     # вход в Streamlit
  views.py                    # вкладки и графики
infra/
  docker/                     # Dockerfiles (backend, celery, streamlit)
  monitoring/                 # Prometheus config + Grafana provisioning
tests/
  unit/                       # 44 теста: API, billing, ML, worker, loyalty
  integration/                # 3 теста: полный workflow + failure modes
  e2e/                        # 33 теста: живой docker-стек по доменам
tools/
  smoke.py                    # локальный smoke-тест без docker
docker-compose.yml            # запуск всего стека
```

## Схема взаимодействия компонентов

```
Пользователь
    |
    v
[FastAPI backend] -- JWT --> [PostgreSQL]
    |                              ^
    | (POST /predictions)          |
    v                              |
[Redis] --> [Celery worker] -------+
                |
                v
         [ML model file]
                |
                v
[Prometheus] <-- metrics -- [backend + worker]
    |
    v
[Grafana dashboard]
```

1. Пользователь регистрируется/логинится -> получает `access_token`.
2. Пополняет баланс кредитов через billing API.
3. Загружает `model.pkl` -> backend сохраняет файл и метаданные.
4. `POST /predictions` создаёт запись и отправляет задачу в Celery.
5. Celery worker загружает модель, считает результат, списывает кредиты **только после успеха**.
6. Результат доступен через `GET /predictions/{prediction_id}`.
7. Prometheus собирает метрики, Grafana визуализирует.

## Как запустить проект

### Полный стек через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

После запуска:

| Сервис | URL |
|--------|-----|
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Dashboard | http://localhost:8501 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |

### Локальная smoke-проверка без Docker

```bash
make smoke
```

Поднимает backend на SQLite с eager Celery и проверяет сценарий register -> payment -> upload -> predict.

## Основные API endpoints

**Auth:**
- `POST /api/v1/auth/register` — регистрация
- `POST /api/v1/auth/login` — вход, возвращает access + refresh token
- `POST /api/v1/auth/refresh` — обновление токена

**Users:**
- `GET /api/v1/users/me` — текущий пользователь

**Models:**
- `POST /api/v1/models/upload` — загрузка .pkl модели
- `GET /api/v1/models` — список моделей пользователя
- `GET /api/v1/models/{model_id}` — детали модели
- `DELETE /api/v1/models/{model_id}` — удаление модели

**Predictions:**
- `POST /api/v1/predictions` — создание предсказания (202 Accepted)
- `GET /api/v1/predictions` — список предсказаний
- `GET /api/v1/predictions/{prediction_id}` — статус и результат

**Billing:**
- `GET /api/v1/billing/balance` — текущий баланс
- `POST /api/v1/billing/payments` — пополнение (mock-платёж)
- `GET /api/v1/billing/payments` — история платежей
- `GET /api/v1/billing/transactions` — история транзакций

**Admin (требуется роль ADMIN):**
- `GET /api/v1/admin/users` — все пользователи
- `GET /api/v1/admin/predictions` — все предсказания
- `GET /api/v1/admin/payments` — все платежи
- `GET /api/v1/admin/transactions` — все транзакции

**System:**
- `GET /` — корневой endpoint
- `GET /health` — health check (БД + схема)
- `GET /metrics` — Prometheus метрики

## Как пользоваться API

Типовой сценарий:

```bash
# 1. Регистрация
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'

# 2. Пополнение баланса
curl -X POST http://localhost:8000/api/v1/billing/payments \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"amount":50}'

# 3. Загрузка модели
curl -X POST http://localhost:8000/api/v1/models/upload \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -F "model_name=my-model" \
  -F "file=@model.pkl"

# 4. Создание предсказания
curl -X POST http://localhost:8000/api/v1/predictions \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"model_id":1,"input_data":{"feature1":1.0,"feature2":2.0}}'

# 5. Проверка результата
curl http://localhost:8000/api/v1/predictions/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Как устроен биллинг

### Сущности

- `balances` — текущий баланс пользователя;
- `payments` — пополнения баланса;
- `transactions` — история начислений (credit) и списаний (debit);
- `predictions.credits_spent` — snapshot итоговой цены конкретного запроса.

### Правила

- `1 amount = 1 credit`;
- пополнение создаёт `payment` + `credit transaction` + обновляет `balance`;
- списание за prediction выполняется **только после успешного inference**;
- транзакция по prediction уникальна по `prediction_id` — повторный запуск не спишет кредиты второй раз (идемпотентность).

### Атомарность и обработка ошибок

- `create_payment()` выполняет payment + transaction + balance update в одной DB-транзакции. При ошибке — полный rollback.
- Worker блокирует баланс через `with_for_update()` перед списанием (защита от race conditions).
- Если очередь недоступна при постановке задачи — prediction помечается `failed` с причиной `queue_unavailable`, списания нет.
- Если inference падает — prediction получает `failed`, баланс не меняется.
- Если к моменту списания кредитов не хватает — prediction получает `failed` с причиной `insufficient_credits`.

## Как работает асинхронная обработка

- HTTP API **не делает inference** внутри запроса.
- `POST /predictions` валидирует вход, сохраняет snapshot цены и ставит задачу в Celery.
- Celery worker (`execute_prediction` в `worker.py`) загружает модель, делает predict, списывает кредиты.
- Celery beat раз в месяц запускает `recalculate_monthly_loyalty`.

## Loyalty / Discount система

Уровни: `none` -> `bronze` -> `silver` -> `gold`.

| Уровень | Порог (предсказаний/месяц) | Скидка |
|---------|---------------------------|--------|
| Bronze | 50+ | 5% |
| Silver | 200+ | 10% |
| Gold | 500+ | 20% |

Особенности:

- Правила хранятся в таблице `loyalty_tier_rules` (не захардкожены).
- При создании prediction фиксируются `base_cost`, `discount_percent`, `discount_amount`, `credits_spent`.
- Пересчёт выполняется фоновой задачей 1-го числа каждого месяца в 00:05 UTC.
- Подсчитываются только COMPLETED предсказания за предыдущий месяц.

## Мониторинг (Prometheus + Grafana)

Метрики собираются с двух источников:
- backend: `http://backend:8000/metrics`
- celery worker: `http://celery:9091/metrics`

Основные метрики:

| Метрика | Тип | Описание |
|---------|-----|----------|
| `prediction_requests_total` | Counter | Предсказания по статусу |
| `prediction_latency_seconds` | Histogram | Время выполнения |
| `prediction_errors_total` | Counter | Ошибки по типу |
| `billing_transactions_total` | Counter | Транзакции (credit/debit) |
| `payments_total` | Counter | Платежи по статусу |
| `active_users` | Gauge | Активные пользователи (15 мин) |
| `loyalty_users_total` | Gauge | Пользователи по tier |

В Grafana provisioned dashboard с панелями: throughput, latency p95, success rate, billing, loyalty distribution.

## Как запускать тесты

```bash
make test          # unit + integration тесты с coverage
make smoke         # smoke-тест (SQLite + eager Celery, без Docker)
make e2e           # e2e-тесты (требует docker compose up)
```

## Покрытие тестами

Последний прогон `pytest`:

- **51 unit/integration тестов + 33 e2e теста**
- **Покрытие: 86.83%** (требование ТЗ: > 70%)

Тесты организованы в три уровня:

**Unit тесты (`tests/unit/`)** — 48 тестов, 9 файлов:

| Файл | Что проверяет |
|------|--------------|
| `test_app.py` | root, health, metrics, OpenAPI, logging |
| `test_auth_api.py` | register, login, refresh, JWT валидация, rate limit |
| `test_admin_api.py` | admin endpoints, проверка роли |
| `test_billing.py` | пополнение, rollback, идемпотентность, валидация |
| `test_loyalty.py` | правила, месячный пересчёт, discount snapshot |
| `test_ml.py` | загрузка, валидация, predict, тип модели, features |
| `test_models_api.py` | upload, list, get, delete, изоляция по owner |
| `test_predictions_api.py` | создание, баланс, queue failure, изоляция |
| `test_worker.py` | успешный debit, insufficient credits, model failure |

**Integration тесты (`tests/integration/`)** — 3 теста:

| Файл | Что проверяет |
|------|--------------|
| `test_workflow.py` | полный workflow, queue failure, worker failure |

**E2e тесты (`tests/e2e/`)** — 33 теста, 6 файлов (требуют `docker compose up`):

| Файл | Что проверяет |
|------|--------------|
| `test_system.py` | health, root, metrics, docs, monitoring stack, Grafana, Streamlit |
| `test_auth.py` | auth flow, дубликаты, wrong password, токены, protected endpoints, профиль |
| `test_billing.py` | payments, валидация, накопление |
| `test_models.py` | CRUD, валидация (non-pkl, invalid pkl, wrong extension) |
| `test_predictions.py` | полный workflow, zero balance, foreign model, scoping, multiple debits |
| `test_admin.py` | platform data, фильтрация по user, 404, access control |

## ENV переменные

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | postgresql://... | Строка подключения к БД |
| `SECRET_KEY` | your-secret-key... | Секрет для JWT |
| `ALGORITHM` | HS256 | Алгоритм JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Время жизни access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 | Время жизни refresh token |
| `PREDICTION_COST` | 10 | Базовая стоимость предсказания |
| `DEBUG` | True | Debug-режим |
| `ML_MODELS_DIR` | var/ml_models | Директория хранения моделей |
| `CELERY_BROKER_URL` | redis://redis:6379/0 | Брокер Celery |
| `CELERY_RESULT_BACKEND` | redis://redis:6379/0 | Result backend |
| `CELERY_TASK_ALWAYS_EAGER` | False | Синхронный режим (для тестов) |
| `RATE_LIMIT_PER_MINUTE` | 1000 | Глобальный rate limit |
| `RATE_LIMIT_PER_USER_PER_MINUTE` | 100 | Per-user rate limit |
| `MAX_UPLOAD_SIZE_MB` | 100 | Макс. размер модели |
| `INITIAL_ADMIN_EMAIL` | - | Email начального админа |
| `INITIAL_ADMIN_PASSWORD` | - | Пароль начального админа |
| `INITIAL_ADMIN_CREDITS` | 10000 | Начальный баланс админа |

Все секреты задаются через `.env` или переменные окружения. Пример: `.env.example`.

## Краткий бизнес-план

**УТП:**
- Self-service ML inference: пользователь загружает `scikit-learn` модель и сразу получает платный асинхронный API;
- Pay-per-success: оплата только за успешные предсказания;
- Loyalty-механика стимулирует активное использование.

**Финмодель:**
- Доход из продажи кредитов;
- Базовая цена prediction настраивается через конфиг;
- Loyalty-скидки снижают цену для активных пользователей, повышая retention;
- Dashboard и метрики позволяют отслеживать воронку: регистрации -> пополнения -> predictions -> расход кредитов;
- Можно подключить реальный платёжный шлюз без изменения доменной модели.
