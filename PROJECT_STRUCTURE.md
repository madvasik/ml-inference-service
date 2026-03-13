# Структура проекта

## Обзор

Проект организован по функциональным модулям с четким разделением ответственности.

## Структура директорий

```
ml-inference-service/
├── backend/                    # Backend приложение
│   ├── app/
│   │   ├── api/v1/            # API endpoints
│   │   ├── auth/              # Аутентификация
│   │   ├── billing/           # Биллинг логика
│   │   ├── database/          # DB конфигурация
│   │   ├── middleware/        # Middleware (metrics, rate limiting)
│   │   ├── monitoring/        # Prometheus метрики
│   │   ├── models/            # SQLAlchemy модели
│   │   ├── schemas/           # Pydantic схемы
│   │   ├── services/          # Бизнес-логика
│   │   └── tasks/             # Celery задачи
│   └── requirements.txt
│
├── scripts/                    # Скрипты проекта
│   ├── setup/                 # Инициализация данных
│   │   ├── init_data.py
│   │   ├── init_data_api.py
│   │   ├── init_data_api.sh
│   │   └── cleanup_data.py
│   ├── testing/               # Тестирование и проверка
│   │   ├── test_user_flows.py
│   │   ├── verify_streamlit_and_metrics.py
│   │   ├── check_metrics.py
│   │   └── check_pending.py
│   ├── simulation/            # Симуляция активности
│   │   ├── simulate_activity.py
│   │   └── simulate_activity.sh
│   ├── utils/                 # Утилиты
│   │   └── run_comprehensive_tests.sh
│   └── README.md
│
├── tests/                      # Тесты
│   ├── unit/                  # Unit тесты
│   │   ├── test_admin.py
│   │   ├── test_auth.py
│   │   ├── test_billing.py
│   │   ├── test_models.py
│   │   ├── test_predictions.py
│   │   └── ... (все unit тесты)
│   ├── integration/           # Интеграционные тесты
│   │   └── test_integration.py
│   ├── e2e/                   # End-to-end тесты
│   │   └── (готово для будущих e2e тестов)
│   └── conftest.py            # Pytest конфигурация
│
├── streamlit_dashboard/        # Streamlit админ панель
│   ├── main.py
│   └── requirements.txt
│
├── prometheus/                 # Prometheus конфигурация
│   └── prometheus.yml
│
├── grafana/                    # Grafana конфигурация
│   ├── provisioning/
│   └── dashboards/
│
├── docker/                     # Docker файлы
│   ├── backend/Dockerfile
│   ├── celery/Dockerfile
│   └── streamlit/Dockerfile
│
├── alembic/                    # Миграции БД
│   └── versions/
│
├── ml_models/                  # Загруженные ML модели
├── docker-compose.yml
├── README.md
└── PROJECT_STRUCTURE.md        # Этот файл
```

## Описание модулей

### 📦 scripts/setup/
Скрипты для инициализации и настройки данных:
- **init_data_api.sh** - Инициализация через API (рекомендуется)
- **init_data_api.py** - Python версия инициализации
- **init_data.py** - Старый вариант с прямым доступом к БД
- **cleanup_data.py** - Очистка всех данных

### 🧪 scripts/testing/
Скрипты для тестирования и проверки:
- **test_user_flows.py** - Комплексное тестирование пользовательских флоу
- **verify_streamlit_and_metrics.py** - Проверка Streamlit и метрик
- **check_metrics.py** - Проверка метрик Prometheus
- **check_pending.py** - Проверка pending предсказаний

### 🎮 scripts/simulation/
Скрипты для симуляции активности:
- **simulate_activity.py** - Симуляция на Python
- **simulate_activity.sh** - Симуляция на bash

### 🛠️ scripts/utils/
Утилиты и комплексные скрипты:
- **run_comprehensive_tests.sh** - Запуск всех тестов

### 🧪 tests/unit/
Unit тесты для отдельных компонентов:
- Тесты моделей, сервисов, API endpoints
- Быстрые, изолированные тесты

### 🔗 tests/integration/
Интеграционные тесты:
- Тесты взаимодействия между компонентами
- Тесты полных workflow

### 🎯 tests/e2e/
End-to-end тесты:
- Полные пользовательские сценарии
- Тесты всей системы целиком

## Использование

### Инициализация данных
```bash
# Очистка данных
docker-compose exec backend python scripts/setup/cleanup_data.py

# Инициализация через API
BASE_URL=http://localhost:8000 bash scripts/setup/init_data_api.sh
```

### Тестирование
```bash
# Комплексное тестирование
BASE_URL=http://localhost:8000 bash scripts/utils/run_comprehensive_tests.sh

# Отдельные тесты
BASE_URL=http://localhost:8000 python3 scripts/testing/test_user_flows.py
BASE_URL=http://localhost:8000 python3 scripts/testing/verify_streamlit_and_metrics.py
```

### Симуляция
```bash
BASE_URL=http://localhost:8000 python3 scripts/simulation/simulate_activity.py
```

### Запуск тестов
```bash
# Все тесты
pytest

# Только unit тесты
pytest tests/unit/

# Только интеграционные тесты
pytest tests/integration/

# С покрытием
pytest --cov=backend/app --cov-report=html
```

## Преимущества организации

✅ **Логическая группировка** - код сгруппирован по назначению  
✅ **Легкая навигация** - понятно, где искать нужный файл  
✅ **Масштабируемость** - легко добавлять новые компоненты  
✅ **Разделение ответственности** - четкое разделение между setup, testing, simulation  
✅ **Поддержка** - проще поддерживать и обновлять код  
