# ML Inference Service

Production-ready ML-сервис предсказаний с биллингом на основе кредитов.

## Описание

ML Inference Service - это масштабируемый сервис для выполнения ML-предсказаний через REST API. Сервис позволяет пользователям:

- Загружать ML-модели (scikit-learn)
- Выполнять предсказания через API
- Платить за предсказания внутренними кредитами
- Просматривать статистику использования

Каждый успешный prediction списывает кредиты пользователя.

## Технологический стек

- **Backend**: Python, FastAPI
- **База данных**: PostgreSQL
- **ORM**: SQLAlchemy
- **Миграции**: Alembic
- **ML**: Scikit-learn
- **Аутентификация**: JWT
- **Асинхронные задачи**: Celery + Redis
- **Мониторинг**: Prometheus + Grafana
- **Rate Limiting**: In-memory rate limiter
- **Контейнеризация**: Docker, Docker Compose
- **Тестирование**: Pytest

## Архитектура

```
┌─────────┐
│ Client  │
└────┬────┘
     │ HTTP
     ▼
┌─────────────────┐      ┌──────────┐
│  FastAPI Backend │─────▶│  Celery  │
│  ┌───────────┐  │      │  Worker  │
│  │ Auth      │  │      └────┬─────┘
│  │ Models    │  │           │
│  │ Predict   │  │           ▼
│  │ Billing   │  │      ┌──────────┐
│  └───────────┘  │      │  Redis   │
└────┬────────┬───┘      └──────────┘
     │        │
     ▼        ▼
┌─────────┐ ┌──────────────┐
│PostgreSQL│ │ ml_models/   │
└─────────┘ └──────────────┘
     │
     ▼
┌──────────────┐      ┌──────────┐
│  Prometheus  │─────▶│ Grafana  │
└──────────────┘      └──────────┘
```

## Быстрый старт

### Требования

- Docker и Docker Compose
- Python 3.11+ (для локальной разработки)

### Запуск через Docker Compose

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd ml-inference-service
```

2. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

3. Запустите сервисы:
```bash
docker-compose up -d
```

4. Сервисы будут доступны:
   - **API**: `http://localhost:8000`
   - **API документация (Swagger)**: `http://localhost:8000/docs`
   - **Streamlit Admin Panel**: `http://localhost:8501`
   - **Prometheus**: `http://localhost:9090`
   - **Grafana**: `http://localhost:3000` (admin/admin)

### Локальная разработка

1. Установите зависимости:
```bash
pip install -r backend/requirements.txt
```

2. Настройте переменные окружения в `.env`

3. Запустите миграции:
```bash
alembic upgrade head
```

4. Запустите сервер:
```bash
uvicorn backend.app.main:app --reload
```

## API Документация

### Аутентификация

Все защищенные endpoints требуют JWT токен в заголовке:
```
Authorization: Bearer <access_token>
```

### Endpoints

#### Auth

- `POST /api/v1/auth/register` - Регистрация пользователя
- `POST /api/v1/auth/login` - Вход пользователя
- `POST /api/v1/auth/refresh` - Обновление токена

#### Users

- `GET /api/v1/users/me` - Информация о текущем пользователе

#### Models

- `POST /api/v1/models/upload` - Загрузка ML модели
- `GET /api/v1/models` - Список моделей пользователя
- `GET /api/v1/models/{model_id}` - Информация о модели
- `DELETE /api/v1/models/{model_id}` - Удаление модели

#### Predictions

- `POST /api/v1/predictions` - Создание предсказания
- `GET /api/v1/predictions` - Список предсказаний
- `GET /api/v1/predictions/{prediction_id}` - Информация о предсказании

#### Billing

- `GET /api/v1/billing/balance` - Баланс кредитов
- `POST /api/v1/billing/topup` - Пополнение баланса
- `GET /api/v1/billing/transactions` - История транзакций

#### Admin (только для администраторов)

- `GET /api/v1/admin/users` - Список всех пользователей
- `GET /api/v1/admin/users/{user_id}` - Информация о пользователе
- `GET /api/v1/admin/predictions` - Список всех предсказаний (с фильтрами)
- `GET /api/v1/admin/predictions/{prediction_id}` - Информация о предсказании

## Примеры использования

### 1. Регистрация

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

Ответ:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 2. Вход

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

### 3. Загрузка модели

```bash
curl -X POST "http://localhost:8000/api/v1/models/upload" \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@model.pkl" \
  -F "model_name=my_model"
```

### 4. Пополнение баланса

```bash
curl -X POST "http://localhost:8000/api/v1/billing/topup" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100
  }'
```

### 5. Создание асинхронного предсказания

```bash
curl -X POST "http://localhost:8000/api/v1/predictions" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": 1,
    "input_data": {
      "feature1": 1.5,
      "feature2": 2.3,
      "feature3": 0.8
    }
  }'
```

Ответ (создание задачи):
```json
{
  "task_id": "abc123-def456-ghi789",
  "prediction_id": 1,
  "status": "pending",
  "message": "Prediction task created. Use GET /predictions/{prediction_id} to check status."
}
```

### 6. Проверка статуса предсказания

```bash
curl -X GET "http://localhost:8000/api/v1/predictions/1" \
  -H "Authorization: Bearer <access_token>"
```

Ответ (когда предсказание завершено):
```json
{
  "id": 1,
  "user_id": 1,
  "model_id": 1,
  "input_data": {...},
  "result": {
    "prediction": [0.85],
    "probabilities": [0.15, 0.85]
  },
  "status": "completed",
  "credits_spent": 10,
  "created_at": "2026-03-13T12:00:00"
}
```

## Схема базы данных

### Таблицы

#### users
- `id` (PK)
- `email` (unique)
- `password_hash`
- `role` (user/admin)
- `created_at`

#### ml_models
- `id` (PK)
- `owner_id` (FK -> users.id)
- `model_name`
- `file_path`
- `model_type`
- `created_at`

#### predictions
- `id` (PK)
- `user_id` (FK -> users.id)
- `model_id` (FK -> ml_models.id)
- `input_data` (JSON)
- `result` (JSON)
- `status` (pending/completed/failed)
- `credits_spent`
- `created_at`

#### transactions
- `id` (PK)
- `user_id` (FK -> users.id)
- `amount`
- `type` (credit/debit)
- `description`
- `created_at`

#### balances
- `user_id` (PK, FK -> users.id)
- `credits`
- `updated_at`

## Переменные окружения

Создайте файл `.env` на основе `.env.example` со следующими переменными:

```env
# Database
DATABASE_URL=postgresql://user:password@postgres:5432/ml_service

# JWT
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Billing
PREDICTION_COST=10

# Application
DEBUG=True
API_V1_PREFIX=/api/v1
ML_MODELS_DIR=ml_models

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Rate Limiting
RATE_LIMIT_PER_MINUTE=1000
RATE_LIMIT_PER_USER_PER_MINUTE=100

# CORS (для production указать конкретные домены через запятую)
CORS_ORIGINS=*

# File Upload
MAX_UPLOAD_SIZE_MB=100

# Logging
LOG_JSON_FORMAT=False
```

### Production настройки

Для production окружения рекомендуется:

1. **CORS**: Указать конкретные домены вместо `*`:
   ```env
   CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
   ```

2. **Логирование**: Включить JSON формат для структурированного логирования:
   ```env
   LOG_JSON_FORMAT=True
   DEBUG=False
   ```

3. **Безопасность**: Использовать сильный SECRET_KEY:
   ```env
   SECRET_KEY=<generate-strong-secret-key>
   ```

## Тестирование

Запуск тестов:
```bash
pytest
```

Запуск с покрытием:
```bash
pytest --cov=backend/app --cov-report=html --cov-report=term-missing
```

Покрытие кода должно быть >70%. Проект включает:

- Unit тесты для всех модулей
- Интеграционные тесты для полного workflow
- Тесты для API endpoints
- Тесты для Celery задач
- Тесты для биллинга и авторизации

## Streamlit Admin Panel

Административная панель доступна по адресу: **http://localhost:8501**

### Возможности панели:

- **👥 Пользователи**: список всех пользователей, статистика, графики регистраций
- **🔮 Предсказания**: все предсказания с фильтрацией, статистика, детальный просмотр
- **💰 Транзакции**: история транзакций, графики пополнений и списаний
- **📈 Статистика**: общие метрики, топ пользователей, активность по времени

Для входа используйте учетные данные администратора. Подробнее см. [README_STREAMLIT.md](README_STREAMLIT.md)

## Структура проекта

```
ml-inference-service/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── auth/            # Аутентификация
│   │   ├── billing/         # Биллинг логика
│   │   ├── database/        # DB конфигурация (connection pooling)
│   │   ├── exceptions.py    # Кастомные исключения
│   │   ├── logging_config.py # Конфигурация логирования
│   │   ├── middleware/      # Middleware (metrics, rate limiting)
│   │   ├── monitoring/       # Prometheus метрики
│   │   ├── models/          # SQLAlchemy модели
│   │   ├── schemas/         # Pydantic схемы
│   │   ├── services/        # Бизнес-логика
│   │   ├── tasks/           # Celery задачи
│   │   ├── config.py        # Конфигурация
│   │   └── main.py          # FastAPI app (с exception handlers)
│   └── requirements.txt
├── streamlit_dashboard/     # Streamlit админ панель
│   ├── main.py
│   └── requirements.txt
├── prometheus/              # Prometheus конфигурация
│   └── prometheus.yml
├── grafana/                 # Grafana конфигурация
│   ├── provisioning/        # Автоматическая настройка
│   └── dashboards/          # Dashboards
├── docker/
│   ├── backend/Dockerfile
│   ├── celery/Dockerfile    # Celery worker
│   └── streamlit/Dockerfile
├── alembic/                 # Миграции БД
├── tests/                   # Тесты (покрытие >70%)
├── ml_models/              # Загруженные модели
├── docker-compose.yml
├── .env.example            # Пример переменных окружения
└── README.md
```

## Улучшения для production

### Обработка ошибок

Сервис использует глобальные exception handlers для единообразной обработки ошибок:

- `MLServiceException` - базовое исключение
- `ModelNotFoundError` - модель не найдена (404)
- `InsufficientCreditsError` - недостаточно кредитов (402)
- `InvalidModelError` - невалидная модель (400)
- `PredictionError` - ошибка предсказания (500)

Все ошибки логируются с полным контекстом для отладки.

### Логирование

Поддерживается два формата логирования:

1. **Текстовый формат** (для разработки):
   ```
   2026-03-13 12:00:00 - backend.app.api.v1.predictions - INFO - Prediction created
   ```

2. **JSON формат** (для production):
   ```json
   {
     "timestamp": "2026-03-13T12:00:00",
     "level": "INFO",
     "logger": "backend.app.api.v1.predictions",
     "message": "Prediction created",
     "module": "predictions",
     "function": "create_prediction",
     "line": 45
   }
   ```

Включить JSON формат: `LOG_JSON_FORMAT=True`

### Connection Pooling

База данных использует connection pooling для оптимизации производительности:

- `pool_size=10` - базовый размер пула соединений
- `max_overflow=20` - максимальное количество дополнительных соединений
- `pool_pre_ping=True` - проверка соединений перед использованием
- `pool_recycle=3600` - переиспользование соединений каждый час

### Валидация загрузки моделей

- Проверка расширения файла (.pkl)
- Проверка размера файла (настраивается через `MAX_UPLOAD_SIZE_MB`)
- Валидация структуры модели (scikit-learn BaseEstimator)
- Автоматическое определение типа модели

## Workflow предсказания (асинхронный)

1. Клиент отправляет запрос на создание предсказания
2. Система проверяет JWT токен
3. Проверяется баланс пользователя
4. Если баланс достаточен:
   - Создается запись Prediction со статусом PENDING
   - Запускается Celery задача для выполнения предсказания
   - Возвращается task_id и prediction_id клиенту (HTTP 202)
5. Celery worker выполняет задачу:
   - Загружает модель из файла
   - Выполняет предсказание
   - Атомарно списывает кредиты
   - Обновляет Prediction со статусом COMPLETED и результатом
6. Клиент может проверить статус через GET /predictions/{prediction_id}
7. Если баланс недостаточен - возвращается ошибка 402

## Асинхронные задачи (Celery)

Сервис использует Celery для асинхронного выполнения предсказаний. Это позволяет:

- Обрабатывать длительные операции без блокировки API
- Масштабировать обработку предсказаний независимо от API сервера
- Повторять задачи при ошибках (до 3 попыток)

### Запуск Celery worker

При использовании Docker Compose, Celery worker запускается автоматически. Для локальной разработки:

```bash
celery -A backend.app.tasks.celery_app worker --loglevel=info
```

### Мониторинг задач

Задачи можно мониторить через:
- Логи Celery worker
- Статус предсказания через API: `GET /api/v1/predictions/{prediction_id}`

## Мониторинг (Prometheus + Grafana)

### Prometheus

Prometheus собирает метрики с backend сервиса через endpoint `/metrics`:

- `prediction_requests_total` - общее количество запросов на предсказания
- `prediction_latency_seconds` - время выполнения предсказаний (гистограмма)
- `billing_transactions_total` - количество транзакций биллинга
- `active_users` - количество активных пользователей
- `prediction_errors_total` - количество ошибок предсказаний

**Доступ**: `http://localhost:9090`

### Grafana

Grafana предоставляет визуализацию метрик через готовый dashboard:

- График prediction_requests_total по времени
- График prediction_latency (p50, p95, p99)
- График billing_transactions_total
- График active_users
- Таблица топ моделей по использованию
- Таблица топ пользователей по активности
- График success rate предсказаний

**Доступ**: `http://localhost:3000` (admin/admin)

Dashboard автоматически подключается при запуске через Docker Compose.

## Rate Limiting

Сервис использует rate limiting для защиты от злоупотреблений:

- **Глобальный лимит**: 1000 запросов/минуту на IP адрес
- **Per-user лимит**: 100 запросов/минуту для авторизованных пользователей
- **Исключения**: `/metrics`, `/health`, `/docs` endpoints не ограничены

При превышении лимита возвращается HTTP 429 с заголовками:
- `X-RateLimit-Limit` - максимальное количество запросов
- `X-RateLimit-Remaining` - оставшееся количество запросов
- `X-RateLimit-Reset` - время сброса лимита
- `Retry-After` - время ожидания перед повторным запросом

Настройки можно изменить через переменные окружения:
- `RATE_LIMIT_PER_MINUTE` - глобальный лимит
- `RATE_LIMIT_PER_USER_PER_MINUTE` - лимит на пользователя

## Безопасность

- **JWT аутентификация** для всех защищенных endpoints
- **Хеширование паролей** через bcrypt
- **Валидация входных данных** через Pydantic
- **Атомарные транзакции** для списания кредитов (SELECT FOR UPDATE)
- **Защита от SQL injection** через SQLAlchemy ORM
- **Rate limiting** для защиты от злоупотреблений
- **CORS настройки** для контроля доступа к API
- **Валидация размера файлов** при загрузке моделей
- **Глобальная обработка ошибок** с единообразными ответами


## Лицензия

MIT

## Автор

ML Platform Team
