import pytest
import os
import tempfile
import pickle
from fastapi import status
from sklearn.ensemble import RandomForestClassifier
import numpy as np

from backend.app.config import settings
from backend.app.security import create_access_token


def test_upload_model_invalid_extension(client, test_user):
    """Тест загрузки модели с невалидным расширением"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    # Создаем файл с неправильным расширением
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    temp_file.write(b"not a model")
    temp_file.close()
    
    try:
        with open(temp_file.name, 'rb') as f:
            response = client.post(
                "/api/v1/models/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("model.txt", f, "text/plain")},
                data={"model_name": "test_model"}
            )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only .pkl files" in response.json()["detail"]
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


def test_upload_model_no_filename(client, test_user):
    """Тест загрузки модели без имени файла"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    # Создаем файл модели
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    X = np.array([[1, 2], [3, 4]])
    y = np.array([0, 1])
    model.fit(X, y)
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    pickle.dump(model, temp_file)
    temp_file.close()
    
    try:
        with open(temp_file.name, 'rb') as f:
            response = client.post(
                "/api/v1/models/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("", f, "application/octet-stream")},  # Пустое имя файла
                data={"model_name": "test_model"}
            )
        
        # FastAPI может вернуть 422 для валидации или 400 для бизнес-логики
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT]
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


def test_upload_model_file_too_large(client, test_user, monkeypatch):
    """Тест загрузки модели с превышением размера файла"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    # Временно уменьшаем максимальный размер файла
    original_max_size = settings.max_upload_size_mb
    monkeypatch.setattr(settings, "max_upload_size_mb", 0.001)  # 1 KB
    
    try:
        # Создаем большой файл
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
        temp_file.write(b"x" * (2 * 1024))  # 2 KB
        temp_file.close()
        
        try:
            with open(temp_file.name, 'rb') as f:
                response = client.post(
                    "/api/v1/models/upload",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("model.pkl", f, "application/octet-stream")},
                    data={"model_name": "test_model"}
                )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "File size exceeds" in response.json()["detail"]
        finally:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
    finally:
        monkeypatch.setattr(settings, "max_upload_size_mb", original_max_size)


def test_upload_model_empty_name(client, test_user, test_model_file):
    """Тест загрузки модели с пустым именем"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    with open(test_model_file, 'rb') as f:
        response = client.post(
            "/api/v1/models/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("model.pkl", f, "application/octet-stream")},
            data={"model_name": ""}  # Пустое имя
        )
    
    # FastAPI может вернуть 422 для валидации или 400 для бизнес-логики
    # Используем HTTP_422_UNPROCESSABLE_CONTENT вместо устаревшего HTTP_422_UNPROCESSABLE_ENTITY
    assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT]
    if response.status_code == status.HTTP_400_BAD_REQUEST:
        assert "cannot be empty" in response.json()["detail"]


def test_upload_model_name_too_long(client, test_user, test_model_file):
    """Тест загрузки модели с слишком длинным именем"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    long_name = "a" * 256  # 256 символов
    
    with open(test_model_file, 'rb') as f:
        response = client.post(
            "/api/v1/models/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("model.pkl", f, "application/octet-stream")},
            data={"model_name": long_name}
        )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "too long" in response.json()["detail"]


def test_upload_model_invalid_file(client, test_user):
    """Тест загрузки невалидного файла модели"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    # Создаем файл, который не является валидной моделью
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    pickle.dump({"not": "a model"}, temp_file)
    temp_file.close()
    
    try:
        with open(temp_file.name, 'rb') as f:
            response = client.post(
                "/api/v1/models/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("model.pkl", f, "application/octet-stream")},
                data={"model_name": "test_model"}
            )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid model file" in response.json()["detail"]
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


def test_upload_model_sanitizes_user_supplied_filename(client, test_user, test_model_file):
    """Тест, что имя файла пользователя не может вывести запись за пределы директории пользователя."""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})
    escaped_path = os.path.join(settings.ml_models_dir, "escape.pkl")

    if os.path.exists(escaped_path):
        os.remove(escaped_path)

    with open(test_model_file, 'rb') as f:
        response = client.post(
            "/api/v1/models/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("../../../escape.pkl", f, "application/octet-stream")},
            data={"model_name": "safe_model"}
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["file_path"].startswith(os.path.join(settings.ml_models_dir, str(test_user.id)))
    assert not os.path.exists(escaped_path)


def test_upload_model_server_error(client, test_user, test_model_file, monkeypatch):
    """Тест обработки серверной ошибки при загрузке модели"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    # Мокируем os.rename чтобы вызвать исключение при переименовании файла
    original_rename = os.rename
    
    def mock_rename(src, dst):
        raise OSError("Permission denied")
    
    monkeypatch.setattr(os, "rename", mock_rename)
    
    try:
        with open(test_model_file, 'rb') as f:
            response = client.post(
                "/api/v1/models/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("model.pkl", f, "application/octet-stream")},
                data={"model_name": "test_model"}
            )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to upload model" in response.json()["detail"]
    finally:
        monkeypatch.setattr(os, "rename", original_rename)


def test_get_model_not_found(client, test_user):
    """Тест получения несуществующей модели"""
    token = create_access_token({"sub": str(test_user.id), "type": "access"})

    response = client.get(
        "/api/v1/models/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Model not found" in response.json()["detail"]
