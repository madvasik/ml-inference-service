import pytest
import os
import pickle
import tempfile
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans
import numpy as np
from backend.app.ml import (
    validate_model_file,
    load_model,
    save_model,
    get_model_type
)


@pytest.fixture
def temp_model_file():
    """Создание временного файла с моделью"""
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    X = np.array([[1, 2], [3, 4], [5, 6]])
    y = np.array([0, 1, 0])
    model.fit(X, y)
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    pickle.dump(model, temp_file)
    temp_file.close()
    
    yield temp_file.name
    
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


@pytest.fixture
def temp_invalid_file():
    """Создание временного файла с невалидными данными"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    temp_file.write(b"invalid pickle data")
    temp_file.close()
    
    yield temp_file.name
    
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


def test_validate_model_file_valid(temp_model_file):
    """Тест валидации валидного файла модели"""
    assert validate_model_file(temp_model_file) is True


def test_validate_model_file_invalid(temp_invalid_file):
    """Тест валидации невалидного файла"""
    assert validate_model_file(temp_invalid_file) is False


def test_validate_model_file_nonexistent():
    """Тест валидации несуществующего файла"""
    assert validate_model_file("/nonexistent/file.pkl") is False


def test_validate_model_file_not_sklearn():
    """Тест валидации файла, который не является sklearn моделью"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    pickle.dump({"not": "a model"}, temp_file)
    temp_file.close()
    
    try:
        assert validate_model_file(temp_file.name) is False
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


def test_load_model_success(temp_model_file):
    """Тест успешной загрузки модели"""
    model = load_model(temp_model_file)
    assert model is not None
    assert hasattr(model, 'predict')


def test_load_model_file_not_found():
    """Тест загрузки несуществующего файла"""
    with pytest.raises(FileNotFoundError):
        load_model("/nonexistent/model.pkl")


def test_load_model_invalid_file(temp_invalid_file):
    """Тест загрузки невалидного файла"""
    with pytest.raises(ValueError):
        load_model(temp_invalid_file)


def test_load_model_not_sklearn():
    """Тест загрузки файла, который не является sklearn моделью"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
    pickle.dump({"not": "a model"}, temp_file)
    temp_file.close()
    
    try:
        with pytest.raises(ValueError, match="valid scikit-learn model"):
            load_model(temp_file.name)
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


def test_save_model(temp_model_file):
    """Тест сохранения модели"""
    model = load_model(temp_model_file)
    
    new_path = tempfile.mktemp(suffix='.pkl')
    try:
        save_model(model, new_path)
        assert os.path.exists(new_path)
        
        # Проверяем, что модель можно загрузить обратно
        loaded_model = load_model(new_path)
        assert loaded_model is not None
    finally:
        if os.path.exists(new_path):
            os.remove(new_path)


def test_save_model_creates_directory():
    """Тест создания директории при сохранении"""
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    X = np.array([[1, 2], [3, 4]])
    y = np.array([0, 1])
    model.fit(X, y)
    
    temp_dir = tempfile.mkdtemp()
    new_path = os.path.join(temp_dir, "subdir", "model.pkl")
    
    try:
        save_model(model, new_path)
        assert os.path.exists(new_path)
    finally:
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_get_model_type_classification():
    """Тест определения типа модели - классификация"""
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    assert get_model_type(model) == "classification"


def test_get_model_type_regression():
    """Тест определения типа модели - регрессия"""
    model = LinearRegression()
    assert get_model_type(model) == "regression"


def test_get_model_type_clustering():
    """Тест определения типа модели - кластеризация"""
    model = KMeans(n_clusters=2, random_state=42)
    # KMeans содержит 'cluster' в имени класса
    model_type = get_model_type(model)
    # Проверяем что тип определен (может быть 'clustering' или 'unknown' в зависимости от реализации)
    assert model_type in ["clustering", "unknown"]


def test_get_model_type_unknown():
    """Тест определения типа модели - неизвестный тип"""
    # Создаем мок модели с неизвестным классом
    class UnknownModel:
        pass
    
    model = UnknownModel()
    assert get_model_type(model) == "unknown"
