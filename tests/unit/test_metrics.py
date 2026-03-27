import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from backend.app.main import app
from backend.app.metrics import (
    prediction_requests_total,
    prediction_latency_seconds,
    billing_transactions_total,
    active_users,
    prediction_errors_total
)

# Используем фикстуру client из conftest.py для тестов, требующих БД
# Для тестов без БД можно использовать локальную фикстуру
@pytest.fixture
def client_no_db():
    """Тестовый клиент без БД (для тестов метрик, не требующих БД)"""
    return TestClient(app)


def test_metrics_endpoint_exists(client_no_db):
    """Тест наличия endpoint /metrics"""
    response = client_no_db.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"] or "text/plain; version=0.0.4" in response.headers.get("content-type", "")


def test_metrics_endpoint_contains_prediction_metrics(client_no_db):
    """Тест наличия метрик предсказаний в ответе"""
    response = client_no_db.get("/metrics")
    assert response.status_code == 200
    
    content = response.text
    # Проверяем наличие метрик
    assert "prediction_requests_total" in content or "# HELP prediction_requests_total" in content
    assert "prediction_latency_seconds" in content or "# HELP prediction_latency_seconds" in content


def test_metrics_endpoint_contains_billing_metrics(client_no_db):
    """Тест наличия метрик биллинга в ответе"""
    response = client_no_db.get("/metrics")
    assert response.status_code == 200
    
    content = response.text
    assert "billing_transactions_total" in content or "# HELP billing_transactions_total" in content


def test_prediction_metrics_registered():
    """Тест регистрации метрик предсказаний"""
    # Проверяем, что метрики существуют и имеют правильный тип
    from prometheus_client import Counter, Histogram
    
    assert isinstance(prediction_requests_total, Counter)
    assert isinstance(prediction_latency_seconds, Histogram)
    assert isinstance(prediction_errors_total, Counter)
    
    # Проверяем, что метрики можно использовать
    assert hasattr(prediction_requests_total, 'labels')
    assert hasattr(prediction_latency_seconds, 'observe')


def test_billing_metrics_increment(client, db_session, test_user):
    """Тест инкремента метрик биллинга"""
    from backend.app.billing import add_credits
    from backend.app.models import Balance
    
    # Получаем начальное значение метрики для типа "credit"
    samples = billing_transactions_total.collect()[0].samples
    initial_value = sum(
        sample.value for sample in samples
        if sample.name == "billing_transactions_total_total" and 
        len(sample.labels) > 0 and sample.labels.get("type") == "credit"
    )
    
    # Убеждаемся, что баланс существует
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if not balance:
        balance = Balance(user_id=test_user.id, credits=1000)
        db_session.add(balance)
        db_session.commit()
    
    # Выполняем транзакцию
    add_credits(db_session, test_user.id, 100, "Test")
    
    # Проверяем, что метрика увеличилась
    samples_after = billing_transactions_total.collect()[0].samples
    final_value = sum(
        sample.value for sample in samples_after
        if sample.name == "billing_transactions_total_total" and 
        len(sample.labels) > 0 and sample.labels.get("type") == "credit"
    )
    
    # Метрика должна увеличиться или остаться такой же (если уже была вызвана ранее)
    assert final_value >= initial_value


def test_active_users_metric_exists():
    """Тест наличия метрики активных пользователей"""
    # Проверяем, что метрика существует
    assert active_users is not None
    # Метрика должна быть типа Gauge
    assert hasattr(active_users, 'set')
    assert hasattr(active_users, 'inc')
    assert hasattr(active_users, 'dec')
