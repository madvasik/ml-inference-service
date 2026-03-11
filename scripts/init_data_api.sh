#!/bin/bash
# Скрипт для инициализации тестовых данных через API эндпоинты

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "🚀 Начало инициализации данных через API..."
echo "🌐 API URL: $BASE_URL"
echo "============================================================"

# Проверка доступности API
if ! curl -s -f "$BASE_URL/health" > /dev/null; then
    echo "❌ API недоступен"
    echo "   Убедитесь, что сервис запущен: docker-compose up -d"
    exit 1
fi

echo "✅ API доступен"

# Функция для регистрации пользователя
register_user() {
    local email=$1
    local password=$2
    curl -s -X POST "$BASE_URL/api/v1/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"$password\"}" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null
}

# Функция для входа
login() {
    local email=$1
    local password=$2
    curl -s -X POST "$BASE_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"$password\"}" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null
}

# Функция для пополнения баланса
topup_balance() {
    local token=$1
    local amount=$2
    curl -s -X POST "$BASE_URL/api/v1/billing/topup" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -d "{\"amount\":$amount}" \
        -w "\nHTTP_CODE:%{http_code}"
}

# Функция для загрузки модели
upload_model() {
    local token=$1
    local model_file=$2
    local model_name=$3
    curl -s -X POST "$BASE_URL/api/v1/models/upload" \
        -H "Authorization: Bearer $token" \
        -F "file=@$model_file" \
        -F "model_name=$model_name" \
        -w "\nHTTP_CODE:%{http_code}"
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

# Создание администратора (напрямую в БД, так как нет API)
echo ""
echo "👤 Создание администратора..."
python3 << 'PYEOF'
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sqlalchemy.orm import Session
from backend.app.database.session import SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.balance import Balance
from backend.app.auth.security import get_password_hash

db: Session = SessionLocal()
try:
    admin = db.query(User).filter(User.email == "admin@mlservice.com").first()
    if admin:
        print(f"   ℹ️  Администратор уже существует: {admin.email} (ID: {admin.id})")
    else:
        admin = User(
            email="admin@mlservice.com",
            password_hash=get_password_hash("admin123"),
            role=UserRole.ADMIN
        )
        db.add(admin)
        db.flush()
        admin_balance = Balance(user_id=admin.id, credits=10000)
        db.add(admin_balance)
        db.commit()
        db.refresh(admin)
        print(f"   ✅ Администратор создан: {admin.email} (ID: {admin.id})")
        print(f"   💰 Баланс: {admin_balance.credits} кредитов")
finally:
    db.close()
PYEOF

# Создание тестовой модели
echo ""
echo "🤖 Создание тестовой ML модели..."
MODEL_FILE=$(python3 << 'PYEOF'
import pickle
import tempfile
import numpy as np
from sklearn.ensemble import RandomForestClassifier

X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
y = np.array([0, 1, 0, 1, 0])
model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(X, y)

temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
pickle.dump(model, temp_file)
temp_file.close()
print(temp_file.name)
PYEOF
)

# Создание пользователей через API
echo ""
echo "👥 Создание обычных пользователей через API..."
USERS=(
    "user1@example.com:user123:500"
    "user2@example.com:user123:1000"
    "user3@example.com:user123:750"
    "user4@example.com:user123:1500"
    "user5@example.com:user123:2000"
)

declare -A USER_TOKENS
declare -A USER_MODELS

for user_data in "${USERS[@]}"; do
    email=$(echo "$user_data" | cut -d: -f1)
    password=$(echo "$user_data" | cut -d: -f2)
    credits=$(echo "$user_data" | cut -d: -f3)
    
    echo ""
    echo "   Пользователь: $email"
    
    # Регистрация
    token=$(register_user "$email" "$password")
    if [ -z "$token" ]; then
        # Пробуем войти, если пользователь уже существует
        token=$(login "$email" "$password")
    fi
    
    if [ -z "$token" ]; then
        echo "   ❌ Не удалось зарегистрировать/войти"
        continue
    fi
    
    USER_TOKENS["$email"]=$token
    echo "   ✅ Пользователь зарегистрирован/вошел"
    
    # Пополнение баланса
    topup_result=$(topup_balance "$token" "$credits")
    http_code=$(echo "$topup_result" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    if [ "$http_code" = "200" ]; then
        balance=$(echo "$topup_result" | python3 -c "import sys, json; print(json.load(sys.stdin).get('credits', 0))" 2>/dev/null)
        echo "   💰 Баланс пополнен: $balance кредитов"
    else
        echo "   ⚠️  Ошибка пополнения баланса (HTTP $http_code)"
    fi
    
    # Загрузка модели
    model_name="Model_$(echo "$email" | grep -o '[0-9]')"
    upload_result=$(upload_model "$token" "$MODEL_FILE" "$model_name")
    http_code=$(echo "$upload_result" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    if [ "$http_code" = "201" ]; then
        model_id=$(echo "$upload_result" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
        USER_MODELS["$email"]=$model_id
        echo "   ✅ Модель загружена: $model_name (ID: $model_id)"
    else
        echo "   ❌ Ошибка загрузки модели (HTTP $http_code)"
    fi
done

# Создание предсказаний через API
echo ""
echo "🔮 Создание предсказаний через API..."
total_predictions=0

for user_data in "${USERS[@]}"; do
    email=$(echo "$user_data" | cut -d: -f1)
    token="${USER_TOKENS[$email]}"
    model_id="${USER_MODELS[$email]}"
    
    if [ -z "$token" ] || [ -z "$model_id" ]; then
        continue
    fi
    
    echo ""
    echo "   Пользователь: $email, Model ID: $model_id"
    
    # Создаем 1-3 предсказания
    user_num=$(echo "$email" | grep -o '[0-9]')
    num_predictions=$((user_num % 3 + 1))
    
    for j in $(seq 1 $num_predictions); do
        feature1=$(echo "scale=2; $user_num + $j" | bc)
        feature2=$(echo "scale=2; $user_num + $j + 1" | bc)
        
        pred_result=$(create_prediction "$token" "$model_id" "$feature1" "$feature2")
        http_code=$(echo "$pred_result" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
        
        if [ "$http_code" = "202" ]; then
            prediction_id=$(echo "$pred_result" | python3 -c "import sys, json; print(json.load(sys.stdin).get('prediction_id', '?'))" 2>/dev/null)
            echo "   ✅ Предсказание #$j: создано (ID: $prediction_id)"
            total_predictions=$((total_predictions + 1))
        else
            echo "   ❌ Ошибка создания предсказания #$j (HTTP $http_code)"
        fi
    done
done

# Удаляем временный файл модели
rm -f "$MODEL_FILE"

# Итоговая статистика
echo ""
echo "============================================================"
echo "📊 Итоговая статистика:"
echo "   👥 Пользователей создано: $((${#USERS[@]} + 1)) (1 админ, ${#USERS[@]} обычных)"
echo "   🤖 ML моделей загружено: ${#USER_MODELS[@]}"
echo "   🔮 Предсказаний создано: $total_predictions"
echo ""
echo "✅ Инициализация данных завершена успешно!"
echo ""
echo "📝 Учетные данные:"
echo "   Администратор:"
echo "     Email: admin@mlservice.com"
echo "     Password: admin123"
echo ""
echo "   Обычные пользователи:"
for user_data in "${USERS[@]}"; do
    email=$(echo "$user_data" | cut -d: -f1)
    password=$(echo "$user_data" | cut -d: -f2)
    echo "     $email / $password"
done
