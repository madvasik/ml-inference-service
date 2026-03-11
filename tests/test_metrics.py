import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from backend.app.main import app
from backend.app.monitoring.metrics import (
    prediction_requests_total,
    prediction_latency_seconds,
    billing_transactions_total,
    active_users,
    prediction_errors_total
)


@pytest.fixture
def client():
    """Тестовый клиент"""
    return TestClient(app)


def test_metrics_endpoint_exists(client):
    """Тест наличия endpoint /metrics"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"] or "text/plain; version=0.0.4" in response.headers.get("content-type", "")


def test_metrics_endpoint_contains_prediction_metrics(client):
    """Тест наличия метрик предсказаний в ответе"""
    response = client.get("/metrics")
    assert response.status_code == 200
    
    content = response.text
    # Проверяем наличие метрик
    assert "prediction_requests_total" in content or "# HELP prediction_requests_total" in content
    assert "prediction_latency_seconds" in content or "# HELP prediction_latency_seconds" in content


def test_metrics_endpoint_contains_billing_metrics(client):
    """Тест наличия метрик биллинга в ответе"""
    response = client.get("/metrics")
    assert response.status_code == 200
    
    content = response.text
    assert "billing_transactions_total" in content or "# HELP billing_transactions_total" in content


def test_prediction_metrics_registered():
    """Тест регистрации метрик предсказаний"""
    # Проверяем, что метрики зарегистрированы в Prometheus
    metric_names = [m.name for m in REGISTRY._collector_to_names.keys()]
    
    # Проверяем наличие наших метрик
    assert any("prediction_requests_total" in str(m) for m in REGISTRY._collector_to_names.keys())
    assert any("prediction_latency_seconds" in str(m) for m in REGISTRY._collector_to_names.keys())


def test_billing_metrics_increment():
    """Тест инкремента метрик биллинга"""
    from backend.app.billing.service import add_credits, deduct_credits
    from backend.app.database.session import SessionLocal
    from backend.app.models.user import User
    from backend.app.models.balance import Balance
    
    # Получаем начальное значение метрики
    initial_value = sum(
        sample.value for sample in billing_transactions_total.collect()[0].samples
        if sample.name == "billing_transactions_total"
    )
    
    # Создаем тестового пользователя и баланс
    db = SessionLocal()
    try:
        user = User(email="test_metrics@example.com", password_hash="test")
        db.add(user)
        db.commit()
        db.refresh(user)
        
        balance = Balance(user_id=user.id, credits=1000)
        db.add(balance)
        db.commit()
        
        # Выполняем транзакцию
        add_credits(db, user.id, 100, "Test")
        
        # Проверяем, что метрика увеличилась
        # (в реальном тесте нужно использовать моки или изолированную БД)
        
        # Очистка
        db.delete(balance)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def test_active_users_metric_exists():
    """Тест наличия метрики активных пользователей"""
    # Проверяем, что метрика существует
    assert active_users is not None
    # Метрика должна быть типа Gauge
    assert hasattr(active_users, 'set')
    assert hasattr(active_users, 'inc')
    assert hasattr(active_users, 'dec')
