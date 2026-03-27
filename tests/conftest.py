import pytest
import os
import tempfile
import pickle
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sklearn.ensemble import RandomForestClassifier
import numpy as np

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app import main as main_module
from backend.app.db import session as db_session_module
from backend.app.workers import loyalty_tasks as loyalty_tasks_module
from backend.app.workers import prediction_tasks as prediction_tasks_module
from backend.app.domain.models.user import User, UserRole
from backend.app.domain.models.balance import Balance
from backend.app.domain.models.ml_model import MLModel
from backend.app.auth.security import get_password_hash

@pytest.fixture(scope="function")
def testing_session_factory(tmp_path):
    """Изолированная SQLite-сессия на каждый тест."""
    database_path = tmp_path / "test.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield testing_session_local
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def override_session_locals(monkeypatch, testing_session_factory):
    """Подменяет SessionLocal во всех runtime-модулях на временную SQLite-сессию."""
    monkeypatch.setattr(main_module, "SessionLocal", testing_session_factory)
    monkeypatch.setattr(db_session_module, "SessionLocal", testing_session_factory)
    monkeypatch.setattr(prediction_tasks_module, "SessionLocal", testing_session_factory)
    monkeypatch.setattr(loyalty_tasks_module, "SessionLocal", testing_session_factory)
    yield


@pytest.fixture(scope="function")
def db_session(testing_session_factory):
    """Создание тестовой сессии БД"""
    db = testing_session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Тестовый клиент FastAPI"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Создание тестового пользователя"""
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        role=UserRole.USER
    )
    db_session.add(user)
    db_session.flush()
    
    balance = Balance(user_id=user.id, credits=1000)
    db_session.add(balance)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture
def test_model_file():
    """Создание временного файла с тестовой моделью"""
    # Создание простой модели
    X = np.array([[1, 2], [3, 4], [5, 6]])
    y = np.array([0, 1, 0])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    
    # Сохранение во временный файл
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    pickle.dump(model, temp_file)
    temp_file.close()
    
    yield temp_file.name
    
    # Удаление файла после теста
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


@pytest.fixture
def test_ml_model(db_session, test_user, test_model_file):
    """Создание тестовой ML модели в БД"""
    model = MLModel(
        owner_id=test_user.id,
        model_name="test_model",
        file_path=test_model_file,
        model_type="classification"
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)
    
    return model


@pytest.fixture
def mock_redis():
    """Мок для Redis (для тестов Celery)"""
    from unittest.mock import Mock
    redis_mock = Mock()
    return redis_mock


@pytest.fixture
def mock_celery_app():
    """Мок для Celery app"""
    from unittest.mock import Mock
    celery_app = Mock()
    return celery_app
