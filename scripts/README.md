# Скрипты для симуляции и инициализации данных

Все скрипты используют **только API эндпоинты** для взаимодействия с сервисом.

## Скрипты инициализации данных

### `init_data_api.sh` ✅ (РЕКОМЕНДУЕТСЯ)
Инициализация данных через API эндпоинты:
- Создает администратора (напрямую в БД, так как нет API для создания админа)
- Регистрирует пользователей через `/api/v1/auth/register`
- Пополняет балансы через `/api/v1/billing/topup`
- Загружает модели через `/api/v1/models/upload`
- Создает предсказания через `/api/v1/predictions`

**Использование:**
```bash
BASE_URL=http://localhost:8000 bash scripts/init_data_api.sh
```

### `init_data.py` ⚠️ (СТАРЫЙ)
Старый скрипт, использующий прямой доступ к БД. Оставлен для совместимости.
**Рекомендуется использовать `init_data_api.sh` вместо этого скрипта.**

## Скрипты симуляции активности

### `simulate_activity.sh` ✅
Симуляция активности пользователей через curl и API эндпоинты:
- Вход через `/api/v1/auth/login`
- Получение моделей через `/api/v1/models`
- Создание предсказаний через `/api/v1/predictions`

**Использование:**
```bash
BASE_URL=http://localhost:8000 bash scripts/simulate_activity.sh
```

### `simulate_activity.py` ✅
Альтернативный вариант на Python с использованием библиотеки `requests`:
- Те же операции, что и в `simulate_activity.sh`
- Требует установки `requests`: `pip install requests`

**Использование:**
```bash
BASE_URL=http://localhost:8000 python3 scripts/simulate_activity.py
```

## Скрипты проверки

### `check_pending.py`
Проверка статуса pending предсказаний в базе данных.

**Использование:**
```bash
python3 scripts/check_pending.py
```

## Переменные окружения

- `BASE_URL` - URL API сервиса (по умолчанию: `http://localhost:8000`)
- `DATABASE_URL` - URL базы данных (только для `init_data.py`)

## Примеры использования

### Полная инициализация и симуляция:
```bash
# 1. Инициализация данных через API
BASE_URL=http://localhost:8000 bash scripts/init_data_api.sh

# 2. Симуляция активности через API
BASE_URL=http://localhost:8000 bash scripts/simulate_activity.sh

# 3. Проверка статуса
python3 scripts/check_pending.py
```

Все операции выполняются через API эндпоинты, что обеспечивает:
- ✅ Корректное обновление метрик Prometheus
- ✅ Правильную работу middleware (rate limiting, metrics)
- ✅ Реалистичное тестирование API
- ✅ Соответствие реальному использованию сервиса
