# Tests

В проекте есть unit, integration и e2e уровни проверки.

## Структура

```text
tests/
  conftest.py
  unit/
  integration/
  e2e/
  utils/
```

## Основные команды

### Полный pytest suite

```bash
venv/bin/pytest
```

### Только unit/integration через pytest

```bash
venv/bin/pytest tests/unit
venv/bin/pytest tests/integration
```

### E2E/real-world проверки

Эти тесты требуют поднятые сервисы и находятся в `scripts/testing/` и `tests/e2e/`.

Примеры:

```bash
BASE_URL=http://localhost:8000 python3 scripts/testing/test_no_crashes.py

BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
python3 scripts/testing/test_real_world_scenarios.py
```

## Что покрыто

- JWT auth и permissions
- models upload / CRUD
- async prediction flow
- billing helpers и payment intents
- loyalty recalculation
- admin API
- middleware и metrics

## Полезные наборы

```bash
venv/bin/pytest tests/unit/test_billing.py
venv/bin/pytest tests/unit/test_predictions.py
venv/bin/pytest tests/unit/test_prediction_tasks.py
venv/bin/pytest tests/unit/test_loyalty_service.py
```

## Примечания

- Порог покрытия на `pytest` задан в `pytest.ini` и должен оставаться выше `70%`.
- Для локального запуска backend тестам не нужен поднятый Docker stack.
- Для full smoke через Docker используйте `docker compose up -d --build` и затем e2e-скрипты из `scripts/testing/`.
