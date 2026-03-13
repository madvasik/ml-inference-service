#!/usr/bin/env python3
"""
Скрипт для очистки всех данных из базы:
- Все предсказания (predictions)
- Все транзакции (transactions)
- Все модели (ml_models)
- Все балансы (balances)
- Все пользователи (users)
"""
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from sqlalchemy.orm import Session
from backend.app.database.session import SessionLocal
from backend.app.models.user import User
from backend.app.models.balance import Balance
from backend.app.models.ml_model import MLModel
from backend.app.models.prediction import Prediction
from backend.app.models.transaction import Transaction


def cleanup_all_data():
    """Удаление всех данных из базы"""
    db: Session = SessionLocal()
    
    try:
        print("🧹 Начало очистки данных...")
        
        # Подсчитываем количество записей перед удалением
        predictions_count = db.query(Prediction).count()
        transactions_count = db.query(Transaction).count()
        models_count = db.query(MLModel).count()
        balances_count = db.query(Balance).count()
        users_count = db.query(User).count()
        
        print(f"\n📊 Текущее состояние базы:")
        print(f"   - Предсказаний: {predictions_count}")
        print(f"   - Транзакций: {transactions_count}")
        print(f"   - Моделей: {models_count}")
        print(f"   - Балансов: {balances_count}")
        print(f"   - Пользователей: {users_count}")
        
        # Удаляем в правильном порядке из-за foreign keys
        print("\n🗑️  Удаление данных...")
        
        # Сначала все predictions (они ссылаются на models и users)
        db.query(Prediction).delete()
        print(f"   ✅ Удалено {predictions_count} предсказаний")
        
        # Потом все transactions (они ссылаются на users)
        db.query(Transaction).delete()
        print(f"   ✅ Удалено {transactions_count} транзакций")
        
        # Потом все models (они ссылаются на users)
        db.query(MLModel).delete()
        print(f"   ✅ Удалено {models_count} моделей")
        
        # Потом все balances (они ссылаются на users)
        db.query(Balance).delete()
        print(f"   ✅ Удалено {balances_count} балансов")
        
        # И наконец все users
        for user in db.query(User).all():
            db.delete(user)
        print(f"   ✅ Удалено {users_count} пользователей")
        
        db.commit()
        
        print("\n✅ Очистка завершена успешно!")
        print("   Все данные удалены из базы.")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Ошибка при очистке данных: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_all_data()
