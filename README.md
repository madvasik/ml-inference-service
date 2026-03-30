# ML Inference Service

Масштабируемый ML-сервис (**`ml_inference_service`**): предсказания по загружаемым моделям **scikit-learn**, внутренняя валюта (**кредиты**), асинхронная обработка (**Celery + Redis**), дашборд **Streamlit**, мониторинг **Prometheus + Grafana**.

Краткий бизнес-контекст и финмодель: **[BUSINESS_PLAN.md](BUSINESS_PLAN.md)**.

### Структура репозитория


| Путь                        | Назначение                                                       |
| --------------------------- | ---------------------------------------------------------------- |
| `src/ml_inference_service/` | Устанавливаемый Python-пакет: FastAPI, SQLAlchemy-модели, Celery |
| `streamlit/`                | Дашборд Streamlit                                                |
| `alembic/`                  | Миграции Alembic                                                 |
| `docker/`                   | Скрипты entrypoint, Prometheus, Grafana                          |
| `scripts/`                  | Утилиты и демо-сценарии                                          |
| `tests/`                    | pytest                                                           |


Импорты в коде — `ml_inference_service.*` (пакет в каталоге `src/`, см. `pyproject.toml`).

---

## 1. Цель проекта

Дать пользователям API для **загрузки своих моделей** и **выполнения предсказаний** с **автоматическим списанием кредитов** только за **успешно завершённые** задачи; API остаётся отзывчивым за счёт очереди задач и горизонтального масштабирования воркеров.

---

## 2. Функциональные требования

### Пользовательский блок

- **Регистрация** и **вход** (`POST /api/auth/register`, `POST /api/auth/login`), выдача **JWT**.
- Роли: **user** (по умолчанию), **admin** (создание промокодов и др.; назначение вручную в БД, см. ниже).
- **Личный кабинет** на **Streamlit**: баланс, статистика, mock-пополнение, модели, предсказание, промокоды.

### ML-блок

- Загрузка артефакта **scikit-learn** (`.joblib` / `.pkl`), валидация наличия `predict`.
- **Асинхронные** предсказания: `POST /api/predict` ставит задачу, результат — `GET /api/jobs/{id}` (воркер **Celery** не блокирует HTTP-запросы API).

### Биллинговый блок

- Учёт **баланса** в кредитах, журнал **`credit_transactions`**.
- Списание **после успешного** инференса, с **идемпотентностью** (повтор не списывает дважды).
- **Пополнение в учебной сборке**: `POST /api/billing/mock-topup` с секретом `MOCK_TOPUP_SECRET` (имитация платежа). Интеграция с реальным платёжным шлюзом вынесена в продуктовую дорожку (см. [BUSINESS_PLAN.md](BUSINESS_PLAN.md)).

### Аналитический блок

- **Streamlit**: сводка по задачам, транзакции, расход кредитов.
- **GET /api/analytics/summary** для агрегатов по пользователю.

### API

- **REST API**, автоматическая документация **OpenAPI/Swagger**: **`/docs`**, **`/redoc`**.

---

## 3. Технологический стек


| Компонент  | Технология                                                                                 |
| ---------- | ------------------------------------------------------------------------------------------ |
| Язык       | Python 3.11+                                                                               |
| Web / API  | FastAPI, Uvicorn                                                                           |
| ML         | scikit-learn, joblib                                                                       |
| БД         | PostgreSQL, SQLAlchemy 2, Alembic                                                          |
| Очередь    | Celery, Redis                                                                              |
| UI         | Streamlit                                                                                  |
| Контейнеры | Docker, Docker Compose                                                                     |
| Мониторинг | Prometheus, Grafana, `prometheus-fastapi-instrumentator`                                   |
| Тесты      | pytest, pytest-cov (порог покрытия `ml_inference_service` **≥ 70%**, см. `pyproject.toml`) |


Секреты и URL БД/Redis задаются через **переменные окружения** (шаблон: `[.env.example](.env.example)`).

---

## 4. Этапы реализации (соответствие репозитория)


| Этап                 | Содержание                                                                              |
| -------------------- | --------------------------------------------------------------------------------------- |
| Проектирование       | Схема БД (Alembic), маршруты в `ml_inference_service/api/`, описание в README и Swagger |
| Backend              | Аутентификация, пользователи, биллинг, ML, промокоды, аналитика                         |
| ML-интеграция        | Задачи `ml_inference_service/tasks/predict.py`, брокер Redis, воркер в Docker Compose   |
| Биллинг              | `ml_inference_service/services/billing.py`, транзакции, дебет после успеха              |
| Интерфейс            | `streamlit/dashboard.py`                                                                |
| Инфраструктура       | `docker-compose.yml`, Prometheus, Grafana provisioning                                  |
| Тесты и документация | `tests/`, этот README, бизнес-план                                                      |


---

## 5. Промокоды

- Типы: **фиксированные кредиты** (`fixed_credits`), **процент бонуса к следующему пополнению** (`percent_next_topup`).
- Ограничения: **срок действия** (`expires_at`), **лимит активаций** (`max_activations` — глобально по коду).
- Повторная активация **одним пользователем** одного и того же кода блокируется записью в **`promocode_redemptions`** (ответ API **409**).
- Создание кодов: **`POST /api/promocodes/admin`** (только **admin**). В миграции зашит демо-код **`WELCOME`**.

---

## 6. Критерии приёмки (чек-лист)


| Критерий                               | Реализация                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------- |
| JWT, роли                              | Есть (`ml_inference_service/deps.py`, JWT в `ml_inference_service/security.py`) |
| Атомарность / идемпотентность списаний | Заложено в сервисе биллинга и задаче предсказания                               |
| ML асинхронно (не блокирует API)       | Celery-воркер обрабатывает задачи вне процесса API                              |
| Swagger для эндпоинтов                 | FastAPI автоматически                                                           |
| Запуск одной командой                  | `docker compose up --build` (после `cp .env.example .env`)                      |
| Grafana / метрики                      | Дашборд «ML Inference API», метрики с `/metrics`                                |
| Покрытие тестами **> 70%**             | Порог в `pyproject.toml`                                                        |
| Краткий бизнес-план                    | [BUSINESS_PLAN.md](BUSINESS_PLAN.md)                                            |


### Рекомендации для разработки (из ТЗ)

- **Сбой при списании**: транзакции БД и идемпотентные ключи; при ошибке до `commit` откат без списания.
- **Секреты**: только env / `.env`, не коммитить ключи (см. `.env.example`).
- **Документация биллинга**: README, [BUSINESS_PLAN.md](BUSINESS_PLAN.md), комментарии в `ml_inference_service/services/billing.py`.

---

## Запуск (Docker)

```bash
cp .env.example .env
docker compose up --build
```

### Ссылки после `docker compose` (порты на хосте смотрите в `docker-compose.yml`)


| Сервис                 | URL                                                            | Примечание                                                                     |
| ---------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **API (Swagger)**      | [http://localhost:8001/docs](http://localhost:8001/docs)       | при другом `ports` у `api` замените порт                                       |
| **Метрики приложения** | [http://localhost:8001/metrics](http://localhost:8001/metrics) | текст для Prometheus (не UI Grafana)                                           |
| **Streamlit**          | [http://localhost:8502](http://localhost:8502)                 | регистрация, вход, статистика, mock-пополнение, модели, предсказание, промокод |
| **Prometheus UI**      | [http://localhost:19090](http://localhost:19090)               | запросы PromQL, targets                                                        |
| **Grafana**            | [http://localhost:3001](http://localhost:3001)                 | логин `admin`, пароль `GRAFANA_ADMIN_PASSWORD` или `admin`                     |
| **PostgreSQL**         | `localhost:5433`                                               | внутри сети compose: `postgres:5432`                                           |


В **Grafana**: **Dashboards** → **ML Inference API** — пользователи, успешные предсказания, модели, успешность предсказаний (success rate).

Страница `/metrics` — сырой экспорт; графики — в **Grafana** или **Prometheus UI**.

**Streamlit:** не используйте выдуманные `admin/admin`. Зарегистрируйте пользователя на вкладке **«Регистрация»**, затем войдите на **«Вход»**.

---

## Роли

По умолчанию регистрация создаёт роль `user`. Администратора:

```sql
UPDATE users SET role = 'admin' WHERE email = 'you@example.com';
```

---

## Тесты

- **Покрытие** кода: **~93%**.
- **Количество** тестов: **23** (все в каталоге `tests/`).

