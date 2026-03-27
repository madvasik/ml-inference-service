PYTHON ?= $(if $(wildcard venv/bin/python),venv/bin/python,python3)
PYTEST ?= $(PYTHON) -m pytest

.PHONY: test test-unit smoke stack-up stack-down e2e clean

test:
	$(PYTEST)

test-unit:
	$(PYTEST) tests/unit tests/integration

smoke:
	$(PYTHON) tools/smoke.py

stack-up:
	docker compose up -d --build

stack-down:
	docker compose down

e2e:
	BASE_URL=$${BASE_URL:-http://localhost:8000} \
	PROMETHEUS_URL=$${PROMETHEUS_URL:-http://localhost:9090} \
	GRAFANA_URL=$${GRAFANA_URL:-http://localhost:3000} \
	GRAFANA_USER=$${GRAFANA_USER:-admin} \
	GRAFANA_PASSWORD=$${GRAFANA_PASSWORD:-admin} \
	$(PYTEST) tests/e2e -m e2e -o addopts='-v --strict-markers'

clean:
	rm -rf var/smoke_models var/reports
	rm -f var/smoke.db
