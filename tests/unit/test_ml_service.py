import pytest
import numpy as np
from unittest.mock import Mock, patch
from sklearn.ensemble import RandomForestClassifier
from backend.app.services.ml_service import predict, prepare_features


def test_prepare_features_with_feature_names():
    """Тест подготовки фичей с указанными именами"""
    input_data = {"feature1": 1.5, "feature2": 2.5, "feature3": 3.5}
    feature_names = ["feature1", "feature2", "feature3"]
    
    result = prepare_features(input_data, feature_names)
    
    assert result.shape == (1, 3)
    assert np.array_equal(result, np.array([[1.5, 2.5, 3.5]]))


def test_prepare_features_without_feature_names():
    """Тест подготовки фичей без указанных имен"""
    input_data = {"feature1": 1.5, "feature2": 2.5}
    
    result = prepare_features(input_data)
    
    assert result.shape == (1, 2)
    assert np.array_equal(result, np.array([[1.5, 2.5]]))


def test_prepare_features_missing_feature():
    """Тест подготовки фичей с отсутствующими значениями"""
    input_data = {"feature1": 1.5}
    feature_names = ["feature1", "feature2", "feature3"]
    
    result = prepare_features(input_data, feature_names)
    
    assert result.shape == (1, 3)
    assert result[0][0] == 1.5
    assert result[0][1] == 0  # Отсутствующие значения заменяются на 0
    assert result[0][2] == 0


def test_predict_classification():
    """Тест предсказания для классификации"""
    # Создаем простую модель классификации
    X = np.array([[1, 2], [3, 4], [5, 6]])
    y = np.array([0, 1, 0])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    
    input_data = {"feature1": 1.0, "feature2": 2.0}
    result = predict(model, input_data)
    
    assert "prediction" in result
    assert isinstance(result["prediction"], (int, float, list))
    assert "probabilities" in result  # Для классификатора должны быть вероятности


def test_predict_with_feature_names():
    """Тест предсказания с feature_names_in_"""
    import warnings
    
    X = np.array([[1, 2], [3, 4], [5, 6]])
    y = np.array([0, 1, 0])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    # Устанавливаем feature_names_in_ (это делается автоматически в новых версиях sklearn)
    model.feature_names_in_ = np.array(["feature1", "feature2"])
    
    input_data = {"feature1": 1.0, "feature2": 2.0}
    
    # Подавляем warning от sklearn про feature names
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
        result = predict(model, input_data)
    
    assert "prediction" in result


def test_predict_error():
    """Тест обработки ошибки при предсказании"""
    model = Mock()
    model.predict.side_effect = Exception("Test error")
    
    input_data = {"feature1": 1.0}
    
    with pytest.raises(ValueError, match="Prediction failed"):
        predict(model, input_data)


def test_predict_with_numpy_array_result():
    """Тест предсказания с numpy array результатом"""
    X = np.array([[1, 2], [3, 4], [5, 6]])
    y = np.array([0, 1, 0])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    
    # Мокируем predict чтобы вернуть numpy array
    original_predict = model.predict
    def mock_predict(X):
        result = original_predict(X)
        return np.array([result[0]])  # Возвращаем как numpy array
    model.predict = mock_predict
    
    input_data = {"feature1": 1.0, "feature2": 2.0}
    result = predict(model, input_data)
    
    assert "prediction" in result
    assert isinstance(result["prediction"], (int, float, list))
