#!/bin/bash
# Комплексное тестирование всех систем

echo "======================================================================"
echo "КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ ML INFERENCE SERVICE"
echo "======================================================================"
echo ""

BASE_URL=${BASE_URL:-"http://localhost:8000"}

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

if curl -s -f "http://localhost:9090/-/healthy" > /dev/null; then
    success "Prometheus доступен"
else
    warning "Prometheus недоступен"
fi

if curl -s -f "http://localhost:3000/api/health" > /dev/null; then
    success "Grafana доступна"
else
    warning "Grafana недоступна"
fi

echo ""
log "======================================================================"
log "ШАГ 1: Запуск пользовательских флоу"
log "======================================================================"
python3 scripts/testing/test_user_flows.py

echo ""
log "======================================================================"
log "ШАГ 2: Дополнительная симуляция активности"
log "======================================================================"
BASE_URL="${BASE_URL}" python3 scripts/simulation/simulate_activity.py

echo ""
log "Ожидание обработки предсказаний (10 секунд)..."
sleep 10

echo ""
log "======================================================================"
log "ШАГ 3: Проверка Streamlit и метрик"
log "======================================================================"
python3 scripts/testing/verify_streamlit_and_metrics.py

echo ""
log "======================================================================"
log "ИТОГОВАЯ СВОДКА"
log "======================================================================"
log ""
log "📊 Проверьте следующие системы:"
log ""
log "1. Streamlit Admin Panel:"
log "   URL: http://localhost:8501"
log "   Логин: admin@mlservice.com / admin123"
log "   Проверьте:"
log "   - Отображение пользователей"
log "   - Отображение предсказаний (с фильтрами)"
log "   - Отображение транзакций (с фильтрами)"
log "   - Статистику"
log ""
log "2. Prometheus:"
log "   URL: http://localhost:9090"
log "   Проверьте запросы:"
log "   - active_users"
log "   - sum(prediction_requests_total)"
log "   - billing_transactions_total"
log ""
log "3. Grafana:"
log "   URL: http://localhost:3000"
log "   Логин: admin / admin"
log "   Проверьте:"
log "   - Data Sources → Prometheus должен быть 'Success'"
log "   - Dashboards должны отображать данные"
log ""
log "======================================================================"
success "Тестирование завершено!"
log "======================================================================"
