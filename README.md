# ML Inference Service

Production-ready ML-сервис предсказаний с биллингом на основе кредитов.

## Описание

Масштабируемый REST API сервис для выполнения ML-предсказаний через scikit-learn модели. Пользователи загружают модели, выполняют предсказания и платят внутренними кредитами.

## Технологический стек

- **Backend**: FastAPI, Python 3.11+
- **База данных**: PostgreSQL, SQLAlchemy, Alembic
- **ML**: Scikit-learn
- **Аутентификация**: JWT
- **Асинхронные задачи**: Celery + Redis
- **Мониторинг**: Prometheus + Grafana
- **Тестирование**: Pytest (95.52% coverage)

## Быстрый старт

### Docker Compose

```bash
git clone <repository-url>
cd ml-inference-service
cp .env.example .env
docker-compose up -d
```

**Сервисы:**
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Streamlit Admin: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)

### Локальная разработка

```bash
pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.app.main:app --reload
```

## API Endpoints

### Auth
- `POST /api/v1/auth/register` - Регистрация
- `POST /api/v1/auth/login` - Вход
- `POST /api/v1/auth/refresh` - Обновление токена

### Models
- `POST /api/v1/models/upload` - Загрузка модели
- `GET /api/v1/models` - Список моделей
- `GET /api/v1/models/{id}` - Информация о модели
- `DELETE /api/v1/models/{id}` - Удаление модели

### Predictions
- `POST /api/v1/predictions` - Создание предсказания (асинхронно)
- `GET /api/v1/predictions` - Список предсказаний
- `GET /api/v1/predictions/{id}` - Статус предсказания

### Billing
- `GET /api/v1/billing/balance` - Баланс кредитов
- `POST /api/v1/billing/topup` - Пополнение баланса
- `GET /api/v1/billing/transactions` - История транзакций

### Admin
- `GET /api/v1/admin/users` - Все пользователи
- `GET /api/v1/admin/predictions` - Все предсказания (с фильтрами)
- `GET /api/v1/admin/transactions` - Все транзакции

**Аутентификация:** Все защищенные endpoints требуют `Authorization: Bearer <token>`

## Примеры использования

### Регистрация и создание предсказания

```bash
# Регистрация
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# Пополнение баланса
curl -X POST "http://localhost:8000/api/v1/billing/topup" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"amount": 100}'

# Загрузка модели
curl -X POST "http://localhost:8000/api/v1/models/upload" \
  -H "Authorization: Bearer <token>" \
  -F "file=@model.pkl" \
  -F "model_name=my_model"

# Создание предсказания
curl -X POST "http://localhost:8000/api/v1/predictions" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": 1,
    "input_data": {"feature1": 1.5, "feature2": 2.3}
  }'
```

## Тестирование

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=backend/app --cov-report=html

# E2E тесты реальных сценариев
BASE_URL=http://localhost:8000 python3 scripts/testing/test_real_world_scenarios.py
```

**Результаты:**
- 151 unit тест пройден
- 22 E2E сценария пройдены
- Покрытие кода: 95.52%

## Переменные окружения

Основные переменные (см. `.env.example`):

```env
DATABASE_URL=postgresql://user:password@postgres:5432/ml_service
SECRET_KEY=your-secret-key
REDIS_URL=redis://redis:6379/0
PREDICTION_COST=10
RATE_LIMIT_PER_MINUTE=1000
```

## Архитектура

```
Client → FastAPI Backend → Celery Worker → Redis
              ↓                ↓
          PostgreSQL      ml_models/
              ↓
         Prometheus → Grafana
```

## Структура проекта

```
ml-inference-service/
├── backend/app/          # FastAPI приложение
│   ├── api/v1/          # API endpoints
│   ├── models/          # SQLAlchemy модели
│   ├── services/        # Бизнес-логика
│   └── tasks/           # Celery задачи
├── tests/               # Тесты (95.52% coverage)
├── scripts/testing/     # E2E тесты реальных сценариев
├── docker-compose.yml   # Docker конфигурация
└── README.md
```

## Основные возможности

- ✅ Асинхронная обработка предсказаний через Celery
- ✅ Биллинг с атомарным списанием кредитов
- ✅ Rate limiting и безопасность
- ✅ Мониторинг через Prometheus/Grafana
- ✅ Админ панель на Streamlit
- ✅ Полное тестовое покрытие

## Лицензия

MIT
