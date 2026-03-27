# ML Inference Service

Сервис для загрузки `scikit-learn` моделей и запуска предсказаний через API.
За каждое успешное предсказание с пользователя списываются внутренние кредиты.

## Что делает проект

Проект решает 4 задачи:

1. хранит пользователей и выдаёт им токены для входа;
2. принимает и хранит ML-модели;
3. запускает предсказания в фоне, чтобы API не зависал;
4. ведёт баланс кредитов, пополнение и историю списаний.

Дополнительно есть:

- простая админ-панель на `Streamlit`;
- мониторинг через `Prometheus` и `Grafana`;
- автоматическое создание первого администратора;
- система уровней лояльности со скидкой на предсказания.

Выбранная вариативная часть ТЗ: вариант Б.
В проекте реализованы уровни `Bronze / Silver / Gold`, скидка на стоимость предсказания и фоновый ежемесячный пересчёт статуса через `Celery Beat`.

## Из чего состоит проект

- `backend` - основное API.
- `postgres` - база данных.
- `redis` - очередь и промежуточное хранилище для фоновых задач.
- `celery` - воркер, который выполняет предсказания.
- `celery-beat` - планировщик регулярных задач.
- `streamlit` - админ-панель.
- `prometheus` и `grafana` - метрики и графики.

## Как это работает

Обычный сценарий такой:

1. пользователь регистрируется и входит в систему;
2. пополняет баланс кредитов;
3. загружает модель;
4. отправляет запрос на предсказание;
5. задача уходит в очередь;
6. воркер выполняет расчёт;
7. если предсказание выполнено успешно, кредиты списываются;
8. результат сохраняется в базе и доступен через API.

Если очередь недоступна, запрос не зависает в ожидании: задача сразу получает статус ошибки.

## Уровни лояльности

Уровень зависит от числа успешных предсказаний за прошлый месяц.

- `Bronze` - от `50` предсказаний, скидка `5%`
- `Silver` - от `200`, скидка `10%`
- `Gold` - от `500`, скидка `20%`

Стоимость фиксируется в момент создания запроса. Если уровень пользователя изменился позже, старые запросы не пересчитываются.

## Пополнение баланса

В проекте используется тестовый платёжный поток:

1. создаётся запись о платеже;
2. платёж подтверждается;
3. после подтверждения кредиты зачисляются на баланс.

Правило простое: `1 amount = 1 credit`.

Для совместимости сохранён старый endpoint `POST /api/v1/billing/topup`.

## Быстрый запуск

### Запуск через Docker

```bash
cp .env.example .env
docker compose up -d --build
```

После запуска:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Streamlit: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Первый администратор создаётся автоматически из `.env`:

- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`

Значения по умолчанию:

- `admin@mlservice.com`
- `admin123`

### Локальный запуск без Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.app.main:app --reload
```

Для панели `Streamlit`:

```bash
pip install -r streamlit_dashboard/requirements.txt
BASE_URL=http://localhost:8000 streamlit run streamlit_dashboard/main.py
```

### Локальный smoke без PostgreSQL и Redis

Это режим для быстрой ручной проверки API и панели, если нужно быстро поднять проект без Docker.
Для асинхронных задач используется `CELERY_TASK_ALWAYS_EAGER=true`, а в качестве БД — `SQLite`.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
pip install -r streamlit_dashboard/requirements.txt

DATABASE_URL=sqlite:///./smoke.db \
SECRET_KEY=smoke-secret \
CELERY_TASK_ALWAYS_EAGER=true \
CELERY_BROKER_URL=memory:// \
CELERY_RESULT_BACKEND=cache+memory:// \
ML_MODELS_DIR=smoke_models \
venv/bin/python -c "from backend.app.database.base import Base; from backend.app.database.session import engine; Base.metadata.create_all(bind=engine)"

DATABASE_URL=sqlite:///./smoke.db \
SECRET_KEY=smoke-secret \
CELERY_TASK_ALWAYS_EAGER=true \
CELERY_BROKER_URL=memory:// \
CELERY_RESULT_BACKEND=cache+memory:// \
ML_MODELS_DIR=smoke_models \
venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

После этого можно отдельно поднять панель:

```bash
BASE_URL=http://127.0.0.1:8000 \
venv/bin/streamlit run streamlit_dashboard/main.py --server.headless true
```

## Основные разделы API

Актуальный список и формат запросов всегда доступны в Swagger: `http://localhost:8000/docs`

Главные группы endpoints:

- `auth` - регистрация и вход;
- `users` - данные текущего пользователя;
- `models` - загрузка и просмотр моделей;
- `predictions` - создание и просмотр предсказаний;
- `billing` - баланс, платежи, транзакции;
- `admin` - просмотр пользователей, предсказаний, платежей и транзакций.

## Минимальный пример работы

1. Зарегистрировать пользователя: `POST /api/v1/auth/register`
2. Войти: `POST /api/v1/auth/login`
3. Пополнить баланс:
   `POST /api/v1/billing/payments`
   `POST /api/v1/billing/payments/{payment_id}/confirm`
4. Загрузить модель: `POST /api/v1/models/upload`
5. Создать предсказание: `POST /api/v1/predictions`
6. Проверить статус предсказания: `GET /api/v1/predictions/{id}`

## Проверка проекта

Запуск тестов:

```bash
venv/bin/pytest
```

Проверка Docker Compose-конфига:

```bash
docker compose config
```

Полезные выборочные проверки:

```bash
venv/bin/pytest tests/unit/test_billing.py
venv/bin/pytest tests/unit/test_predictions.py
venv/bin/pytest tests/unit/test_loyalty_service.py
```

E2E/smoke скрипты для поднятого стека:

```bash
bash scripts/testing/run_all_e2e_tests.sh
python3 scripts/testing/test_no_crashes.py
python3 scripts/testing/test_real_world_scenarios.py
python3 scripts/testing/test_grafana_consistency.py
```

## Структура репозитория

```text
backend/app/
  api/         endpoints
  models/      таблицы базы данных
  schemas/     форматы запросов и ответов
  services/    бизнес-логика
  tasks/       фоновые задачи

alembic/       миграции базы
streamlit_dashboard/
prometheus/
grafana/
tests/
docker/
```

## Для чего проект может быть полезен

Проект подходит как учебный пример сервиса, в котором есть:

- API;
- база данных;
- фоновые задачи;
- биллинг;
- мониторинг;
- простая админ-панель.

Его можно использовать как основу для собственного ML-сервиса или как пример архитектуры дипломного проекта.

## Бизнес-план

УТП:

- self-service сервис для команд, которым нужен готовый REST-слой над `scikit-learn` моделями;
- монетизация заложена сразу: кредиты, платежи, история транзакций, скидки по лояльности;
- инфраструктурные части уже включены: очередь задач, мониторинг, dashboard, swagger.

Целевая аудитория:

- internal platform / data science команды;
- учебные и дипломные проекты;
- маленькие B2B SaaS-продукты, которым нужен быстрый inference API без отдельной разработки биллинга.

Финмодель:

- пользователь покупает кредиты пакетами;
- каждое успешное предсказание списывает фиксированную стоимость;
- уровни лояльности повышают retention и среднее число предсказаний на пользователя;
- маржа формируется как разница между ценой кредитов и стоимостью инфраструктуры/ML workload.

## Важные замечания

- Для полного запуска нужен рабочий Docker daemon.
- Docker-образы проекта используют `Python 3.11`; локальный `venv` можно запускать и на `Python 3.13`.
- Папка `ml_models/` используется для хранения загруженных моделей.
- `/health` теперь проверяет не только API, но и доступность БД.
- Платёжная логика в этом проекте тестовая, без реального внешнего платёжного провайдера.
- Для локального smoke-режима можно использовать `CELERY_TASK_ALWAYS_EAGER=true`, но production-сценарий рассчитан на отдельные `Redis + Celery worker`.
