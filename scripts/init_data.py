#!/usr/bin/env python3
"""
Скрипт для инициализации тестовых данных:
- 1 администратор
- 5 обычных пользователей
- Пополнение балансов
- Создание моделей
- Создание предсказаний
"""
import sys
import os
import pickle
import tempfile
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from backend.app.database.session import SessionLocal
from backend.app.database.base import Base
from backend.app.models.user import User, UserRole
from backend.app.models.balance import Balance
from backend.app.models.ml_model import MLModel
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.models.transaction import Transaction
from backend.app.auth.security import get_password_hash
from backend.app.billing.service import add_credits
from backend.app.config import settings


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


def init_data():
    """Инициализация тестовых данных"""
    db: Session = SessionLocal()
    
    try:
        print("🚀 Начало инициализации данных...")
        
        # Создаем таблицы если их нет (для SQLite)
        try:
            Base.metadata.create_all(bind=db.bind)
        except:
            pass  # Таблицы уже существуют или используется PostgreSQL
        
        # Удаляем всех существующих пользователей (кроме админа если нужно сохранить)
        print("\n📋 Очистка существующих данных...")
        try:
            existing_users = db.query(User).all()
        except Exception as e:
            print(f"   ⚠️  Таблицы еще не созданы, пропускаем очистку: {e}")
            existing_users = []
        # Удаляем в правильном порядке из-за foreign keys
        # Сначала все predictions (они ссылаются на models и users)
        db.query(Prediction).delete()
        # Потом все transactions (они ссылаются на users)
        db.query(Transaction).delete()
        # Потом все models (они ссылаются на users)
        db.query(MLModel).delete()
        # Потом все balances (они ссылаются на users)
        db.query(Balance).delete()
        # И наконец все users
        for user in existing_users:
            db.delete(user)
        db.commit()
        print(f"   Удалено {len(existing_users)} существующих пользователей")
        
        # Создаем администратора
        print("\n👤 Создание администратора...")
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
        
        # Создаем 5 обычных пользователей
        print("\n👥 Создание обычных пользователей...")
        users_data = [
            {"email": "user1@example.com", "password": "user123", "credits": 500},
            {"email": "user2@example.com", "password": "user123", "credits": 1000},
            {"email": "user3@example.com", "password": "user123", "credits": 750},
            {"email": "user4@example.com", "password": "user123", "credits": 1500},
            {"email": "user5@example.com", "password": "user123", "credits": 2000},
        ]
        
        created_users = []
        for user_data in users_data:
            user = User(
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                role=UserRole.USER
            )
            db.add(user)
            db.flush()
            
            balance = Balance(user_id=user.id, credits=user_data["credits"])
            db.add(balance)
            db.commit()
            db.refresh(user)
            
            created_users.append(user)
            print(f"   ✅ Пользователь создан: {user.email} (ID: {user.id}, баланс: {balance.credits})")
        
        # Создаем модели для пользователей
        print("\n🤖 Создание ML моделей...")
        model_file = create_test_model()
        
        try:
            for i, user in enumerate(created_users, 1):
                # Создаем директорию для пользователя
                user_models_dir = os.path.join(settings.ml_models_dir, str(user.id))
                os.makedirs(user_models_dir, exist_ok=True)
                
                # Копируем модель для каждого пользователя
                user_model_path = os.path.join(user_models_dir, f"{i}.pkl")
                with open(model_file, 'rb') as src, open(user_model_path, 'wb') as dst:
                    dst.write(src.read())
                
                # Создаем запись в БД
                ml_model = MLModel(
                    owner_id=user.id,
                    model_name=f"Model_{i}",
                    file_path=user_model_path,
                    model_type="classification"
                )
                db.add(ml_model)
                db.commit()
                db.refresh(ml_model)
                
                print(f"   ✅ Модель создана для {user.email}: {ml_model.model_name} (ID: {ml_model.id})")
        finally:
            # Удаляем временный файл
            if os.path.exists(model_file):
                os.remove(model_file)
        
        # Создаем предсказания для пользователей
        print("\n🔮 Создание предсказаний...")
        for i, user in enumerate(created_users, 1):
            # Получаем модель пользователя
            user_model = db.query(MLModel).filter(MLModel.owner_id == user.id).first()
            if not user_model:
                continue
            
            # Создаем несколько предсказаний для каждого пользователя
            num_predictions = (i % 3) + 1  # 1-3 предсказания на пользователя
            
            for j in range(num_predictions):
                prediction = Prediction(
                    user_id=user.id,
                    model_id=user_model.id,
                    input_data={"feature1": float(i + j), "feature2": float(i + j + 1)},
                    status=PredictionStatus.COMPLETED if j == 0 else PredictionStatus.PENDING,
                    credits_spent=settings.prediction_cost if j == 0 else 0,
                    result={"prediction": [float(i % 2)], "probabilities": [0.3, 0.7]} if j == 0 else None
                )
                db.add(prediction)
            
            db.commit()
            print(f"   ✅ Создано {num_predictions} предсказаний для {user.email}")
        
        # Пополняем балансы через API (симулируем транзакции)
        print("\n💳 Пополнение балансов...")
        for user in created_users:
            # Добавляем дополнительные кредиты через сервис (для создания транзакций)
            add_credits(db, user.id, 100, "Initial bonus")
        db.commit()
        print("   ✅ Балансы пополнены")
        
        # Итоговая статистика
        print("\n📊 Итоговая статистика:")
        total_users = db.query(User).count()
        total_models = db.query(MLModel).count()
        total_predictions = db.query(Prediction).count()
        total_balances = db.query(Balance).count()
        
        print(f"   👥 Пользователей: {total_users} (1 админ, {total_users - 1} обычных)")
        print(f"   🤖 ML моделей: {total_models}")
        print(f"   🔮 Предсказаний: {total_predictions}")
        print(f"   💰 Балансов: {total_balances}")
        
        print("\n✅ Инициализация данных завершена успешно!")
        print("\n📝 Учетные данные:")
        print("   Администратор:")
        print("     Email: admin@mlservice.com")
        print("     Password: admin123")
        print("\n   Обычные пользователи:")
        for user in created_users:
            balance = db.query(Balance).filter(Balance.user_id == user.id).first()
            print(f"     {user.email} / user123 (баланс: {balance.credits} кредитов)")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Ошибка при инициализации данных: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    # Проверяем наличие переменной окружения DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("⚠️  DATABASE_URL не установлена. Используется SQLite для локального тестирования.")
        os.environ["DATABASE_URL"] = "sqlite:///./test_init.db"
        os.environ["SECRET_KEY"] = os.getenv("SECRET_KEY", "test-secret-key")
    
    init_data()
