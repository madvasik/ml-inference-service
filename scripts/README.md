# Скрипты проекта

Все скрипты организованы по категориям для удобства использования и поддержки.

## Структура

```
scripts/
├── setup/          # Инициализация и настройка данных
├── testing/        # Тестирование и проверка систем
├── simulation/      # Симуляция активности пользователей
└── utils/          # Утилиты и комплексные скрипты
```

---

## 📦 setup/ - Инициализация данных

Скрипты для настройки и инициализации данных в системе.

### `init_data_api.sh` ✅ (РЕКОМЕНДУЕТСЯ)
Инициализация данных через API эндпоинты:
- Создает администратора (напрямую в БД, так как нет API для создания админа)
- Регистрирует пользователей через `/api/v1/auth/register`
- Пополняет балансы через `/api/v1/billing/topup`
- Загружает модели через `/api/v1/models/upload`
- Создает предсказания через `/api/v1/predictions`

**Использование:**
```bash
BASE_URL=http://localhost:8000 bash scripts/setup/init_data_api.sh
```

### `init_data_api.py`
Python версия скрипта инициализации через API.

**Использование:**
```bash
BASE_URL=http://localhost:8000 python3 scripts/setup/init_data_api.py
```

### `init_data.py` ⚠️ (СТАРЫЙ)
Старый скрипт, использующий прямой доступ к БД. Оставлен для совместимости.
**Рекомендуется использовать `init_data_api.sh` вместо этого скрипта.**

### `cleanup_data.py`
Очистка всех данных из базы:
- Удаляет все предсказания
- Удаляет все транзакции
- Удаляет все модели
- Удаляет все балансы
- Удаляет всех пользователей

**Использование:**
```bash
docker-compose exec backend python scripts/setup/cleanup_data.py
```

---

## 🧪 testing/ - Тестирование и проверка

Скрипты для тестирования и проверки работоспособности систем.

### `test_user_flows.py`
Комплексное тестирование пользовательских флоу:
- Флоу 1: Регистрация нового пользователя и первое предсказание
- Флоу 2: Несколько пользователей, высокая нагрузка
- Флоу 3: Тест недостаточного баланса
- Флоу 4: Операции администратора
- Проверка метрик Backend и Prometheus
- Сравнение данных между системами

**Использование:**
```bash
BASE_URL=http://localhost:8000 python3 scripts/testing/test_user_flows.py
```

### `verify_streamlit_and_metrics.py`
Проверка корректности Streamlit и согласованности метрик:
- Проверка данных через API (те же endpoints, что использует Streamlit)
- Проверка фильтров (user_id, model_id)
- Проверка согласованности Prometheus и Backend
- Проверка подключения Grafana
- Проверка согласованности данных между всеми системами

**Использование:**
```bash
BASE_URL=http://localhost:8000 python3 scripts/testing/verify_streamlit_and_metrics.py
```

### `check_metrics.py`
Проверка метрик Prometheus и сравнение с данными из базы.

**Использование:**
```bash
python3 scripts/testing/check_metrics.py
```

### `check_pending.py`
Проверка статуса pending предсказаний в базе данных.

**Использование:**
```bash
python3 scripts/testing/check_pending.py
```

---

## 🎮 simulation/ - Симуляция активности

Скрипты для симуляции активности пользователей.

### `simulate_activity.sh` ✅
Симуляция активности пользователей через curl и API эндпоинты:
- Вход через `/api/v1/auth/login`
- Получение моделей через `/api/v1/models`
- Создание предсказаний через `/api/v1/predictions`

**Использование:**
```bash
BASE_URL=http://localhost:8000 bash scripts/simulation/simulate_activity.sh
```

### `simulate_activity.py` ✅
Альтернативный вариант на Python с использованием библиотеки `requests`:
- Те же операции, что и в `simulate_activity.sh`
- Требует установки `requests`: `pip install requests`

**Использование:**
```bash
BASE_URL=http://localhost:8000 python3 scripts/simulation/simulate_activity.py
```

---

## 🛠️ utils/ - Утилиты

Комплексные скрипты и утилиты.

### `run_comprehensive_tests.sh`
Комплексный скрипт для запуска всех тестов:
1. Запуск пользовательских флоу
2. Дополнительная симуляция активности
3. Проверка Streamlit и метрик

**Использование:**
```bash
BASE_URL=http://localhost:8000 bash scripts/utils/run_comprehensive_tests.sh
```

---

## Переменные окружения

- `BASE_URL` - URL API сервиса (по умолчанию: `http://localhost:8000`)
- `PROMETHEUS_URL` - URL Prometheus (по умолчанию: `http://localhost:9090`)
- `GRAFANA_URL` - URL Grafana (по умолчанию: `http://localhost:3000`)
- `DATABASE_URL` - URL базы данных (только для `init_data.py`)

---

## Примеры использования

### Полная инициализация и тестирование:
```bash
# 1. Очистка данных (опционально)
docker-compose exec backend python scripts/setup/cleanup_data.py

# 2. Инициализация данных через API
BASE_URL=http://localhost:8000 bash scripts/setup/init_data_api.sh

# 3. Симуляция активности через API
BASE_URL=http://localhost:8000 bash scripts/simulation/simulate_activity.sh

# 4. Комплексное тестирование
BASE_URL=http://localhost:8000 bash scripts/utils/run_comprehensive_tests.sh

# 5. Проверка метрик
python3 scripts/testing/check_metrics.py
```

### Быстрая проверка системы:
```bash
# Проверка Streamlit и метрик
BASE_URL=http://localhost:8000 python3 scripts/testing/verify_streamlit_and_metrics.py
```

---

## Преимущества организации

✅ **Логическая группировка** - скрипты сгруппированы по назначению  
✅ **Легкая навигация** - понятно, где искать нужный скрипт  
✅ **Масштабируемость** - легко добавлять новые скрипты в нужную категорию  
✅ **Документация** - каждый раздел имеет четкое назначение  

---

## Все операции выполняются через API

Все скрипты используют API эндпоинты, что обеспечивает:
- ✅ Корректное обновление метрик Prometheus
- ✅ Правильную работу middleware (rate limiting, metrics)
- ✅ Реалистичное тестирование API
- ✅ Соответствие реальному использованию сервиса
