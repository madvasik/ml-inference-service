#!/bin/bash
# Комплексный запуск всех E2E тестов реального использования

echo "======================================================================"
echo "КОМПЛЕКСНОЕ E2E ТЕСТИРОВАНИЕ РЕАЛЬНЫХ СЦЕНАРИЕВ"
echo "======================================================================"
echo ""

BASE_URL=${BASE_URL:-"http://localhost:8000"}
PROMETHEUS_URL=${PROMETHEUS_URL:-"http://localhost:9090"}
GRAFANA_URL=${GRAFANA_URL:-"http://localhost:3000"}

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}$1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Проверка доступности сервисов
log "Проверка доступности сервисов..."
if curl -s -f "${BASE_URL}/health" > /dev/null; then
    success "Backend доступен"
else
    error "Backend недоступен"
    exit 1
fi

if curl -s -f "${PROMETHEUS_URL}/-/healthy" > /dev/null; then
    success "Prometheus доступен"
else
    warning "Prometheus недоступен"
fi

if curl -s -f "${GRAFANA_URL}/api/health" > /dev/null; then
    success "Grafana доступна"
else
    warning "Grafana недоступна"
fi

echo ""
log "======================================================================"
log "ШАГ 1: Тест стабильности системы (отсутствие падений)"
log "======================================================================"
BASE_URL="${BASE_URL}" python3 scripts/testing/test_no_crashes.py
NO_CRASHES_EXIT=$?

echo ""
log "======================================================================"
log "ШАГ 2: Тест реальных пользовательских сценариев"
log "======================================================================"
BASE_URL="${BASE_URL}" PROMETHEUS_URL="${PROMETHEUS_URL}" GRAFANA_URL="${GRAFANA_URL}" \
    python3 scripts/testing/test_real_world_scenarios.py
SCENARIOS_EXIT=$?

echo ""
log "======================================================================"
log "ШАГ 3: Проверка согласованности с Grafana"
log "======================================================================"
BASE_URL="${BASE_URL}" PROMETHEUS_URL="${PROMETHEUS_URL}" GRAFANA_URL="${GRAFANA_URL}" \
    python3 scripts/testing/test_grafana_consistency.py
GRAFANA_EXIT=$?

echo ""
log "======================================================================"
log "ИТОГОВАЯ СВОДКА"
log "======================================================================"
log ""

TOTAL_TESTS=3
PASSED_TESTS=0

if [ $NO_CRASHES_EXIT -eq 0 ]; then
    success "Тест стабильности: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    error "Тест стабильности: FAILED"
fi

if [ $SCENARIOS_EXIT -eq 0 ]; then
    success "Тест реальных сценариев: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    error "Тест реальных сценариев: FAILED"
fi

if [ $GRAFANA_EXIT -eq 0 ]; then
    success "Тест согласованности Grafana: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    error "Тест согласованности Grafana: FAILED"
fi

echo ""
log "======================================================================"
if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    success "ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! ($PASSED_TESTS/$TOTAL_TESTS)"
    log "======================================================================"
    exit 0
else
    error "НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ ($PASSED_TESTS/$TOTAL_TESTS)"
    log "======================================================================"
    exit 1
fi
