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
- **Контейнеризация**: Docker, Docker Compose
- **Тестирование**: Pytest

## Архитектура

```
┌─────────┐
│ Client  │
└────┬────┘
     │ HTTP
     ▼
┌─────────────────┐
│  FastAPI Backend │
│  ┌───────────┐  │
│  │ Auth      │  │
│  │ Models    │  │
│  │ Predict   │  │
│  │ Billing   │  │
│  └───────────┘  │
└────┬────────┬───┘
     │        │
     ▼        ▼
┌─────────┐ ┌──────────────┐
│PostgreSQL│ │ ml_models/   │
└─────────┘ └──────────────┘
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

### 5. Создание предсказания

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

Ответ:
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

Создайте файл `.env` со следующими переменными:

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
```

## Тестирование

Запуск тестов:
```bash
pytest
```

Запуск с покрытием:
```bash
pytest --cov=backend/app --cov-report=html
```

Покрытие кода должно быть >70%.

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
│   │   ├── database/        # DB конфигурация
│   │   ├── models/          # SQLAlchemy модели
│   │   ├── schemas/         # Pydantic схемы
│   │   ├── services/        # Бизнес-логика
│   │   ├── config.py        # Конфигурация
│   │   └── main.py          # FastAPI app
│   └── requirements.txt
├── streamlit_dashboard/     # Streamlit админ панель
│   ├── main.py
│   └── requirements.txt
├── alembic/                 # Миграции БД
├── tests/                   # Тесты
├── ml_models/              # Загруженные модели
├── docker-compose.yml
└── README.md
```

## Workflow предсказания

1. Клиент отправляет запрос на создание предсказания
2. Система проверяет JWT токен
3. Проверяется баланс пользователя
4. Если баланс достаточен:
   - Атомарно списываются кредиты
   - Загружается модель из файла
   - Выполняется предсказание
   - Сохраняется результат
   - Возвращается ответ клиенту
5. Если баланс недостаточен - возвращается ошибка 402

## Безопасность

- JWT аутентификация для всех защищенных endpoints
- Хеширование паролей через bcrypt
- Валидация входных данных через Pydantic
- Атомарные транзакции для списания кредитов
- Защита от SQL injection через SQLAlchemy ORM

## Лицензия

MIT

## Автор

ML Platform Team
