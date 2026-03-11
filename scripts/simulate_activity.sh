#!/bin/bash
# Скрипт для симуляции активности пользователей через curl

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "🚀 Начало симуляции активности пользователей"
echo "🌐 API URL: $BASE_URL"
echo "============================================================"

# Функция для входа и получения токена
login() {
    local email=$1
    local password=$2
    curl -s -X POST "$BASE_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"$password\"}" | \
        grep -o '"access_token":"[^"]*' | cut -d'"' -f4
}

# Функция для получения моделей пользователя
get_models() {
    local token=$1
    local response=$(curl -s -X GET "$BASE_URL/api/v1/models" \
        -H "Authorization: Bearer $token")
    echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); models=data.get('models', data) if isinstance(data, dict) else data; print('\n'.join([str(m['id']) for m in models])) if isinstance(models, list) else print('')" 2>/dev/null
}

# Функция для создания предсказания
create_prediction() {
    local token=$1
    local model_id=$2
    local feature1=$3
    local feature2=$4
    
    curl -s -X POST "$BASE_URL/api/v1/predictions" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -d "{\"model_id\":$model_id,\"input_data\":{\"feature1\":$feature1,\"feature2\":$feature2}}" \
        -w "\nHTTP_CODE:%{http_code}"
}

# Учетные данные пользователей (email:password)
USERS=(
    "admin@mlservice.com:admin123"
    "user1@example.com:user123"
    "user2@example.com:user123"
    "user3@example.com:user123"
    "user4@example.com:user123"
    "user5@example.com:user123"
)

TOTAL_REQUESTS=0

# Симулируем активность для каждого пользователя
for user_cred in "${USERS[@]}"; do
    email=$(echo "$user_cred" | cut -d: -f1)
    password=$(echo "$user_cred" | cut -d: -f2)
    
    echo ""
    echo "👤 Пользователь: $email"
    
    # Вход
    token=$(login "$email" "$password")
    if [ -z "$token" ]; then
        echo "   ⚠️  Не удалось войти"
        continue
    fi
    
    # Получаем модели
    models=$(get_models "$token")
    if [ -z "$models" ]; then
        echo "   ⚠️  У пользователя нет моделей"
        continue
    fi
    
    # Выбираем первую модель
    model_id=$(echo "$models" | head -1)
    echo "   🤖 Используем модель ID: $model_id"
    
    # Создаем случайное количество запросов (5-20)
    num_requests=$((RANDOM % 16 + 5))
    echo "   📊 Создаем $num_requests запросов..."
    
    success=0
    errors=0
    
    for i in $(seq 1 $num_requests); do
        # Случайная задержка между запросами
        if [ $i -gt 1 ]; then
            sleep $(echo "scale=2; $RANDOM/32768*2" | bc)
        fi
        
        # Генерируем случайные входные данные
        feature1=$(echo "scale=2; $RANDOM/3276.8" | bc)
        feature2=$(echo "scale=2; $RANDOM/3276.8" | bc)
        
        result=$(create_prediction "$token" "$model_id" "$feature1" "$feature2")
        http_code=$(echo "$result" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
        
        if [ "$http_code" = "202" ]; then
            success=$((success + 1))
            prediction_id=$(echo "$result" | grep -o '"prediction_id":[0-9]*' | cut -d: -f2)
            echo "   ✅ Запрос #$i: создано предсказание $prediction_id"
        else
            errors=$((errors + 1))
            echo "   ❌ Запрос #$i: ошибка (HTTP $http_code)"
        fi
        
        TOTAL_REQUESTS=$((TOTAL_REQUESTS + 1))
    done
    
    echo "   📈 Итого: $success успешных, $errors ошибок"
    
    # Небольшая пауза между пользователями
    sleep 1
done

echo ""
echo "============================================================"
echo "✅ Симуляция завершена!"
echo "📊 Всего создано запросов: $TOTAL_REQUESTS"
echo "💡 Проверьте Grafana для просмотра метрик"
echo "💡 Проверьте статус предсказаний: python3 scripts/check_pending.py"
