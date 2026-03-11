#!/usr/bin/env python3
"""Тестирование административных функций"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("ТЕСТИРОВАНИЕ АДМИНИСТРАТИВНЫХ ФУНКЦИЙ")
print("=" * 60)

# Сначала нужно создать админа или использовать существующего
# Для демонстрации создадим нового админа через SQL или используем существующего пользователя

# 1. Вход как обычный пользователь
print("\n1. ВХОД КАК ОБЫЧНЫЙ ПОЛЬЗОВАТЕЛЬ")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    json={"email": "demo@example.com", "password": "demo123"}
)
if response.status_code == 200:
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Вход выполнен")
    
    # Попытка доступа к админским функциям
    print("\n2. ПОПЫТКА ДОСТУПА К АДМИНСКИМ ФУНКЦИЯМ (должна быть отклонена)")
    response = requests.get(f"{BASE_URL}/api/v1/admin/users", headers=headers)
    if response.status_code == 403:
        print("✅ Доступ правильно запрещен для обычного пользователя")
    else:
        print(f"⚠️  Неожиданный статус: {response.status_code} - {response.text}")

# Создаем админа через прямой запрос к БД или через скрипт
print("\n3. СОЗДАНИЕ АДМИНИСТРАТОРА")
# Регистрируем нового пользователя как админа
response = requests.post(
    f"{BASE_URL}/api/v1/auth/register",
    json={"email": "admin@example.com", "password": "admin123"}
)
if response.status_code == 201:
    admin_token = response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("✅ Администратор зарегистрирован")
    
    # Нужно вручную установить роль admin в БД
    # Для демонстрации покажем, как это сделать через SQL
    print("\n⚠️  ВАЖНО: Установите роль admin в БД:")
    print("   docker-compose exec postgres psql -U user -d ml_service -c")
    print("   \"UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';\"")
    
    # После установки роли можно использовать админские функции
    print("\n4. ИСПОЛЬЗОВАНИЕ АДМИНСКИХ ФУНКЦИЙ")
    print("   (После установки роли admin в БД)")
    print("\n   Примеры запросов:")
    print(f"   GET {BASE_URL}/api/v1/admin/users")
    print(f"   GET {BASE_URL}/api/v1/admin/predictions")
    print(f"   GET {BASE_URL}/api/v1/admin/predictions?user_id=1")
    print(f"   GET {BASE_URL}/api/v1/admin/predictions?model_id=1")
else:
    print("⚠️  Администратор уже существует, выполняем вход...")
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"}
    )
    if response.status_code == 200:
        admin_token = response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("✅ Вход выполнен")
        
        # Проверяем доступ к админским функциям
        print("\n4. СПИСОК ВСЕХ ПОЛЬЗОВАТЕЛЕЙ")
        response = requests.get(f"{BASE_URL}/api/v1/admin/users", headers=admin_headers)
        if response.status_code == 200:
            users = response.json()
            print(f"✅ Найдено пользователей: {len(users)}")
            for user in users[:5]:
                print(f"   - {user['email']} (ID: {user['id']}, Роль: {user['role']})")
        elif response.status_code == 403:
            print("❌ Доступ запрещен. Установите роль admin в БД:")
            print("   docker-compose exec postgres psql -U user -d ml_service -c")
            print("   \"UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';\"")
        else:
            print(f"❌ Ошибка: {response.status_code} - {response.text}")
        
        print("\n5. СПИСОК ВСЕХ ПРЕДСКАЗАНИЙ")
        response = requests.get(f"{BASE_URL}/api/v1/admin/predictions", headers=admin_headers)
        if response.status_code == 200:
            predictions = response.json()
            print(f"✅ Всего предсказаний: {predictions['total']}")
            for pred in predictions['predictions'][:5]:
                print(f"   - ID: {pred['id']}, User: {pred['user_id']}, Model: {pred['model_id']}, Status: {pred['status']}")
        elif response.status_code == 403:
            print("❌ Доступ запрещен. Установите роль admin в БД")
        else:
            print(f"❌ Ошибка: {response.status_code} - {response.text}")

print("\n" + "=" * 60)
print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 60)
