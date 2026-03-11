#!/usr/bin/env python3
"""
Скрипт для симуляции бурной активности пользователей:
- Множественные запросы на предсказания от разных пользователей
- Случайные интервалы между запросами
- Разные модели и входные данные
"""
import sys
import os
import time
import random
import requests
from datetime import datetime

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Учетные данные пользователей из init_data.py
USERS = [
    {"email": "admin@mlservice.com", "password": "admin123"},
    {"email": "user1@example.com", "password": "user123"},
    {"email": "user2@example.com", "password": "user123"},
    {"email": "user3@example.com", "password": "user123"},
    {"email": "user4@example.com", "password": "user123"},
    {"email": "user5@example.com", "password": "user123"},
]


def login(email: str, password: str) -> str:
    """Вход пользователя и получение токена"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"❌ Ошибка входа для {email}: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ошибка подключения для {email}: {str(e)}")
        return None


def get_user_models(token: str) -> list:
    """Получение списка моделей пользователя"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/v1/models",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            models = response.json()
            return models if isinstance(models, list) else []
        return []
    except Exception as e:
        print(f"❌ Ошибка получения моделей: {str(e)}")
        return []


def get_user_balance(token: str) -> int:
    """Получение баланса пользователя"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/v1/billing/balance",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("credits", 0)
        return 0
    except Exception as e:
        print(f"❌ Ошибка получения баланса: {str(e)}")
        return 0


def create_prediction(token: str, model_id: int) -> dict:
    """Создание запроса на предсказание"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        # Генерируем случайные входные данные
        input_data = {
            "feature1": round(random.uniform(1.0, 10.0), 2),
            "feature2": round(random.uniform(1.0, 10.0), 2)
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/predictions",
            headers=headers,
            json={
                "model_id": model_id,
                "input_data": input_data
            },
            timeout=5
        )
        
        if response.status_code == 202:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def simulate_user_activity(user_data: dict, num_requests: int = 10):
    """Симуляция активности одного пользователя"""
    email = user_data["email"]
    password = user_data["password"]
    
    print(f"\n👤 Пользователь: {email}")
    
    # Вход
    token = login(email, password)
    if not token:
        print(f"   ⚠️  Не удалось войти")
        return
    
    # Получаем модели
    models = get_user_models(token)
    if not models:
        print(f"   ⚠️  У пользователя нет моделей")
        return
    
    # Получаем баланс
    balance = get_user_balance(token)
    print(f"   💰 Баланс: {balance} кредитов")
    print(f"   🤖 Моделей: {len(models)}")
    
    # Выбираем случайную модель
    model = random.choice(models)
    model_id = model["id"]
    print(f"   📊 Используем модель: {model['model_name']} (ID: {model_id})")
    
    # Создаем запросы
    success_count = 0
    error_count = 0
    
    for i in range(num_requests):
        # Случайная задержка между запросами (0.1-2 секунды)
        if i > 0:
            delay = random.uniform(0.1, 2.0)
            time.sleep(delay)
        
        result = create_prediction(token, model_id)
        
        if result["success"]:
            success_count += 1
            prediction_id = result["data"].get("prediction_id", "?")
            print(f"   ✅ Запрос #{i+1}: создано предсказание {prediction_id}")
        else:
            error_count += 1
            print(f"   ❌ Запрос #{i+1}: ошибка - {result['error']}")
    
    print(f"   📈 Итого: {success_count} успешных, {error_count} ошибок")


def main():
    """Основная функция симуляции"""
    print("🚀 Начало симуляции активности пользователей")
    print(f"🌐 API URL: {BASE_URL}")
    print("=" * 60)
    
    # Проверяем доступность API
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ API недоступен (статус: {response.status_code})")
            return
    except Exception as e:
        print(f"❌ Не удалось подключиться к API: {str(e)}")
        print("   Убедитесь, что сервис запущен: docker-compose up -d")
        return
    
    print("✅ API доступен\n")
    
    # Симулируем активность для каждого пользователя
    total_requests = 0
    
    for user_data in USERS:
        # Случайное количество запросов от 5 до 20 на пользователя
        num_requests = random.randint(5, 20)
        total_requests += num_requests
        
        simulate_user_activity(user_data, num_requests)
        
        # Небольшая пауза между пользователями
        time.sleep(random.uniform(1, 3))
    
    print("\n" + "=" * 60)
    print(f"✅ Симуляция завершена!")
    print(f"📊 Всего создано запросов: ~{total_requests}")
    print(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n💡 Проверьте Grafana для просмотра метрик")
    print("💡 Проверьте статус предсказаний через API или Streamlit")


if __name__ == "__main__":
    main()
