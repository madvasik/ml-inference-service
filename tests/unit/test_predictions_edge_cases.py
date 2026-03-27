from fastapi import status

from backend.app.models import MLModel, Prediction, PredictionStatus, User, UserRole
from backend.app.security import create_access_token, get_password_hash


def test_get_prediction_not_found(client, test_user):
    """Тест получения несуществующего предсказания"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    response = client.get(
        "/api/v1/predictions/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Prediction not found" in response.json()["detail"]


def test_get_prediction_other_user(client, test_user, db_session):
    """Тест получения предсказания другого пользователя"""
    # Создаем другого пользователя
    other_user = User(
        email="other@example.com",
        password_hash=get_password_hash("password"),
        role=UserRole.USER
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    
    # Создаем модель для другого пользователя
    model = MLModel(
        owner_id=other_user.id,
        model_name="other_model",
        file_path="/path/to/model.pkl",
        model_type="classification"
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)
    
    # Создаем предсказание для другого пользователя
    prediction = Prediction(
        user_id=other_user.id,
        model_id=model.id,
        input_data={"feature": 1},
        status=PredictionStatus.COMPLETED,
        credits_spent=10
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)
    
    # Пытаемся получить предсказание от имени первого пользователя
    token = create_access_token({"sub": str(test_user.id), "type": "access"})
    
    response = client.get(
        f"/api/v1/predictions/{prediction.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Prediction not found" in response.json()["detail"]
