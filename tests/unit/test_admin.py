import pytest
from fastapi import status
from backend.app.domain.models.user import User, UserRole
from backend.app.domain.models.prediction import Prediction, PredictionStatus
from backend.app.domain.models.ml_model import MLModel


@pytest.fixture
def admin_user(db_session, test_user):
    """Создание администратора"""
    from backend.app.auth.security import get_password_hash
    admin = User(
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword"),
        role=UserRole.ADMIN
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def another_user(db_session):
    """Создание другого пользователя"""
    from backend.app.auth.security import get_password_hash
    user = User(
        email="another@example.com",
        password_hash=get_password_hash("anotherpassword"),
        role=UserRole.USER
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_list_all_users_as_admin(client, admin_user, test_user, another_user):
    """Тест получения списка всех пользователей администратором"""
    from backend.app.auth.jwt import create_access_token
    
    # Создаем токен напрямую для теста (более надежно чем логин)
    token = create_access_token({"sub": str(admin_user.id), "type": "access"})
    
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 2  # Должно быть минимум admin_user и test_user


def test_list_all_users_pagination(client, admin_user, db_session):
    """Тест пагинации списка пользователей"""
    from backend.app.auth.security import get_password_hash
    # Создаем несколько пользователей
    for i in range(5):
        user = User(
            email=f"user{i}@example.com",
            password_hash=get_password_hash(f"password{i}"),
            role=UserRole.USER
        )
        db_session.add(user)
    db_session.commit()
    
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        "/api/v1/admin/users?skip=0&limit=3",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) <= 3


def test_get_user_by_id(client, admin_user, test_user):
    """Тест получения пользователя по ID"""
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        f"/api/v1/admin/users/{test_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email


def test_get_user_not_found(client, admin_user):
    """Тест получения несуществующего пользователя"""
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        "/api/v1/admin/users/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_list_all_predictions(client, admin_user, test_user, test_ml_model, db_session):
    """Тест получения списка всех предсказаний"""
    # Создаем несколько предсказаний
    for i in range(3):
        prediction = Prediction(
            user_id=test_user.id,
            model_id=test_ml_model.id,
            input_data={"feature": i},
            status=PredictionStatus.COMPLETED,
            credits_spent=10
        )
        db_session.add(prediction)
    db_session.commit()
    
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        "/api/v1/admin/predictions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 3
    assert len(data["predictions"]) >= 3


def test_list_predictions_filtered_by_user_id(client, admin_user, test_user, another_user, test_ml_model, db_session):
    """Тест фильтрации предсказаний по user_id"""
    # Создаем предсказания для разных пользователей
    prediction1 = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature": 1},
        status=PredictionStatus.COMPLETED,
        credits_spent=10
    )
    prediction2 = Prediction(
        user_id=another_user.id,
        model_id=test_ml_model.id,
        input_data={"feature": 2},
        status=PredictionStatus.COMPLETED,
        credits_spent=10
    )
    db_session.add_all([prediction1, prediction2])
    db_session.commit()
    
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        f"/api/v1/admin/predictions?user_id={test_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert all(p["user_id"] == test_user.id for p in data["predictions"])


def test_list_predictions_filtered_by_model_id(client, admin_user, test_user, test_ml_model, db_session):
    """Тест фильтрации предсказаний по model_id"""
    # Создаем другую модель
    from backend.app.domain.models.ml_model import MLModel
    model2 = MLModel(
        owner_id=test_user.id,
        model_name="model2",
        file_path="/path/to/model2.pkl",
        model_type="classification"
    )
    db_session.add(model2)
    db_session.commit()
    
    # Создаем предсказания для разных моделей
    prediction1 = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature": 1},
        status=PredictionStatus.COMPLETED,
        credits_spent=10
    )
    prediction2 = Prediction(
        user_id=test_user.id,
        model_id=model2.id,
        input_data={"feature": 2},
        status=PredictionStatus.COMPLETED,
        credits_spent=10
    )
    db_session.add_all([prediction1, prediction2])
    db_session.commit()
    
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        f"/api/v1/admin/predictions?model_id={test_ml_model.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert all(p["model_id"] == test_ml_model.id for p in data["predictions"])


def test_get_prediction_by_id(client, admin_user, test_user, test_ml_model, db_session):
    """Тест получения предсказания по ID"""
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature": 1},
        status=PredictionStatus.COMPLETED,
        credits_spent=10
    )
    db_session.add(prediction)
    db_session.commit()
    
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        f"/api/v1/admin/predictions/{prediction.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == prediction.id


def test_get_prediction_not_found(client, admin_user):
    """Тест получения несуществующего предсказания"""
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(admin_user.id)})
    
    response = client.get(
        "/api/v1/admin/predictions/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_admin_endpoints_require_admin(client, test_user):
    """Тест, что админские endpoints требуют прав администратора"""
    from backend.app.auth.jwt import create_access_token
    token = create_access_token({"sub": str(test_user.id)})  # Обычный пользователь
    
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
