# ML Inference Service

ML-сервис для загрузки `scikit-learn` моделей, асинхронных предсказаний, кредитного биллинга, mock payment gateway, loyalty tiers и мониторинга.

## Что внутри

- `FastAPI` backend с JWT-аутентификацией и OpenAPI/Swagger.
- Асинхронные предсказания через `Celery + Redis`.
- `PostgreSQL + SQLAlchemy + Alembic`.
- Кредитный биллинг с audit trail в `transactions`.
- Mock payment gateway по схеме `payment intent -> confirm`.
- Loyalty tiers: `Bronze / Silver / Gold` со скидками `5 / 10 / 20%`.
- `Prometheus + Grafana` для метрик и `Streamlit` для admin dashboard.

## Loyalty policy

- `Bronze`: от `50` успешных предсказаний за прошлый календарный месяц, скидка `5%`.
- `Silver`: от `200`, скидка `10%`.
- `Gold`: от `500`, скидка `20%`.
- Пересчет выполняется задачей `Celery Beat` в `00:05 UTC` первого числа каждого месяца.
- Стоимость prediction snapshot’ится в момент создания запроса: дальнейшая смена tier не меняет уже созданные предсказания.

## Payment flow

- Канонический API:
  - `POST /api/v1/billing/payments` создает payment intent.
  - `POST /api/v1/billing/payments/{payment_id}/confirm` подтверждает mock payment и начисляет кредиты.
- Для обратной совместимости сохранен `POST /api/v1/billing/topup`: он внутри делает `create + confirm`.
- В этой реализации `1 amount = 1 credit`.

## Быстрый старт

### Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Сервисы:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Streamlit admin: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Admin bootstrap:

- Email: `${INITIAL_ADMIN_EMAIL}` из `.env`
- Password: `${INITIAL_ADMIN_PASSWORD}` из `.env`
- По умолчанию: `admin@mlservice.com / admin123`

### Локальная разработка

`.env.example` настроен под host-run (`localhost` для Postgres/Redis). Compose сам подставляет внутренние Docker hostnames.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.app.main:app --reload
```

Отдельно для Streamlit:

```bash
pip install -r streamlit_dashboard/requirements.txt
BASE_URL=http://localhost:8000 streamlit run streamlit_dashboard/main.py
```

## Основные API endpoints

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/users/me`

### Models

- `POST /api/v1/models/upload`
- `GET /api/v1/models`
- `GET /api/v1/models/{id}`
- `DELETE /api/v1/models/{id}`

### Predictions

- `POST /api/v1/predictions`
- `GET /api/v1/predictions`
- `GET /api/v1/predictions/{id}`

`PredictionResponse` дополнительно возвращает:

- `task_id`
- `base_cost`
- `discount_percent`
- `discount_amount`
- `credits_spent`
- `completed_at`
- `failure_reason`

### Billing

- `GET /api/v1/billing/balance`
- `POST /api/v1/billing/topup`
- `POST /api/v1/billing/payments`
- `POST /api/v1/billing/payments/{payment_id}/confirm`
- `GET /api/v1/billing/payments`
- `GET /api/v1/billing/transactions`

### Admin

- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/predictions`
- `GET /api/v1/admin/predictions/{prediction_id}`
- `GET /api/v1/admin/transactions`
- `GET /api/v1/admin/payments`

## Пример сценария

```bash
# 1. Регистрация
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'

# 2. Создание payment intent
curl -X POST http://localhost:8000/api/v1/billing/payments \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"amount":100}'

# 3. Confirm payment
curl -X POST http://localhost:8000/api/v1/billing/payments/1/confirm \
  -H "Authorization: Bearer <token>"

# 4. Upload model
curl -X POST http://localhost:8000/api/v1/models/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@model.pkl" \
  -F "model_name=my_model"

# 5. Create async prediction
curl -X POST http://localhost:8000/api/v1/predictions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"model_id":1,"input_data":{"feature1":1.5,"feature2":2.3}}'
```

## Тестирование

```bash
venv/bin/pytest
```

Полезные наборы:

```bash
venv/bin/pytest tests/unit/test_billing.py
venv/bin/pytest tests/unit/test_predictions.py
venv/bin/pytest tests/unit/test_loyalty_service.py
```

E2E-скрипты находятся в `scripts/testing/`. Для них нужны поднятые сервисы через Docker Compose.

## Monitoring

- Backend и Celery экспортируют Prometheus metrics.
- Grafana dashboard показывает:
  - активных пользователей,
  - confirmed payments,
  - discounted credits,
  - prediction throughput и latency,
  - billing transaction rate,
  - loyalty tier distribution,
  - prediction errors.

## Структура проекта

```text
backend/app/
  api/v1/          REST endpoints
  billing/         billing helpers
  models/          SQLAlchemy models
  schemas/         Pydantic schemas
  services/        loyalty/payment/bootstrap logic
  tasks/           Celery worker + beat tasks

alembic/           DB migrations
streamlit_dashboard/
grafana/
prometheus/
tests/
scripts/testing/   smoke и e2e утилиты
```

## Бизнес-план

УТП:

- self-service inference для команд, которым нужен быстрый REST-слой поверх `scikit-learn` без самостоятельной сборки очередей, биллинга и мониторинга.

Целевая аудитория:

- команды data science,
- internal platform teams,
- образовательные и pet-project use cases,
- B2B SaaS, где нужно быстро монетизировать inference по кредитной модели.

Финмодель:

- базовая единица монетизации — кредиты;
- пополнение идет через payment intents;
- скидки loyalty tiers стимулируют частое использование;
- маржа формируется за счет разницы между ценой кредитов и инфраструктурной стоимостью prediction workload.

## Примечания

- Full Docker smoke (`docker compose up -d --build` + end-to-end flow) требует доступного Docker daemon.
- Администратор создается автоматически, если заданы `INITIAL_ADMIN_EMAIL` и `INITIAL_ADMIN_PASSWORD`.
- `/api/v1/billing/topup` сохранен как compatibility wrapper, но для новых интеграций рекомендуется использовать `payments` endpoints.
