#!/usr/bin/env python3
"""
Скрипт для проверки метрик Prometheus и сравнения с данными из базы
"""
import sys
import os
import requests
import json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.database.session import SessionLocal
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.models.transaction import Transaction
from backend.app.models.user import User

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")


def get_db_stats():
    """Получение статистики из базы данных"""
    db: Session = SessionLocal()
    try:
        # Подсчет предсказаний
        total_predictions = db.query(Prediction).count()
        completed_predictions = db.query(Prediction).filter(
            Prediction.status == PredictionStatus.COMPLETED
        ).count()
        pending_predictions = db.query(Prediction).filter(
            Prediction.status == PredictionStatus.PENDING
        ).count()
        failed_predictions = db.query(Prediction).filter(
            Prediction.status == PredictionStatus.FAILED
        ).count()
        
        # Подсчет транзакций
        credit_transactions = db.query(Transaction).filter(
            Transaction.type == 'CREDIT'
        ).count()
        debit_transactions = db.query(Transaction).filter(
            Transaction.type == 'DEBIT'
        ).count()
        
        # Активные пользователи (за последние 15 минут)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=15)
        active_users_count = db.query(func.count(func.distinct(Prediction.user_id))).filter(
            Prediction.created_at >= cutoff_time
        ).scalar() or 0
        
        return {
            "predictions": {
                "total": total_predictions,
                "completed": completed_predictions,
                "pending": pending_predictions,
                "failed": failed_predictions
            },
            "transactions": {
                "credit": credit_transactions,
                "debit": debit_transactions,
                "total": credit_transactions + debit_transactions
            },
            "active_users": active_users_count
        }
    finally:
        db.close()


def get_prometheus_metrics():
    """Получение метрик из Prometheus"""
    metrics = {}
    
    try:
        # Prediction requests total
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "sum(prediction_requests_total)"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("data", {}).get("result"):
                metrics["prediction_requests_total"] = float(
                    data["data"]["result"][0]["value"][1]
                )
        
        # Active users
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "active_users"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("data", {}).get("result"):
                metrics["active_users"] = float(
                    data["data"]["result"][0]["value"][1]
                )
        
        # Billing transactions
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "billing_transactions_total"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                credit = 0
                debit = 0
                for result in data.get("data", {}).get("result", []):
                    if result["metric"].get("type") == "credit":
                        credit = float(result["value"][1])
                    elif result["metric"].get("type") == "debit":
                        debit = float(result["value"][1])
                metrics["billing_transactions"] = {
                    "credit": credit,
                    "debit": debit,
                    "total": credit + debit
                }
    except Exception as e:
        print(f"⚠️  Ошибка получения метрик Prometheus: {e}")
    
    return metrics


def get_backend_metrics():
    """Получение метрик напрямую из backend"""
    try:
        response = requests.get(f"{BASE_URL}/metrics", timeout=5)
        if response.status_code == 200:
            lines = response.text.split('\n')
            metrics = {}
            for line in lines:
                if line.startswith('active_users '):
                    metrics["active_users"] = float(line.split()[1])
                elif line.startswith('billing_transactions_total{type="credit"}'):
                    metrics["billing_credit"] = float(line.split()[1])
                elif line.startswith('billing_transactions_total{type="debit"}'):
                    metrics["billing_debit"] = float(line.split()[1])
            return metrics
    except Exception as e:
        print(f"⚠️  Ошибка получения метрик backend: {e}")
    return {}


def main():
    print("=" * 70)
    print("📊 Проверка метрик Prometheus и сравнение с базой данных")
    print("=" * 70)
    
    # Получаем данные из базы
    print("\n📦 Данные из базы данных:")
    db_stats = get_db_stats()
    print(f"   Предсказания:")
    print(f"      Всего: {db_stats['predictions']['total']}")
    print(f"      Завершено: {db_stats['predictions']['completed']}")
    print(f"      В ожидании: {db_stats['predictions']['pending']}")
    print(f"      Ошибок: {db_stats['predictions']['failed']}")
    print(f"   Транзакции:")
    print(f"      CREDIT: {db_stats['transactions']['credit']}")
    print(f"      DEBIT: {db_stats['transactions']['debit']}")
    print(f"      Всего: {db_stats['transactions']['total']}")
    print(f"   Активные пользователи (15 мин): {db_stats['active_users']}")
    
    # Получаем метрики из backend
    print("\n🔧 Метрики из backend (/metrics):")
    backend_metrics = get_backend_metrics()
    if backend_metrics:
        print(f"   active_users: {backend_metrics.get('active_users', 'N/A')}")
        print(f"   billing_transactions_total (credit): {backend_metrics.get('billing_credit', 'N/A')}")
        print(f"   billing_transactions_total (debit): {backend_metrics.get('billing_debit', 'N/A (метрика инкрементируется в Celery)')}")
    else:
        print("   ⚠️  Не удалось получить метрики")
    
    # Получаем метрики из Prometheus
    print("\n📈 Метрики из Prometheus:")
    prom_metrics = get_prometheus_metrics()
    if prom_metrics:
        if "prediction_requests_total" in prom_metrics:
            print(f"   prediction_requests_total: {prom_metrics['prediction_requests_total']}")
        if "active_users" in prom_metrics:
            print(f"   active_users: {prom_metrics['active_users']}")
        if "billing_transactions" in prom_metrics:
            bt = prom_metrics["billing_transactions"]
            print(f"   billing_transactions_total:")
            print(f"      credit: {bt['credit']}")
            print(f"      debit: {bt['debit']} (⚠️  метрика инкрементируется в Celery worker)")
            print(f"      total: {bt['total']}")
    else:
        print("   ⚠️  Не удалось получить метрики")
    
    # Сравнение
    print("\n✅ Сравнение:")
    if backend_metrics and db_stats:
        active_users_match = backend_metrics.get('active_users') == db_stats['active_users']
        print(f"   active_users: {'✅ Совпадает' if active_users_match else '❌ Не совпадает'}")
        print(f"      БД: {db_stats['active_users']}, Backend: {backend_metrics.get('active_users', 'N/A')}")
    
    print("\n" + "=" * 70)
    print("💡 Примечание: billing_transactions_total для debit транзакций")
    print("   инкрементируется в Celery worker, поэтому не отображается")
    print("   в метриках backend процесса. Это нормальное поведение.")
    print("=" * 70)


if __name__ == "__main__":
    main()
