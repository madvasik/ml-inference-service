# Scripts

Поддерживаемые скрипты проекта сейчас находятся в `scripts/testing/`.

## Актуальная структура

```text
scripts/
  testing/
    run_all_e2e_tests.sh
    test_no_crashes.py
    test_real_world_scenarios.py
    test_grafana_consistency.py
    README_E2E_TESTS.md
  scripts_backup/
    ... архивные и больше не поддерживаемые утилиты
```

## Основные сценарии

### Запуск всех E2E проверок

```bash
BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
bash scripts/testing/run_all_e2e_tests.sh
```

### Smoke на отсутствие падений

```bash
BASE_URL=http://localhost:8000 python3 scripts/testing/test_no_crashes.py
```

### Реальные пользовательские сценарии

```bash
BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
python3 scripts/testing/test_real_world_scenarios.py
```

### Проверка Grafana / Prometheus consistency

```bash
BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
GRAFANA_USER=admin \
GRAFANA_PASSWORD=admin \
python3 scripts/testing/test_grafana_consistency.py
```

## Важно

- Эти скрипты рассчитаны на уже поднятый стек через `docker compose up -d --build`.
- Для admin-проверок используется seed admin из `.env`: `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD`.
- `scripts/scripts_backup/` оставлен как архив старых утилит и не должен считаться актуальной документацией проекта.
