#!/usr/bin/env python3
"""
Скрипт для инициализации тестовых данных через API эндпоинты:
- 1 администратор (создается через прямой доступ к БД, так как нет API для создания админа)
- 5 обычных пользователей (через /api/v1/auth/register)
- Пополнение балансов (через /api/v1/billing/topup)
- Создание моделей (через /api/v1/models/upload)
- Создание предсказаний (через /api/v1/predictions)
"""
import sys
import os
import pickle
import tempfile
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def create_test_model() -> str:
    """Создание тестовой ML модели"""
    # Создаем простую модель классификации
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
    y = np.array([0, 1, 0, 1, 0])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    
    # Сохраняем во временный файл
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    pickle.dump(model, temp_file)
    temp_file.close()
    
    return temp_file.name


def register_user(email: str, password: str) -> dict:
    """Регистрация пользователя через API"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={"email": email, "password": password},
            timeout=5
        )
        if response.status_code == 201:
            return {"success": True, "token": response.json()["access_token"]}
        elif response.status_code == 400 and "already registered" in response.text.lower():
            # Пользователь уже существует, пробуем войти
            login_response = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=5
            )
            if login_response.status_code == 200:
                return {"success": True, "token": login_response.json()["access_token"]}
        return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def topup_balance(token: str, amount: int) -> dict:
    """Пополнение баланса через API"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/billing/topup",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": amount},
            timeout=5
        )
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_model(token: str, model_file: str, model_name: str) -> dict:
    """Загрузка модели через API"""
    try:
        with open(model_file, 'rb') as f:
            files = {'file': (os.path.basename(model_file), f, 'application/octet-stream')}
            data = {'model_name': model_name}
            response = requests.post(
                f"{BASE_URL}/api/v1/models/upload",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data,
                timeout=10
            )
        if response.status_code == 201:
            return {"success": True, "data": response.json()}
        return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_prediction(token: str, model_id: int, input_data: dict) -> dict:
    """Создание предсказания через API"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/predictions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model_id": model_id, "input_data": input_data},
            timeout=5
        )
        if response.status_code == 202:
            return {"success": True, "data": response.json()}
        return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_admin_direct():
    """Создание администратора напрямую в БД (нет API эндпоинта для создания админа)"""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
    from sqlalchemy.orm import Session
    from backend.app.database.session import SessionLocal
    from backend.app.models.user import User, UserRole
    from backend.app.models.balance import Balance
    from backend.app.auth.security import get_password_hash
    
    db: Session = SessionLocal()
    try:
        # Проверяем, существует ли уже админ
        admin = db.query(User).filter(User.email == "admin@mlservice.com").first()
        if admin:
            print(f"   ℹ️  Администратор уже существует: {admin.email} (ID: {admin.id})")
            return admin.id
        
        # Создаем администратора
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
        return admin.id
    except Exception as e:
        db.rollback()
        print(f"   ❌ Ошибка создания администратора: {str(e)}")
        raise
    finally:
        db.close()


def init_data():
    """Инициализация тестовых данных через API"""
    print("🚀 Начало инициализации данных через API...")
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
    
    # Создаем администратора (напрямую в БД, так как нет API для создания админа)
    print("👤 Создание администратора...")
    try:
        admin_id = create_admin_direct()
        # Получаем токен для админа
        admin_result = register_user("admin@mlservice.com", "admin123")
        if not admin_result["success"]:
            print(f"   ⚠️  Не удалось получить токен админа: {admin_result.get('error')}")
    except Exception as e:
        print(f"   ❌ Ошибка: {str(e)}")
        return
    
    # Создаем 5 обычных пользователей через API
    print("\n👥 Создание обычных пользователей через API...")
    users_data = [
        {"email": "user1@example.com", "password": "user123", "credits": 500},
        {"email": "user2@example.com", "password": "user123", "credits": 1000},
        {"email": "user3@example.com", "password": "user123", "credits": 750},
        {"email": "user4@example.com", "password": "user123", "credits": 1500},
        {"email": "user5@example.com", "password": "user123", "credits": 2000},
    ]
    
    created_users = []
    for user_data in users_data:
        print(f"\n   Пользователь: {user_data['email']}")
        
        # Регистрация через API
        result = register_user(user_data["email"], user_data["password"])
        if not result["success"]:
            print(f"   ❌ Ошибка регистрации: {result.get('error')}")
            continue
        
        token = result["token"]
        print(f"   ✅ Пользователь зарегистрирован")
        
        # Пополнение баланса через API
        topup_result = topup_balance(token, user_data["credits"])
        if topup_result["success"]:
            balance = topup_result["data"].get("credits", user_data["credits"])
            print(f"   💰 Баланс пополнен: {balance} кредитов")
        else:
            print(f"   ⚠️  Ошибка пополнения баланса: {topup_result.get('error')}")
        
        created_users.append({
            "email": user_data["email"],
            "password": user_data["password"],
            "token": token
        })
    
    if not created_users:
        print("❌ Не удалось создать пользователей")
        return
    
    # Создаем тестовую модель
    print("\n🤖 Создание тестовой ML модели...")
    model_file = create_test_model()
    
    # Загружаем модели для каждого пользователя через API
    print("\n📤 Загрузка ML моделей через API...")
    user_models = []
    try:
        for i, user in enumerate(created_users, 1):
            print(f"\n   Пользователь: {user['email']}")
            
            # Загрузка модели через API
            upload_result = upload_model(
                user["token"],
                model_file,
                f"Model_{i}"
            )
            
            if upload_result["success"]:
                model_id = upload_result["data"]["id"]
                model_name = upload_result["data"]["model_name"]
                print(f"   ✅ Модель загружена: {model_name} (ID: {model_id})")
                user_models.append({
                    "user": user,
                    "model_id": model_id
                })
            else:
                print(f"   ❌ Ошибка загрузки модели: {upload_result.get('error')}")
    finally:
        # Удаляем временный файл модели
        if os.path.exists(model_file):
            os.remove(model_file)
    
    if not user_models:
        print("❌ Не удалось загрузить модели")
        return
    
    # Создаем предсказания через API
    print("\n🔮 Создание предсказаний через API...")
    total_predictions = 0
    for i, user_model in enumerate(user_models, 1):
        user = user_model["user"]
        model_id = user_model["model_id"]
        
        print(f"\n   Пользователь: {user['email']}, Model ID: {model_id}")
        
        # Создаем несколько предсказаний для каждого пользователя
        num_predictions = (i % 3) + 1  # 1-3 предсказания на пользователя
        
        for j in range(num_predictions):
            input_data = {
                "feature1": float(i + j),
                "feature2": float(i + j + 1)
            }
            
            pred_result = create_prediction(user["token"], model_id, input_data)
            
            if pred_result["success"]:
                prediction_id = pred_result["data"].get("prediction_id", "?")
                print(f"   ✅ Предсказание #{j+1}: создано (ID: {prediction_id})")
                total_predictions += 1
            else:
                print(f"   ❌ Ошибка создания предсказания #{j+1}: {pred_result.get('error')}")
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 Итоговая статистика:")
    print(f"   👥 Пользователей создано: {len(created_users) + 1} (1 админ, {len(created_users)} обычных)")
    print(f"   🤖 ML моделей загружено: {len(user_models)}")
    print(f"   🔮 Предсказаний создано: {total_predictions}")
    
    print("\n✅ Инициализация данных завершена успешно!")
    print("\n📝 Учетные данные:")
    print("   Администратор:")
    print("     Email: admin@mlservice.com")
    print("     Password: admin123")
    print("\n   Обычные пользователи:")
    for user in created_users:
        print(f"     {user['email']} / {user['password']}")


if __name__ == "__main__":
    init_data()
