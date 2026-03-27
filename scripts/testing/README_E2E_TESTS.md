# E2E Testing

Скрипты в этой папке проверяют end-to-end сценарии уже поднятого сервиса.

## Требования

- запущенный stack через `docker compose up -d --build`
- доступный backend на `BASE_URL`
- для расширенных проверок: Prometheus и Grafana
- seed admin из `.env`

## Команды

### Все e2e сразу

```bash
BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
bash scripts/testing/run_all_e2e_tests.sh
```

### Отсутствие падений

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

### Проверка Grafana consistency

```bash
BASE_URL=http://localhost:8000 \
PROMETHEUS_URL=http://localhost:9090 \
GRAFANA_URL=http://localhost:3000 \
GRAFANA_USER=admin \
GRAFANA_PASSWORD=admin \
python3 scripts/testing/test_grafana_consistency.py
```

## Что важно помнить

- `/api/v1/billing/topup` остается совместимым wrapper, но основной billing-flow теперь идет через payment intents.
- Лояльность и скидки влияют на стоимость prediction, поэтому в real-world тестах удобно отдельно смотреть `credits_spent`, `discount_amount` и payment history.
- Если Docker daemon недоступен, e2e smoke придется запускать позже на машине с рабочим Docker.
