#!/usr/bin/env python3
"""Полный цикл тестирования ML-сервиса"""
import requests
import json
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import tempfile
import os

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("ПОЛНЫЙ ЦИКЛ РАБОТЫ С ML-СЕРВИСОМ")
print("=" * 60)

# 1. Регистрация/Вход
print("\n1. РЕГИСТРАЦИЯ/ВХОД")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/register",
    json={"email": "demo@example.com", "password": "demo123"}
)
if response.status_code == 201:
    data = response.json()
    access_token = data["access_token"]
    print("✅ Регистрация успешна!")
else:
    print("⚠️  Пользователь уже существует, выполняем вход...")
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": "demo@example.com", "password": "demo123"}
    )
    data = response.json()
    access_token = data["access_token"]
    print("✅ Вход выполнен!")

headers = {"Authorization": f"Bearer {access_token}"}

# 2. Проверка текущего пользователя
print("\n2. ПРОВЕРКА ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ")
response = requests.get(f"{BASE_URL}/api/v1/users/me", headers=headers)
if response.status_code == 200:
    user_data = response.json()
    print(f"✅ Пользователь: {user_data['email']} (ID: {user_data['id']})")

# 3. Пополнение баланса
print("\n3. ПОПОЛНЕНИЕ БАЛАНСА")
response = requests.post(
    f"{BASE_URL}/api/v1/billing/topup",
    headers=headers,
    json={"amount": 1000}
)
if response.status_code == 200:
    balance_data = response.json()
    print(f"✅ Баланс пополнен! Текущий баланс: {balance_data['credits']} кредитов")
else:
    print(f"❌ Ошибка: {response.status_code} - {response.text}")

# 4. Создание тестовой модели
print("\n4. СОЗДАНИЕ ТЕСТОВОЙ ML-МОДЕЛИ")
X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
y = np.array([0, 1, 0, 1, 0])
model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(X, y)

temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
pickle.dump(model, temp_file)
temp_file.close()
print(f"✅ Модель создана: {os.path.getsize(temp_file.name)} байт")

# 5. Загрузка модели
print("\n5. ЗАГРУЗКА МОДЕЛИ НА СЕРВЕР")
with open(temp_file.name, 'rb') as f:
    files = {'file': ('model.pkl', f, 'application/octet-stream')}
    response = requests.post(
        f"{BASE_URL}/api/v1/models/upload?model_name=test_model",
        headers=headers,
        files=files
    )
os.unlink(temp_file.name)

if response.status_code == 201:
    model_data = response.json()
    model_id = model_data['id']
    print(f"✅ Модель загружена! ID: {model_id}, Тип: {model_data.get('model_type', 'unknown')}")
else:
    print(f"❌ Ошибка загрузки: {response.status_code} - {response.text}")
    exit(1)

# 6. Проверка баланса перед предсказанием
print("\n6. ПРОВЕРКА БАЛАНСА ПЕРЕД ПРЕДСКАЗАНИЕМ")
response = requests.get(f"{BASE_URL}/api/v1/billing/balance", headers=headers)
if response.status_code == 200:
    balance = response.json()['credits']
    print(f"✅ Текущий баланс: {balance} кредитов")

# 7. Создание предсказания
print("\n7. СОЗДАНИЕ ПРЕДСКАЗАНИЯ")
prediction_data = {
    "model_id": model_id,
    "input_data": {"feature1": 1.0, "feature2": 2.0}
}
response = requests.post(
    f"{BASE_URL}/api/v1/predictions",
    headers=headers,
    json=prediction_data
)

if response.status_code == 201:
    pred_result = response.json()
    print(f"✅ Предсказание выполнено!")
    print(f"   Статус: {pred_result['status']}")
    print(f"   Результат: {json.dumps(pred_result['result'], indent=2)}")
    print(f"   Потрачено кредитов: {pred_result['credits_spent']}")
else:
    print(f"❌ Ошибка предсказания: {response.status_code} - {response.text}")

# 8. Проверка баланса после предсказания
print("\n8. ПРОВЕРКА БАЛАНСА ПОСЛЕ ПРЕДСКАЗАНИЯ")
response = requests.get(f"{BASE_URL}/api/v1/billing/balance", headers=headers)
if response.status_code == 200:
    balance = response.json()['credits']
    print(f"✅ Текущий баланс: {balance} кредитов")

# 9. История транзакций
print("\n9. ИСТОРИЯ ТРАНЗАКЦИЙ")
response = requests.get(f"{BASE_URL}/api/v1/billing/transactions", headers=headers)
if response.status_code == 200:
    transactions = response.json()
    print(f"✅ Всего транзакций: {transactions['total']}")
    for t in transactions['transactions'][:5]:
        print(f"   - {t['type']}: {t['amount']} кредитов - {t.get('description', 'N/A')}")

# 10. Список предсказаний
print("\n10. СПИСОК ПРЕДСКАЗАНИЙ")
response = requests.get(f"{BASE_URL}/api/v1/predictions", headers=headers)
if response.status_code == 200:
    predictions = response.json()
    print(f"✅ Всего предсказаний: {predictions['total']}")
    for p in predictions['predictions'][:3]:
        print(f"   - ID: {p['id']}, Статус: {p['status']}, Кредитов: {p['credits_spent']}")

print("\n" + "=" * 60)
print("ЦИКЛ ЗАВЕРШЕН УСПЕШНО! ✅")
print("=" * 60)
