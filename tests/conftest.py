import os
import pickle
import tempfile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sklearn.ensemble import RandomForestClassifier

from backend.app.config import settings
from backend.app.db import Base, get_db
from backend.app.main import app
import backend.app.db as db_module
import backend.app.main as main_module
import backend.app.worker as worker_module
from backend.app.models import Balance, MLModel, User, UserRole
from backend.app.security import create_access_token, get_password_hash

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
    monkeypatch.setattr(db_module, "SessionLocal", testing_session_factory)
    monkeypatch.setattr(worker_module, "SessionLocal", testing_session_factory)
    monkeypatch.setattr(main_module.db_module, "SessionLocal", testing_session_factory)
    yield


@pytest.fixture(autouse=True)
def isolate_model_storage(tmp_path, monkeypatch):
    models_dir = tmp_path / "ml_models"
    models_dir.mkdir()
    monkeypatch.setattr(settings, "ml_models_dir", str(models_dir))
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
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.flush()

    balance = Balance(user_id=user.id, credits=1000)
    db_session.add(balance)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def admin_user(db_session):
    user = User(
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword"),
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Balance(user_id=user.id, credits=1000))
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def access_token_for():
    def _build(user: User) -> str:
        return create_access_token(data={"sub": str(user.id), "email": user.email})

    return _build


@pytest.fixture
def test_model_file():
    X = np.array([[1, 2], [3, 4], [5, 6]])
    y = np.array([0, 1, 0])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
    pickle.dump(model, temp_file)
    temp_file.close()

    yield temp_file.name

    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


@pytest.fixture
def test_ml_model(db_session, test_user, test_model_file):
    model = MLModel(
        owner_id=test_user.id,
        model_name="test_model",
        file_path=test_model_file,
        model_type="classification",
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)

    return model
