#!/usr/bin/env python3
"""
Скрипт для просмотра всех клиентов и запросов (требуются права администратора)
"""
import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"


def login(email: str, password: str) -> str:
    """Вход и получение токена"""
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": password}
    )
    if response.status_code != 200:
        print(f"❌ Ошибка входа: {response.status_code} - {response.text}")
        sys.exit(1)
    return response.json()["access_token"]


def print_users(headers: dict):
    """Вывод списка всех пользователей"""
    print("\n" + "=" * 60)
    print("СПИСОК ВСЕХ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/v1/admin/users", headers=headers)
    if response.status_code == 200:
        users = response.json()
        print(f"\nВсего пользователей: {len(users)}\n")
        
        for user in users:
            print(f"ID: {user['id']}")
            print(f"  Email: {user['email']}")
            print(f"  Роль: {user['role']}")
            print(f"  Создан: {user['created_at']}")
            print()
    elif response.status_code == 403:
        print("❌ Доступ запрещен. Нужны права администратора")
        print("\nДля получения прав администратора выполните:")
        print("docker-compose exec postgres psql -U user -d ml_service -c")
        print("\"UPDATE users SET role = 'ADMIN' WHERE email = 'ваш_email@example.com';\"")
        sys.exit(1)
    else:
        print(f"❌ Ошибка: {response.status_code} - {response.text}")
        sys.exit(1)


def print_predictions(headers: dict, user_id: int = None, model_id: int = None):
    """Вывод списка всех предсказаний"""
    print("\n" + "=" * 60)
    print("СПИСОК ВСЕХ ПРЕДСКАЗАНИЙ")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/v1/admin/predictions"
    params = {}
    if user_id:
        params['user_id'] = user_id
        print(f"\nФильтр: user_id = {user_id}")
    if model_id:
        params['model_id'] = model_id
        print(f"Фильтр: model_id = {model_id}")
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        predictions = data['predictions']
        total = data['total']
        
        print(f"\nВсего предсказаний: {total}\n")
        
        for pred in predictions:
            print(f"ID: {pred['id']}")
            print(f"  User ID: {pred['user_id']}")
            print(f"  Model ID: {pred['model_id']}")
            print(f"  Статус: {pred['status']}")
            print(f"  Потрачено кредитов: {pred['credits_spent']}")
            print(f"  Создано: {pred['created_at']}")
            if pred.get('result'):
                result = pred['result']
                print(f"  Результат: {json.dumps(result, indent=4)}")
            print()
    elif response.status_code == 403:
        print("❌ Доступ запрещен. Нужны права администратора")
        sys.exit(1)
    else:
        print(f"❌ Ошибка: {response.status_code} - {response.text}")
        sys.exit(1)


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Просмотр клиентов и запросов (требуются права администратора)')
    parser.add_argument('--email', default='demo@example.com', help='Email администратора')
    parser.add_argument('--password', default='demo123', help='Пароль администратора')
    parser.add_argument('--users', action='store_true', help='Показать список пользователей')
    parser.add_argument('--predictions', action='store_true', help='Показать список предсказаний')
    parser.add_argument('--user-id', type=int, help='Фильтр предсказаний по user_id')
    parser.add_argument('--model-id', type=int, help='Фильтр предсказаний по model_id')
    
    args = parser.parse_args()
    
    # Если не указаны опции, показываем все
    if not args.users and not args.predictions:
        args.users = True
        args.predictions = True
    
    # Вход
    print("Вход в систему...")
    token = login(args.email, args.password)
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Вход выполнен\n")
    
    # Вывод данных
    if args.users:
        print_users(headers)
    
    if args.predictions:
        print_predictions(headers, user_id=args.user_id, model_id=args.model_id)


if __name__ == "__main__":
    main()
