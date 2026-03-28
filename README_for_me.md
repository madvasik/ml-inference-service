# ML Inference Service — подробный гайд

Это ML-сервис. Пользователь загружает свою scikit-learn модель (.pkl), отправляет данные, получает предсказание и платит за него кредитами. Всё крутится на FastAPI + Celery + PostgreSQL + Redis.

---

## Как работает запрос от начала до конца

```
1. POST /api/v1/auth/register      -> создаётся User + Balance (0 кредитов)
2. POST /api/v1/billing/payments    -> mock-платёж, кредиты зачисляются на баланс
3. POST /api/v1/models/upload       -> .pkl файл проверяется (sklearn?), сохраняется на диск + запись в БД
4. POST /api/v1/predictions         -> проверяется баланс, фиксируется цена со скидкой,
                                       создаётся Prediction (status=PENDING),
                                       задача ставится в очередь Celery, возвращается 202
5. Celery worker (execute_prediction):
   - блокирует prediction через with_for_update()
   - загружает модель с диска (ml.py)
   - делает model.predict()
   - блокирует баланс через with_for_update()
   - списывает кредиты (billing.py → charge_prediction)
   - сохраняет результат, ставит status=COMPLETED
6. GET /api/v1/predictions/{id}     -> пользователь получает результат и status
```

Ключевой принцип: **оплата только за успешный inference**. Если worker упал, модель сломана или не хватило кредитов — prediction получает status=FAILED, баланс не меняется.

---

## Структура проекта по папкам

### `backend/app/` — ядро сервиса

#### Точка входа и конфигурация

| Файл | Зачем |
|------|-------|
| `main.py` | Главный файл — здесь запускается сервер. Собирает всё вместе: подключает все API-роуты, включает защиту от спама (rate limit) и сбор статистики. При первом старте создаёт таблицы в БД и добавляет admin-аккаунт |
| `config.py` | Читает настройки из файла `.env` (пароли, ключи, адреса). Весь код берёт настройки только отсюда — менять конфиг в одном месте |
| `db.py` | Отвечает за подключение к базе данных. Проверяет что БД живая и таблицы на месте. Даёт каждому запросу своё соединение с БД |
| `log_config.py` | Настраивает логи. Можно писать в обычном тексте или в JSON (для продакшена) |

#### ORM и схемы

| Файл | Зачем |
|------|-------|
| `models.py` | Описание всех 7 таблиц в БД: **User** (аккаунт), **Balance** (кредиты), **Payment** (пополнения), **Transaction** (история списаний и зачислений), **MLModel** (загруженные модели), **Prediction** (запросы на предсказание), **LoyaltyTierRule** (правила скидок) |
| `schemas.py` | Описание того, что принимает и возвращает API. Например, как выглядит запрос на регистрацию или ответ с балансом |

#### Бизнес-логика

| Файл | Зачем |
|------|-------|
| `security.py` | Всё про авторизацию: создание и проверка JWT-токенов, хэширование паролей. Отвечает на вопрос «кто этот пользователь и есть ли у него права» |
| `billing.py` | Вся логика денег: пополнение баланса (зачисляет кредиты и записывает транзакцию), списание за предсказание (проверяет хватает ли кредитов, снимает деньги). Всё атомарно — либо всё прошло, либо ничего |
| `loyalty.py` | Система скидок. Чем больше предсказаний сделал за месяц — тем выше уровень (Bronze/Silver/Gold) и тем дешевле следующие предсказания. Пересчитывается автоматически 1-го числа |
| `ml.py` | Работа с моделями: проверить что .pkl файл — настоящая sklearn-модель, загрузить её с диска, запустить предсказание и вернуть результат |
| `worker.py` | Фоновый обработчик задач. Берёт предсказание из очереди, считает результат, списывает кредиты. Если что-то пошло не так — пробует ещё 3 раза. Также раз в месяц пересчитывает loyalty-уровни |
| `middleware.py` | Перехватывает каждый запрос до того, как он дойдёт до API. Считает скорость запросов (не даёт спамить), замеряет время выполнения для статистики |
| `metrics.py` | Список всех счётчиков и метрик, которые собирает Prometheus (количество предсказаний, ошибок, активных пользователей и т.д.) |

#### HTTP endpoints (`backend/app/api/`)

| Файл | Endpoints | Что делает |
|------|-----------|-----------|
| `auth.py` | `POST /register`, `POST /login`, `POST /refresh` | Регистрация, вход и обновление токена. После регистрации сразу выдаёт токены — отдельный логин не нужен |
| `users.py` | `GET /users/me` | Информация о себе: email, роль, loyalty-уровень и текущая скидка |
| `models.py` | `POST /upload`, `GET /`, `GET /{id}`, `DELETE /{id}` | Загрузить .pkl, посмотреть список своих моделей, получить детали, удалить. Чужие модели недоступны |
| `predictions.py` | `POST /`, `GET /`, `GET /{id}` | Создать предсказание (ставит в очередь, сразу возвращает 202), посмотреть статус и результат. Чужие предсказания недоступны |
| `billing.py` | `GET /balance`, `POST /payments`, `GET /payments`, `GET /transactions` | Баланс, пополнение кредитов, история платежей и транзакций |
| `admin.py` | `GET /users`, `GET /users/{id}`, `GET /predictions`, `GET /predictions/{id}`, `GET /transactions`, `GET /payments` | Только для администратора. Видит всех пользователей, все предсказания и транзакции. Можно фильтровать по конкретному пользователю |
| `system.py` | `GET /`, `GET /health`, `GET /metrics` | Статус сервера, проверка здоровья БД, метрики для Prometheus |

---

### `dashboard/` — Streamlit админ-панель

| Файл | Зачем |
|------|-------|
| `main.py` | Запускает веб-интерфейс. Показывает форму входа, после логина — 5 вкладок с данными |
| `views.py` | Код каждой вкладки: **Users** (таблица пользователей, график регистраций), **Predictions** (статусы, фильтры, timeline по дням), **Payments** (история платежей, диаграмма), **Transactions** (зачисления vs списания), **Stats** (топ-10 активных, распределение по loyalty, активность по часам) |
| `api_client.py` | Ходит в backend по HTTP и достаёт данные для каждой вкладки. Хранит токен между запросами |
| `config.py` | Адрес backend-а |

---

### `infra/` — Docker и мониторинг

| Путь | Зачем |
|------|-------|
| `docker/backend/Dockerfile` | Инструкция по сборке контейнера для API-сервера |
| `docker/celery/Dockerfile` | Инструкция по сборке контейнера для фонового обработчика задач |
| `docker/streamlit/Dockerfile` | Инструкция по сборке контейнера для admin-панели |
| `monitoring/prometheus/prometheus.yml` | Говорит Prometheus куда ходить за метриками: API-сервер (порт 8000) и worker (порт 9091), каждые 15 секунд |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | Автоматически подключает Prometheus как источник данных в Grafana при старте |
| `monitoring/grafana/provisioning/dashboards/dashboard.yml` | Говорит Grafana где лежит JSON с дашбордом, чтобы он появился автоматически |
| `monitoring/grafana/dashboards/ml_service_dashboard.json` | Сам дашборд: графики throughput, latency, success rate, биллинг, loyalty |

---

### `tests/` — три уровня тестов

#### `tests/conftest.py` — общие фикстуры

Готовые «заготовки» для тестов, чтобы не писать одно и то же в каждом файле:
- `db_session` — чистая база данных в памяти для каждого теста (SQLite, не нужна PostgreSQL)
- `client` — фейковый HTTP-клиент, который вызывает API без реального сервера
- `test_user` — готовый пользователь с 1000 кредитов
- `admin_user` — пользователь с правами администратора
- `access_token_for(user)` — генерирует JWT-токен для любого пользователя
- `test_model_file` — готовый .pkl файл с обученной RandomForest-моделью
- `test_ml_model` — запись о модели в БД + файл на диске

#### `tests/helpers.py` — вспомогательные функции

- `unique_email(prefix)` — генерирует уникальный email, чтобы тесты не конфликтовали
- `auth_headers(token)` — формирует заголовок `Authorization: Bearer ...` для запросов
- `temporary_model_file()` — создаёт временный .pkl файл на время теста, потом удаляет
- `wait_for_prediction(fetch, id)` — ждёт пока предсказание завершится (для e2e-тестов)

#### `tests/unit/` — 48 тестов, 9 файлов

| Файл | Кол-во | Что проверяет |
|------|--------|--------------|
| `test_app.py` | 6 | root, health (ok + db failure), metrics, openapi paths, logging (handler reuse + JSON format) |
| `test_auth_api.py` | 8 | register → login → refresh → me flow; duplicate email; wrong password; refresh rejects access token; malformed subject; no auth → 401; invalid token → 401; rate limit headers |
| `test_admin_api.py` | 2 | admin может читать users/predictions/payments/transactions; non-admin получает 403 |
| `test_billing.py` | 4 | payment добавляет кредиты + транзакцию; rollback при ошибке; charge_prediction идемпотентен; amount ≤ 0 отвергается |
| `test_loyalty.py` | 3 | seed правил (Bronze/Silver/Gold) создаётся один раз; monthly recalculation считает прошлый месяц; prediction_cost_snapshot применяет скидку |
| `test_ml.py` | 14 | validate (sklearn ok, non-sklearn reject, missing file); load (ok, missing, non-sklearn); get_model_type (classifier, regressor, KMeans); predict (с probabilities, без, invalid input); prepare_features (с именами и без) |
| `test_models_api.py` | 3 | upload → list → get → delete; reject invalid extension; access scoped to owner |
| `test_predictions_api.py` | 4 | creation сохраняет discount snapshot; requires balance; queue failure → status=FAILED + no transaction; scoped to owner |
| `test_worker.py` | 4 | success → debit once; insufficient credits → failed; model load error → no charge; monthly loyalty task |

#### `tests/integration/` — 3 теста, 1 файл

| Файл | Что проверяет |
|------|--------------|
| `test_workflow.py` | **Полный workflow**: register → fund 100 → upload → predict → worker → balance=90, 2 transactions. **Queue failure**: delay бросает RuntimeError → prediction=FAILED, reason=queue_unavailable, 0 transactions. **Worker failure**: load_model бросает ValueError → result=failed, balance=1000, 0 transactions |

#### `tests/e2e/` — 33 теста, 6 файлов (нужен `docker compose up`)

| Файл | Кол-во | Что проверяет |
|------|--------|--------------|
| `test_system.py` | 8 | health (status + components); root (version); metrics (все counters); docs + openapi paths; monitoring stack (Prometheus targets up, worker metrics); Grafana (health, datasource, proxied query); provisioned dashboard (uid, title); Streamlit доступен |
| `test_auth.py` | 6 | register → login → refresh → me flow; duplicate email → 400; wrong password → 401; invalid refresh token → 401; protected endpoints require auth (6 endpoints); user profile shows loyalty_tier=none |
| `test_billing.py` | 3 | payment → balance → transactions history; amount=0 и amount=-10 → 400; два платежа (30+20) → balance=50, total=2 |
| `test_models.py` | 4 | upload → list → get → delete → 404; .csv → 400; invalid .pkl bytes → 400; .txt → 400 |
| `test_predictions.py` | 8 | полный workflow (register → fund → upload → predict → wait → verify balance + transactions); zero balance → 402; nonexistent model → 404; foreign model → 404; own model + zero balance → 402; scoped to user (user B не видит prediction user A); 3 predictions → balance=70, 3 debits; deleted model → 404 |
| `test_admin.py` | 4 | admin видит users/payments/transactions; admin фильтрует predictions/transactions по user_id + видит user detail + prediction detail; nonexistent user → 404; non-admin → 403 |

---

### `tools/`

| Файл | Зачем |
|------|-------|
| `smoke.py` | Быстрая проверка что всё работает — без Docker. Запускает сервер на SQLite, прогоняет сценарий регистрация → пополнение → загрузка модели → предсказание, проверяет результат и останавливает сервер |

---

### Корневые файлы

| Файл | Зачем |
|------|-------|
| `docker-compose.yml` | Запускает все 8 сервисов одной командой. Папка `./var/ml_models` с файлами моделей расшарена между API-сервером, worker-ом и планировщиком |
| `Makefile` | Короткие псевдонимы для длинных команд: `make test`, `make e2e`, `make smoke`, `make stack-up` и т.д. |
| `pytest.ini` | Настройки тестов: где искать тесты, минимальное покрытие 70%, пометка для e2e-тестов |
| `.env.example` | Шаблон с примерами всех настроек — скопировать в `.env` и заполнить |
| `backend/requirements.txt` | Список всех Python-библиотек проекта |

---

## Как запускать

### Весь стек (Docker)

```bash
cp .env.example .env        # скопировать конфиг
docker compose up -d --build # поднять все 8 сервисов
```

После этого доступно:
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Dashboard: http://localhost:8501 (admin@mlservice.com / admin123)
- Grafana: http://localhost:3000 (admin / admin)
- Prometheus: http://localhost:9090

Остановить: `docker compose down`

### Smoke-тест (без Docker)

```bash
source venv/bin/activate
make smoke
```

Поднимает локальный сервер на SQLite и прогоняет основной сценарий.

---

## Как тестировать

```bash
source venv/bin/activate

make test          # unit + integration (51 тест, ~16 сек, покрытие 87%)
make e2e           # e2e тесты (33 теста, нужен docker compose up)
make smoke         # smoke без Docker

# Один конкретный тест:
venv/bin/python -m pytest tests/unit/test_billing.py::test_charge_prediction_is_idempotent -v
```

Unit/integration тесты работают на SQLite in-memory — PostgreSQL не нужен.
E2e тесты бьют по живому Docker-стеку через HTTP.

---

## Как попробовать API руками (через Swagger)

1. Открой http://localhost:8000/docs
2. Нажми `POST /api/v1/auth/register` → Try it out → введи email и password → Execute
3. Скопируй `access_token` из ответа
4. Нажми кнопку "Authorize" вверху страницы → вставь токен → Authorize
5. `POST /api/v1/billing/payments` → `{"amount": 50}` → Execute
6. `POST /api/v1/models/upload` → выбери .pkl файл и введи model_name → Execute
7. `POST /api/v1/predictions` → `{"model_id": 1, "input_data": {"feature1": 1, "feature2": 2}}` → Execute
8. Подожди пару секунд, потом `GET /api/v1/predictions/{prediction_id}` → должен быть status=completed
9. `GET /api/v1/billing/balance` → баланс уменьшился на стоимость prediction

---

## Сценарий для записи демо

### Подготовка (до записи)

```bash
docker compose down -v          # чистый старт
docker compose up -d --build    # поднять стек
```

Подготовь .pkl файл заранее:

```python
python3 -c "
import pickle, numpy as np
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(np.array([[1,2],[2,3],[3,4],[4,5]]), np.array([0,0,1,1]))
pickle.dump(model, open('demo_model.pkl', 'wb'))
print('Готово: demo_model.pkl')
"
```

### Сценарий записи (~5-7 минут)

**1. Показать архитектуру (30 сек)**
- Открой `docker-compose.yml`, покажи 8 сервисов
- Открой http://localhost:8000/health — покажи что всё healthy

**2. Регистрация и авторизация (1 мин)**
- Открой Swagger http://localhost:8000/docs
- `POST /register` с email и паролем → покажи access_token + refresh_token
- Авторизуйся через кнопку Authorize
- `GET /users/me` → покажи профиль (role=user, loyalty_tier=none)

**3. Биллинг (1 мин)**
- `GET /billing/balance` → покажи что credits=0
- `POST /billing/payments` → `{"amount": 100}` → покажи что credits=100
- `GET /billing/transactions` → покажи credit-транзакцию

**4. Загрузка модели (1 мин)**
- `POST /models/upload` → загрузи .pkl файл
- `GET /models` → покажи список (model_type=classification)
- Попробуй загрузить .txt → покажи ошибку 400

**5. Предсказание (2 мин)**
- `POST /predictions` → `{"model_id": 1, "input_data": {"feature1": 1, "feature2": 2}}`
- Покажи ответ 202 (accepted, prediction_id)
- `GET /predictions/{id}` → покажи status=completed, result, credits_spent
- `GET /billing/balance` → покажи что credits уменьшились (100 - 10 = 90)
- `GET /billing/transactions` → покажи debit-транзакцию
- Сделай ещё 1-2 предсказания, покажи что баланс уменьшается

**6. Попытка без денег (30 сек)**
- Создай нового пользователя (register), авторизуйся через Authorize
- Загрузи ему модель (`POST /models/upload`)
- `POST /predictions` без пополнения баланса → покажи ошибку 402 (insufficient credits)

**7. Админ-панель Streamlit (1 мин)**
- Открой http://localhost:8501
- Залогинься как admin@mlservice.com / admin123
- Покажи вкладки: Users (список), Predictions (статусы), Payments, Transactions, Stats

**8. Мониторинг (1 мин)**
- Открой http://localhost:8000/metrics → покажи Prometheus-метрики
- Открой Grafana http://localhost:3000 (admin/admin)
- Открой dashboard "ML Inference Service Dashboard" → покажи графики

**9. Тесты (30 сек)**
- Переключись в терминал
- `make test` → покажи что 51 тест зелёный, покрытие 87%
- Упомяни что есть ещё 33 e2e теста

### Если спросят на защите

- **Почему async?** — inference может занять секунды/минуты, нельзя блокировать HTTP-поток
- **Почему оплата после inference?** — пользователь платит только за результат, при ошибке кредиты не списываются
- **Как защита от race conditions?** — `with_for_update()` блокирует строку баланса в PostgreSQL
- **Как идемпотентность?** — charge_prediction проверяет наличие transaction по prediction_id, не списывает дважды
- **Зачем loyalty?** — стимулирует активное использование, чем больше predictions, тем дешевле
- **Почему snapshot цены?** — фиксируется при создании prediction, чтобы изменение правил не повлияло на уже созданные запросы
