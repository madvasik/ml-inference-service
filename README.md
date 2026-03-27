# ML Inference Service

ML-сервис для асинхронных предсказаний по пользовательским `scikit-learn` моделям с JWT-аутентификацией, внутренним биллингом в кредитах, loyalty-скидками, Streamlit-дашбордом и мониторингом через Prometheus/Grafana.

## Цель проекта

Цель проекта — дать пользователю простой API, в котором можно:

- зарегистрироваться и получить JWT;
- пополнить внутренний баланс кредитов;
- загрузить свою `pkl`-модель;
- создать асинхронный inference-запрос;
- получить результат позже через API;
- видеть расход кредитов и статистику использования.

## Что реализовано

- REST API на `FastAPI` со Swagger/OpenAPI;
- JWT auth c ролями `user` и `admin`;
- загрузка `scikit-learn` моделей;
- асинхронные предсказания через `Celery + Redis`;
- PostgreSQL как основная БД;
- внутренний биллинг с историей транзакций;
- loyalty tiers и автоматические скидки;
- ежемесячный пересчет loyalty через `celery-beat`;
- админский Streamlit dashboard;
- метрики backend и worker для `Prometheus`;
- готовая визуализация в `Grafana`;
- unit/integration/e2e тесты.

Примечание по платежному шлюзу: в учебной реализации используется `mock`-провайдер. Внешний контракт пополнения и внутренняя транзакционная логика уже отделены, поэтому реальный gateway можно подключить без перестройки основного домена.

## Архитектура

Компоненты:

- `backend` — HTTP API, бизнес-логика, работа с БД, JWT, billing.
- `postgres` — пользователи, балансы, модели, предсказания, платежи, транзакции, loyalty rules.
- `redis` — брокер и result backend для Celery.
- `celery` — выполняет inference и публикует worker metrics.
- `celery-beat` — запускает ежемесячный пересчет loyalty.
- `streamlit` — админский дашборд.
- `prometheus` — сбор метрик backend и celery worker.
- `grafana` — готовые дашборды для мониторинга.

### Схема взаимодействия

1. Пользователь регистрируется или логинится и получает JWT.
2. Пользователь пополняет баланс через billing API.
3. Пользователь загружает `pkl`-модель, backend валидирует файл и сохраняет метаданные.
4. `POST /api/v1/predictions` создает запись `prediction` со snapshot стоимости.
5. Backend ставит задачу в Celery и сразу возвращает `202 Accepted`.
6. Worker загружает модель, делает inference и только после успеха списывает кредиты.
7. Результат сохраняется в БД, а пользователь читает его через `GET /api/v1/predictions/{id}`.
8. Prometheus собирает `/metrics` у backend и worker, Grafana показывает графики.

## Упрощенная структура проекта

```text
backend/
  alembic/                    # миграции БД
  app/
    api/routes/              # REST endpoints
    models/                  # SQLAlchemy модели по доменам
    schemas/                 # Pydantic схемы по доменам
    billing.py               # кредиты, платежи, транзакции
    bootstrap.py             # стартовый admin и seed-инициализация
    config.py                # настройки из env
    db.py                    # engine, SessionLocal, readiness
    loyalty.py               # tiers, скидки, monthly recalculation
    main.py                  # app factory и wiring
    metrics.py               # Prometheus метрики
    middleware.py            # rate limit и metrics middleware
    ml.py                    # работа с файлами моделей и predict
    security.py              # JWT, password hashing, current user/admin
    worker.py                # Celery app, tasks, worker metrics
streamlit_dashboard/
  api_client.py              # запросы к backend
  main.py                    # вход в Streamlit
  views.py                   # все вкладки dashboard
infra/
  docker/                    # Dockerfiles
  monitoring/                # Prometheus и Grafana provisioning
tests/
  unit/                      # модульные тесты
  integration/               # сценарии API + DB
  e2e/                       # проверки живого docker-стека
  conftest.py                # общие фикстуры
  helpers.py                 # повторно используемые test helpers
tools/
  smoke.py                   # быстрый локальный smoke-сценарий
docker-compose.yml           # единая точка запуска всего стека
Makefile                     # команды запуска и тестов
```

## Как запустить

### Полный стек через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Или через make:

```bash
make stack-up
```

После старта доступны:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Streamlit: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Администратор создается автоматически из:

- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`
- `INITIAL_ADMIN_CREDITS`

### Локальный smoke без PostgreSQL и Redis

```bash
make smoke
```

Smoke поднимает backend на `SQLite`, включает eager Celery и прогоняет сценарий:

`register -> payment -> model upload -> prediction`

## Основные API endpoints

Auth:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`

User:

- `GET /api/v1/users/me`

Models:

- `POST /api/v1/models/upload`
- `GET /api/v1/models`
- `GET /api/v1/models/{model_id}`
- `DELETE /api/v1/models/{model_id}`

Predictions:

- `POST /api/v1/predictions`
- `GET /api/v1/predictions`
- `GET /api/v1/predictions/{prediction_id}`

Billing:

- `GET /api/v1/billing/balance`
- `POST /api/v1/billing/payments`
- `GET /api/v1/billing/payments`
- `GET /api/v1/billing/transactions`

Admin:

- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/predictions`
- `GET /api/v1/admin/predictions/{prediction_id}`
- `GET /api/v1/admin/payments`
- `GET /api/v1/admin/transactions`

System:

- `GET /`
- `GET /health`
- `GET /metrics`
- `POST /api/v1/metrics/update-active-users`

## Как пользоваться API

Короткий сценарий:

1. Зарегистрировать пользователя.
2. Взять `access_token` из ответа.
3. Пополнить баланс запросом `POST /api/v1/billing/payments`.
4. Загрузить `model.pkl`.
5. Создать prediction.
6. Периодически читать `GET /api/v1/predictions/{id}`.

Пример:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

```bash
curl -X POST http://localhost:8000/api/v1/billing/payments \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"amount":50}'
```

## Как устроен биллинг

Сущности:

- `balances` — текущий остаток кредитов.
- `payments` — пополнения.
- `transactions` — история кредитов и списаний.

Ключевые правила:

- `1 amount = 1 credit`.
- Пополнение добавляет `payment` и `credit transaction` в одной DB-транзакции.
- Списание за prediction происходит только после успешного inference.
- У prediction debit идемпотентен: повторное выполнение не создает второе списание, потому что списание привязано к `prediction_id`.

### Атомарность и обработка ошибок

- При пополнении сначала создается `payment`, затем `credit transaction`, затем коммитится все вместе.
- При исполнении prediction worker блокирует строки через `with_for_update`, повторно проверяет статус и баланс и только потом создает `debit transaction`.
- Если очередь недоступна на этапе постановки задачи, prediction помечается как `failed` с причиной `queue_unavailable`, а кредиты не списываются.
- Если в момент фактического исполнения у пользователя уже не хватает кредитов, prediction завершается как `failed` с причиной `insufficient_credits`.
- `/health` отделяет проблему подключения к БД от проблемы неинициализированной схемы.

## Как работает асинхронная обработка

- API не делает inference внутри HTTP-запроса.
- `POST /api/v1/predictions` только создает запись и отправляет задачу в Celery.
- `backend/app/worker.py` содержит Celery app и обе фоновые задачи:
  - `execute_prediction`
  - `recalculate_monthly_loyalty`
- Worker публикует собственные Prometheus metrics на порту `9091`.

## Loyalty и скидки

Уровни:

- `none`
- `bronze`
- `silver`
- `gold`

Правила по умолчанию:

- `Bronze`: от `50` успешных предсказаний за прошлый месяц, скидка `5%`
- `Silver`: от `200`, скидка `10%`
- `Gold`: от `500`, скидка `20%`

Особенности реализации:

- Правила хранятся в таблице `loyalty_tier_rules`, а не только в коде.
- Скидка фиксируется в момент создания prediction: `base_cost`, `discount_percent`, `discount_amount`, `credits_spent`.
- Изменение уровня позже не пересчитывает старые predictions.
- `celery-beat` раз в месяц пересчитывает уровень пользователя по числу успешных predictions за предыдущий месяц.

## Мониторинг

Backend:

- endpoint: `GET /metrics`

Worker:

- endpoint: `http://localhost:9091/metrics`

Prometheus:

- backend scrape target: `backend:8000/metrics`
- worker scrape target: `celery:9091/metrics`

Grafana:

- автоматически получает provisioned Prometheus datasource
- использует dashboard из `infra/monitoring/grafana/dashboards/ml_service_dashboard.json`

Проверка состояния:

- `GET /health`
- `http://localhost:9090/-/healthy`
- `http://localhost:3000/api/health`

## Тесты

Команды:

```bash
make test
make test-unit
make smoke
make e2e
```

Эквиваленты:

```bash
venv/bin/pytest
venv/bin/python tools/smoke.py
docker compose up -d --build
make e2e
```

Что проверяется:

- auth, JWT, refresh flow, роли;
- загрузка и чтение моделей;
- async prediction flow и queue failure;
- списание только за успешный prediction;
- платежи, баланс, транзакции;
- loyalty скидки и monthly recalculation;
- health, rate limiting, backend metrics, worker metrics;
- monitoring stack: backend, Prometheus, Grafana.

Последний локальный прогон после рефакторинга:

- `pytest`: `171 passed`
- coverage: `89.65%`

## Переменные окружения

Ключевые настройки:

| Переменная | Назначение |
| --- | --- |
| `DATABASE_URL` | строка подключения к PostgreSQL |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | параметры postgres |
| `SECRET_KEY`, `ALGORITHM` | JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | TTL токенов |
| `PREDICTION_COST` | базовая цена prediction в кредитах |
| `ML_MODELS_DIR` | директория хранения моделей |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Celery/Redis |
| `CELERY_TASK_ALWAYS_EAGER` | eager-mode для локального smoke/tests |
| `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_USER_PER_MINUTE` | rate limiting |
| `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_CREDITS` | bootstrap admin |
| `MAX_UPLOAD_SIZE_MB` | лимит размера модели |
| `CORS_ORIGINS` | CORS |
| `LOG_JSON_FORMAT`, `DEBUG` | runtime/logging режим |

Полный список и значения по умолчанию: [`.env.example`](.env.example)

## Краткий бизнес-план

### УТП

Сервис дает готовый inference backend для небольших команд и учебных проектов:

- не нужно отдельно писать auth, billing и async execution;
- можно быстро загрузить `scikit-learn` модель и сразу использовать API;
- есть готовый monitoring и админская панель.

### Целевая аудитория

- внутренние продуктовые команды;
- учебные проекты;
- небольшие ML-команды;
- команды, которым нужен простой inference backend без отдельной платформы.

### Финмодель

- пользователь пополняет кредитный баланс;
- каждый успешный inference списывает кредиты;
- loyalty tiers понижают стоимость для активных пользователей и стимулируют retention;
- в рост можно добавить тарифы по типу модели, SLA, приоритетные очереди, промокоды и бонусные кредиты.
