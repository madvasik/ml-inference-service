#!/usr/bin/env python3
"""
Скрипт для проверки статуса pending предсказаний
"""
import sys
import os
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from sqlalchemy.orm import Session
from backend.app.database.session import SessionLocal
from backend.app.models.prediction import Prediction, PredictionStatus

def check_pending():
    """Проверка pending предсказаний"""
    db: Session = SessionLocal()
    
    try:
        # Получаем все pending предсказания
        pending = db.query(Prediction).filter(
            Prediction.status == PredictionStatus.PENDING
        ).order_by(Prediction.created_at.desc()).all()
        
        print(f"\n📊 Статус предсказаний:")
        print("=" * 60)
        
        # Общая статистика
        total = db.query(Prediction).count()
        completed = db.query(Prediction).filter(
            Prediction.status == PredictionStatus.COMPLETED
        ).count()
        failed = db.query(Prediction).filter(
            Prediction.status == PredictionStatus.FAILED
        ).count()
        
        print(f"Всего предсказаний: {total}")
        print(f"✅ Completed: {completed}")
        print(f"❌ Failed: {failed}")
        print(f"⏳ Pending: {len(pending)}")
        
        if pending:
            print(f"\n⚠️  Найдено {len(pending)} pending предсказаний:")
            print("-" * 60)
            
            for pred in pending:
                age = datetime.now(pred.created_at.tzinfo) - pred.created_at
                age_minutes = age.total_seconds() / 60
                
                print(f"ID: {pred.id}")
                print(f"  User ID: {pred.user_id}")
                print(f"  Model ID: {pred.model_id}")
                print(f"  Создано: {pred.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Возраст: {age_minutes:.1f} минут")
                
                if age_minutes > 5:
                    print(f"  ⚠️  ВНИМАНИЕ: Предсказание висит более 5 минут!")
                
                print()
            
            print("\n💡 Возможные причины:")
            print("   1. Celery worker не запущен или не подключен к Redis")
            print("   2. Задачи в очереди Redis не обрабатываются")
            print("   3. Ошибка при выполнении задачи (проверьте логи Celery)")
            print("   4. Проблема с подключением к БД из Celery worker")
        else:
            print("\n✅ Нет pending предсказаний - все задачи обработаны!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при проверке: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    check_pending()
