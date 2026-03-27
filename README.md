# ML Inference Service

Масштабируемый ML-сервис для асинхронных предсказаний по пользовательским `scikit-learn` моделям. Сервис включает JWT-аутентификацию, биллинг во внутренних кредитах, loyalty-скидки, Streamlit dashboard, Prometheus/Grafana и запуск всего стека одной командой через Docker Compose.

## Цель и задачи

Цель проекта: дать пользователю API, через который он может загрузить свою модель, отправить асинхронный inference-запрос и заплатить кредитами только за успешный результат.

Задачи проекта:

- регистрация, аутентификация и роли пользователей;
- загрузка `pkl`-моделей и запуск предсказаний через REST API;
- асинхронная обработка запросов через Celery + Redis;
- биллинг с атомарными транзакциями и историей операций;
- loyalty/discount механика с ежемесячным пересчётом;
- аналитический dashboard для администратора;
- мониторинг через Prometheus и Grafana;
- автодокументация Swagger/OpenAPI;
- тестовое покрытие выше 70%.

## Архитектура

Компоненты:

- `backend` — FastAPI, JWT, SQLAlchemy, Swagger/OpenAPI, доменная логика.
- `postgres` — хранение пользователей, балансов, моделей, предсказаний, платежей, транзакций и loyalty rules.
- `redis` — брокер и result backend Celery.
- `celery` — выполнение предсказаний в фоне.
- `celery-beat` — ежемесячный пересчёт loyalty tiers.
- `dashboard` — Streamlit-панель для администратора.
- `prometheus` — сбор метрик backend и worker.
- `grafana` — визуализация метрик.

Упрощённые принципы архитектуры:

- все ORM-модели лежат в одном файле `backend/app/models.py`;
- все Pydantic-схемы лежат в одном файле `backend/app/schemas.py`;
- HTTP-роуты лежат в одном уровне `backend/app/api/*.py`, без лишней папки `routes`;
- критичные правила биллинга сосредоточены в `backend/app/billing.py`;
- тяжёлая асинхронная логика вынесена в `backend/app/worker.py`.

## Используемые технологии

- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Celery
- Redis
- Scikit-learn
- Streamlit
- Prometheus
- Grafana
- Docker / Docker Compose
- Pytest / pytest-cov

## Структура проекта

```text
backend/
  alembic/                    # миграции БД
  app/
    api/                      # HTTP endpoints
      admin.py
      auth.py
      billing.py
      models.py
      predictions.py
      system.py
      users.py
    billing.py                # кредиты, платежи, транзакции
    config.py                 # env-настройки
    db.py                     # engine, SessionLocal, health/schema probes
    log_config.py             # логирование
    loyalty.py                # tiers, скидки, monthly recalculation
    main.py                   # точка входа FastAPI
    metrics.py                # Prometheus-метрики
    middleware.py             # rate limiting и API-метрики
    ml.py                     # загрузка и inference моделей
    models.py                 # все SQLAlchemy модели
    schemas.py                # все Pydantic схемы
    security.py               # JWT, passwords, current user/admin
    worker.py                 # Celery app, worker tasks, beat tasks
dashboard/
  api_client.py               # клиент к backend API
  config.py                   # настройки dashboard
  main.py                     # вход в Streamlit
  views.py                    # вкладки и графики
infra/
  docker/                     # Dockerfiles backend/celery/dashboard
  monitoring/                 # Prometheus + Grafana provisioning
tests/
  unit/                       # точечные проверки API и доменной логики
  integration/                # сквозные сценарии через API + БД
  e2e/                        # проверки живого docker-стека
tools/
  smoke.py                    # локальный smoke сценарий без docker
docker-compose.yml            # запуск всего стека
README_for_me.md              # упрощённое объяснение проекта
```

## Схема взаимодействия компонентов

1. Пользователь регистрируется или логинится и получает `access_token`.
2. Пользователь пополняет баланс кредитов через billing API.
3. Пользователь загружает `model.pkl`, backend сохраняет файл и метаданные.
4. `POST /api/v1/predictions` создаёт запись `prediction` и отправляет задачу в Celery.
5. Celery worker загружает модель, считает результат и только после успеха списывает кредиты.
6. Результат сохраняется в БД и доступен через `GET /api/v1/predictions/{prediction_id}`.
7. Prometheus собирает метрики с backend и worker, Grafana показывает dashboard.

## Как запустить проект

### Полный стек через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

После запуска доступны:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Dashboard: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

### Локальная smoke-проверка без Docker

```bash
make smoke
```

Smoke поднимает backend на SQLite, включает eager Celery и проверяет сценарий `register -> payment -> model upload -> prediction`.

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

Типовой пользовательский сценарий:

1. Зарегистрировать пользователя.
2. Взять `access_token` из ответа.
3. Пополнить баланс через `POST /api/v1/billing/payments`.
4. Загрузить `model.pkl`.
5. Создать prediction.
6. Периодически опрашивать `GET /api/v1/predictions/{prediction_id}`.

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

- `balances` — текущий баланс пользователя;
- `payments` — пополнения;
- `transactions` — история начислений и списаний;
- `predictions.credits_spent` — snapshot итоговой цены конкретного запроса.

Правила:

- `1 amount = 1 credit`;
- пополнение создаёт `payment` и `credit transaction`;
- списание за prediction выполняется только после успешного inference;
- транзакция по prediction уникальна по `prediction_id`, поэтому повторный запуск не спишет кредиты второй раз.

### Атомарность и обработка ошибок

- `create_payment()` делает `payment + credit transaction + balance update` в одной DB-транзакции и откатывает всё при исключении.
- worker блокирует баланс пользователя через `with_for_update()` перед фактическим списанием.
- если очередь недоступна при постановке задачи, prediction помечается как `failed` с причиной `queue_unavailable`, но списания нет.
- если inference падает, prediction получает `failed`, а баланс не меняется.
- если к моменту реального списания кредитов уже не хватает, prediction получает `failed` с причиной `insufficient_credits`.

## Как работает асинхронная обработка

- HTTP API не делает inference внутри запроса.
- `POST /api/v1/predictions` только валидирует вход, сохраняет snapshot цены и ставит задачу в Celery.
- `backend/app/worker.py` выполняет `execute_prediction`.
- `celery-beat` раз в месяц запускает `recalculate_monthly_loyalty`.

## Loyalty / Discount система

Уровни:

- `none`
- `bronze`
- `silver`
- `gold`

Правила по умолчанию:

- Bronze: от `50` успешных предсказаний за прошлый месяц, скидка `5%`;
- Silver: от `200`, скидка `10%`;
- Gold: от `500`, скидка `20%`.

Особенности реализации:

- правила лежат в таблице `loyalty_tier_rules`, а не захардкожены в API;
- при создании prediction фиксируются `base_cost`, `discount_percent`, `discount_amount`, `credits_spent`;
- ежемесячный пересчёт запускается отдельной фоновой задачей.

## Мониторинг

Мониторинг включает:

- backend-метрики через `GET /metrics`;
- worker-метрики через `http://localhost:9091/metrics`;
- Prometheus для сбора;
- Grafana для визуализации.

В Grafana уже подключён Prometheus datasource и provisioned dashboard.

## Как запускать тесты

```bash
make test
make smoke
make e2e
```

Что реально проверяется:

- auth, JWT и роли;
- загрузка модели;
- асинхронное предсказание;
- списание кредитов только после успеха;
- откаты billing-операций при ошибках;
- loyalty tiers и месячный пересчёт;
- admin API;
- health/metrics/openapi;
- live docker stack и monitoring.

## Покрытие тестами

Последний локальный прогон `pytest` после рефакторинга:

- `36 passed`
- total coverage: `84.46%`

Это выше требования ТЗ `> 70%`.

## ENV переменные

Основные:

- `DATABASE_URL`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `PREDICTION_COST`
- `DEBUG`
- `API_V1_PREFIX`
- `ML_MODELS_DIR`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CELERY_TASK_ALWAYS_EAGER`
- `RATE_LIMIT_PER_MINUTE`
- `RATE_LIMIT_PER_USER_PER_MINUTE`
- `MAX_UPLOAD_SIZE_MB`
- `LOG_JSON_FORMAT`
- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`
- `INITIAL_ADMIN_CREDITS`

Все чувствительные значения должны задаваться через `.env` или переменные окружения.

## Краткий бизнес-план

УТП:

- простой self-service ML inference для пользователей, которым нужно быстро опубликовать `scikit-learn` модель без отдельного ML Ops контура;
- прозрачная модель оплаты: платёж только за успешные inference-запросы;
- loyalty-механика стимулирует возвращаемость и рост потребления.

Финмодель:

- доход формируется из продажи кредитов;
- базовая цена prediction задаётся конфигом;
- loyalty-скидки уменьшают цену на запрос, но повышают retention;
- dashboard и метрики позволяют отслеживать воронку: пользователи -> пополнения -> успешные prediction -> расход кредитов.

Подняты:

- Prometheus с готовым scrape-конфигом
- Grafana с подключенным datasource и дашбордом

## Тесты

Команды:

```bash
make test
make smoke
make e2e
```

Что проверяется:

- auth и JWT
- роли и admin endpoints
- загрузка модели
- async prediction flow
- списание кредитов только после успешного worker run
- rollback платежей при ошибке
- loyalty tiers и перерасчет
- health и metrics

Текущее покрытие `pytest`: выше `70%`.

## Переменные окружения

Основные переменные:

- `DATABASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `PREDICTION_COST`
- `DEBUG`
- `API_V1_PREFIX`
- `ML_MODELS_DIR`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CELERY_TASK_ALWAYS_EAGER`
- `RATE_LIMIT_PER_MINUTE`
- `RATE_LIMIT_PER_USER_PER_MINUTE`
- `CORS_ORIGINS`
- `MAX_UPLOAD_SIZE_MB`
- `LOG_JSON_FORMAT`
- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`
- `INITIAL_ADMIN_CREDITS`

Пример настроек есть в [`.env.example`](/Users/madvas/Documents/ml-inference-service/.env.example).

## Краткий бизнес-план

УТП:

- простой сервис, где пользователь загружает свою модель и сразу получает платные асинхронные предсказания;
- billing встроен в продукт, а не вынесен в отдельный сложный контур;
- loyalty делает сервис удобнее для активных пользователей и стимулирует повторное использование.

Финмодель:

- пользователь покупает внутренние кредиты;
- каждый успешный prediction списывает фиксированную стоимость;
- активные пользователи получают скидку по tier-модели;
- доход растет за счет числа предсказаний и пополнений баланса;
- далее можно подключить реальный платежный шлюз без изменения доменной модели.
