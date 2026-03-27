# Testing

## Базовые команды

```bash
make test
make test-unit
make smoke
make e2e
```

Эквиваленты:

```bash
pytest
pytest tests/unit tests/integration
python tools/smoke.py
bash tools/e2e/run_all_e2e_tests.sh
```

## Что покрывает `pytest`

- auth и JWT
- загрузку и CRUD моделей
- prediction API и Celery tasks
- billing helpers и payment API
- loyalty service
- admin endpoints
- middleware и Prometheus metrics
- startup/health/exceptions

Текущий порог покрытия задается в `pytest.ini` и должен оставаться выше `70%`.

## E2E-скрипты

Скрипты из `tools/e2e/` требуют уже поднятый стек:

```bash
docker compose up -d --build
```

Примеры:

```bash
BASE_URL=http://localhost:8000 python3 tools/e2e/test_no_crashes.py

BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
python3 tools/e2e/test_real_world_scenarios.py

BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
GRAFANA_USER=admin \
GRAFANA_PASSWORD=admin \
python3 tools/e2e/test_grafana_consistency.py
```

## Полезные выборочные проверки

```bash
pytest tests/unit/test_billing.py
pytest tests/unit/test_predictions.py
pytest tests/unit/test_prediction_tasks.py
pytest tests/unit/test_loyalty_service.py
```

## Примечание по артефактам

Обычный `pytest` больше не пишет `htmlcov/` в корень репозитория. Если нужен HTML-отчет, запускайте его явно, например:

```bash
pytest --cov=backend/app --cov-report=html:var/reports/htmlcov
```
