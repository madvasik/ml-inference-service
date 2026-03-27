# README for me

Этот файл нужен, чтобы быстро войти в проект без сложных слов и лишней архитектуры.

## Как разобраться в проекте за 5 минут

Смотри на сервис как на одну простую цепочку:

1. Пользователь регистрируется и получает токен.
2. Пополняет баланс кредитов.
3. Загружает свою `pkl`-модель.
4. Создаёт prediction.
5. Worker считает результат в фоне.
6. Кредиты списываются только если prediction завершился успешно.

Если понять эту цепочку, понятен почти весь проект.

## С чего начать чтение кода

Открывай файлы в таком порядке:

1. `docker-compose.yml`
2. `backend/app/main.py`
3. `backend/app/models.py`
4. `backend/app/api/auth.py`
5. `backend/app/api/models.py`
6. `backend/app/api/predictions.py`
7. `backend/app/worker.py`
8. `backend/app/billing.py`

Этого хватает, чтобы понять, как сервис работает целиком.

## Главные файлы проекта

`backend/app/main.py`

- собирает FastAPI-приложение;
- подключает middleware и все роуты;
- на старте создаёт loyalty rules и initial admin, если они заданы в env.

`backend/app/models.py`

- все таблицы БД в одном месте;
- лучший файл, чтобы понять, какие сущности вообще есть.

`backend/app/api/*.py`

- здесь лежат все HTTP-ручки;
- каждый файл отвечает за свой блок: auth, billing, models, predictions, admin, system.

`backend/app/billing.py`

- логика кредитов, платежей и списаний;
- здесь самое важное правило проекта: не списывать раньше времени.

`backend/app/worker.py`

- Celery app;
- фоновая prediction-задача;
- ежемесячный пересчёт loyalty.

`dashboard/main.py`

- вход в Streamlit dashboard.

## Как устроена логика очень просто

Тут всего несколько понятных частей:

- API принимает запросы.
- БД хранит состояние.
- Worker делает тяжёлую работу в фоне.
- Billing отвечает за деньги.
- Dashboard показывает статистику.

Самая важная мысль:

кредиты не списываются в HTTP-запросе. Они списываются только после успешного результата worker-а.

## Как работает запрос пользователя шаг за шагом

### Регистрация

1. Пользователь вызывает `POST /api/v1/auth/register`.
2. Backend создаёт пользователя и стартовый баланс.
3. Backend возвращает `access_token` и `refresh_token`.

### Пополнение

1. Пользователь вызывает `POST /api/v1/billing/payments`.
2. Backend создаёт запись `payment`.
3. Backend создаёт credit-транзакцию.
4. Баланс увеличивается.

### Загрузка модели

1. Пользователь отправляет `model.pkl`.
2. Backend проверяет расширение, размер и валидность `scikit-learn` модели.
3. Файл сохраняется на диск.
4. В БД появляется запись о модели.

### Prediction

1. Пользователь вызывает `POST /api/v1/predictions`.
2. Backend проверяет, что модель принадлежит пользователю.
3. Backend проверяет баланс и фиксирует цену prediction со скидкой.
4. Backend ставит задачу в Celery и сразу отвечает `202`.
5. Worker загружает модель и считает результат.
6. Если всё успешно, worker списывает кредиты.
7. Если ошибка, prediction становится `failed`, а баланс остаётся прежним.

## Где что лежит и зачем

```text
backend/app/
  api/             # все HTTP endpoints
  billing.py       # кредиты, платежи, транзакции
  config.py        # env-настройки
  db.py            # engine и SessionLocal
  log_config.py    # логирование
  loyalty.py       # уровни и скидки
  main.py          # FastAPI приложение
  metrics.py       # Prometheus metrics
  middleware.py    # rate limit и API-метрики
  ml.py            # загрузка модели и prediction
  models.py        # ORM таблицы
  schemas.py       # схемы запросов/ответов
  security.py      # JWT и пароли
  worker.py        # Celery задачи

dashboard/
  main.py          # точка входа dashboard
  api_client.py    # запросы к backend
  views.py         # вкладки панели

infra/
  docker/          # Dockerfiles
  monitoring/      # Prometheus и Grafana

tests/
  unit/            # быстрые тесты по модулям
  integration/     # сценарии API + БД + worker
  e2e/             # проверки живого docker-стека
```

## Как локально что-то поменять и не сломать

Нормальный рабочий порядок такой:

1. Запусти `make smoke`, чтобы понять, что базовый сценарий жив.
2. Меняй один файл или одну небольшую связку файлов.
3. Сразу запускай `make test`.
4. Если трогал Docker, Celery, monitoring или dashboard, потом запускай `make e2e`.

Полезное правило:

- меняешь `billing.py` — проверь billing и prediction тесты;
- меняешь `auth.py` или `security.py` — проверь auth и admin доступ;
- меняешь `worker.py` — проверь integration flow;
- меняешь `docker-compose.yml` или `infra/monitoring` — проверь e2e.

## Как дебажить

Если что-то не работает, смотри в таком порядке:

1. `GET /health`
2. `GET /docs`
3. логи backend
4. логи celery
5. `GET /metrics`
6. Prometheus targets
7. Grafana health

Если prediction ломается, обычно проблема в одном из мест:

- модель невалидна;
- очередь недоступна;
- кредиты закончились;
- worker не может прочитать файл модели;
- упала БД или Redis.

## Как запускать тесты и что они проверяют

```bash
make test
make smoke
make e2e
```

Что проверяют тесты:

- auth, JWT и роли;
- загрузку модели;
- создание prediction;
- успешное выполнение worker;
- списание кредитов только после успеха;
- rollback при ошибках;
- loyalty tiers и месячный пересчёт;
- health, metrics и openapi;
- живой docker stack и monitoring.

## Самая полезная короткая формула

Чтобы не теряться, думай так:

`API создаёт задачу -> worker считает -> billing списывает только после успеха`

Если держать в голове эту формулу, проект читается очень быстро.
