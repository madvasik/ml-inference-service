# README for me

Этот файл объясняет проект простым языком.

## Как понять проект за 5 минут

Самая короткая версия:

- пользователь регистрируется;
- пополняет кредиты;
- загружает `pkl`-модель;
- создает prediction;
- backend быстро отвечает, а реальная работа уходит в Celery;
- после успешного результата кредиты списываются;
- админ может смотреть общую статистику в Streamlit.

Если хочешь очень быстро войти в код, открой файлы в таком порядке:

1. `docker-compose.yml`
2. `backend/app/main.py`
3. `backend/app/api/routes/predictions.py`
4. `backend/app/worker.py`
5. `backend/app/billing.py`
6. `backend/app/models/`

Этого уже хватит, чтобы понять почти все важное.

## Главные файлы

`backend/app/main.py`

- собирает FastAPI приложение;
- подключает middleware;
- подключает роуты;
- делает bootstrap при старте.

`backend/app/api/routes/`

- здесь все HTTP ручки;
- если хочешь понять, что умеет API, почти всегда нужно начинать отсюда.

`backend/app/billing.py`

- вся логика кредитов, платежей и транзакций.

`backend/app/ml.py`

- проверка файла модели;
- загрузка модели;
- обычный вызов `predict`.

`backend/app/worker.py`

- Celery app;
- фоновая задача prediction;
- ежемесячный пересчет loyalty;
- worker metrics на `9091`.

`backend/app/models/`

- таблицы БД.

`backend/app/schemas/`

- что API принимает и что возвращает.

`streamlit_dashboard/main.py`

- вход в админский dashboard.

## Как устроена логика очень просто

Есть 4 основные идеи:

1. API принимает запросы.
2. БД хранит состояние.
3. Worker делает тяжелую работу в фоне.
4. Billing следит, чтобы кредиты списывались только когда prediction реально удался.

То есть HTTP-ручка не считает модель сама.
Она только создает запись и отправляет задачу в очередь.

## Как проходит запрос пользователя шаг за шагом

### Регистрация

1. Пользователь идет в `POST /api/v1/auth/register`.
2. Backend создает пользователя.
3. Backend сразу создает для него баланс.
4. Backend возвращает access и refresh token.

### Пополнение баланса

1. Пользователь вызывает `POST /api/v1/billing/payments`.
2. Backend создает запись платежа.
3. Backend создает credit-транзакцию.
4. Баланс увеличивается.

### Загрузка модели

1. Пользователь шлет `model.pkl`.
2. Backend проверяет размер, расширение и что это правда `scikit-learn` модель.
3. Файл сохраняется на диск.
4. В БД создается запись о модели.

### Prediction

1. Пользователь вызывает `POST /api/v1/predictions`.
2. Backend проверяет, что модель его и что на балансе хватает кредитов.
3. Backend создает запись `prediction` со стоимостью и скидкой.
4. Backend отправляет задачу в Celery и сразу отвечает `202`.
5. Worker загружает модель и считает результат.
6. Если prediction успешен, только тогда списываются кредиты.
7. Если что-то упало, prediction становится `failed`, а лишнего списания нет.

## Где что лежит и зачем

```text
backend/app/
  api/routes/      # endpoints
  models/          # ORM модели
  schemas/         # Pydantic схемы
  billing.py       # кредиты и платежи
  loyalty.py       # уровни и скидки
  ml.py            # работа с моделью
  worker.py        # Celery задачи
  security.py      # JWT и пароль
  db.py            # engine и SessionLocal
  config.py        # env настройки
  main.py          # сборка приложения

streamlit_dashboard/
  main.py          # запуск dashboard
  views.py         # вкладки панели

infra/
  docker/          # Dockerfiles
  monitoring/      # Prometheus и Grafana

tests/
  unit/            # маленькие проверки по кускам
  integration/     # сценарии через API + БД
  e2e/             # проверки живого docker-стека
```

## С чего начать чтение кода

Если хочешь понять систему, читай так:

1. `backend/app/main.py`
2. `backend/app/api/routes/auth.py`
3. `backend/app/api/routes/models.py`
4. `backend/app/api/routes/predictions.py`
5. `backend/app/worker.py`
6. `backend/app/billing.py`

Почему так:

- сначала увидишь, как собирается приложение;
- потом увидишь вход пользователя;
- потом загрузку модели;
- потом главный бизнес-поток;
- потом асинхронную часть;
- потом деньги.

## Как локально что-то поменять и не сломать

Самый безопасный путь:

1. Подними стек: `docker compose up -d --build`
2. Проверь `http://localhost:8000/health`
3. Меняй один модуль за раз
4. После каждого заметного шага запускай `make test`
5. Перед финалом запускай `make smoke` и `make e2e`

Хорошее правило:

- меняешь роуты — прогоняй `tests/unit/test_*.py` для этого API;
- меняешь billing — обязательно прогоняй billing и prediction тесты;
- меняешь worker — обязательно смотри `make e2e` и monitoring.

## Как дебажить

Быстрая последовательность:

1. `docker compose ps`
2. `http://localhost:8000/health`
3. `http://localhost:8000/docs`
4. `docker compose logs backend`
5. `docker compose logs celery`
6. `http://localhost:9090/-/healthy`
7. `http://localhost:3000/api/health`

Если сломался prediction, обычно проверять нужно:

- `backend`
- `celery`
- `redis`
- `postgres`

Если не видны метрики:

- backend metrics: `http://localhost:8000/metrics`
- worker metrics: `http://localhost:9091/metrics`
- Prometheus targets
- Grafana datasource

## Как запускать тесты

Все основные команды:

```bash
make test
make test-unit
make smoke
make e2e
```

Что они делают:

- `make test` — unit + integration + coverage;
- `make test-unit` — то же самое по явным папкам;
- `make smoke` — быстрый локальный сценарий без полного docker-стека;
- `make e2e` — живой сценарий поверх поднятого compose-стека.

Что тесты проверяют:

- auth и JWT;
- роли;
- загрузку моделей;
- prediction flow;
- billing и транзакции;
- loyalty;
- health, metrics и rate limit;
- monitoring stack.

## Самая важная мысль про проект

Это не “сложная магия”.

Это довольно прямой пайплайн:

- API принимает команду;
- БД хранит состояние;
- Celery считает в фоне;
- billing делает безопасное начисление и списание;
- monitoring показывает, что все живо.
