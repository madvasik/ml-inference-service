import pytest
import os
from fastapi import status


def test_upload_model(client, test_user, test_model_file):
    """Тест загрузки модели"""
    # Логинимся
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # Загружаем модель
    with open(test_model_file, 'rb') as f:
        response = client.post(
            "/api/v1/models/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("model.pkl", f, "application/octet-stream")},
            data={"model_name": "test_model"}
        )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["model_name"] == "test_model"
    assert data["owner_id"] == test_user.id
    assert "id" in data


def test_list_models(client, test_user, test_ml_model):
    """Тест получения списка моделей"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.get(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 1
    assert len(data["models"]) >= 1


def test_get_model(client, test_user, test_ml_model):
    """Тест получения информации о модели"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.get(
        f"/api/v1/models/{test_ml_model.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_ml_model.id


def test_delete_model(client, test_user, test_ml_model):
    """Тест удаления модели"""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    response = client.delete(
        f"/api/v1/models/{test_ml_model.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
