import pickle
import tempfile

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans

from backend.app.ml import get_model_type, load_model, predict, prepare_features, validate_model_file


@pytest.fixture
def classifier_model(tmp_path):
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([0, 1, 0, 1])
    model = RandomForestClassifier(n_estimators=5, random_state=42)
    model.fit(X, y)
    path = tmp_path / "classifier.pkl"
    with open(path, "wb") as f:
        pickle.dump(model, f)
    return str(path), model


@pytest.fixture
def regressor_model(tmp_path):
    X = np.array([[1], [2], [3], [4]])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    model = LinearRegression()
    model.fit(X, y)
    path = tmp_path / "regressor.pkl"
    with open(path, "wb") as f:
        pickle.dump(model, f)
    return str(path), model


def test_validate_model_file_accepts_sklearn_model(classifier_model):
    path, _ = classifier_model
    assert validate_model_file(path) is True


def test_validate_model_file_rejects_non_sklearn_object(tmp_path):
    path = tmp_path / "bad.pkl"
    with open(path, "wb") as f:
        pickle.dump({"not": "a model"}, f)
    assert validate_model_file(path) is False


def test_validate_model_file_rejects_nonexistent_file():
    assert validate_model_file("/no/such/file.pkl") is False


def test_load_model_returns_sklearn_estimator(classifier_model):
    path, _ = classifier_model
    model = load_model(path)
    assert hasattr(model, "predict")


def test_load_model_raises_on_missing_file():
    with pytest.raises((FileNotFoundError, ValueError)):
        load_model("/no/such/file.pkl")


def test_load_model_raises_on_non_sklearn_object(tmp_path):
    path = tmp_path / "bad.pkl"
    with open(path, "wb") as f:
        pickle.dump("just a string", f)
    with pytest.raises(ValueError, match="Failed to load model"):
        load_model(str(path))


def test_get_model_type_classifier():
    model = RandomForestClassifier(n_estimators=2)
    model.fit([[1, 2]], [0])
    assert get_model_type(model) == "classification"


def test_get_model_type_regressor():
    model = LinearRegression()
    model.fit([[1]], [1.0])
    assert get_model_type(model) == "regression"


def test_get_model_type_clustering():
    model = KMeans(n_clusters=2)
    model.fit([[1, 2], [3, 4]])
    assert get_model_type(model) == "clustering"


def test_predict_returns_prediction_with_probabilities(classifier_model):
    _, model = classifier_model
    result = predict(model, {"feature1": 1.0, "feature2": 2.0})
    assert "prediction" in result
    assert "probabilities" in result


def test_predict_returns_prediction_without_probabilities(regressor_model):
    _, model = regressor_model
    result = predict(model, {"feature1": 2.5})
    assert "prediction" in result
    assert "probabilities" not in result


def test_predict_raises_on_invalid_input(classifier_model):
    _, model = classifier_model
    with pytest.raises(ValueError, match="Prediction failed"):
        predict(model, {})


def test_prepare_features_with_named_features():
    data = {"a": 1, "b": 2, "c": 3}
    features = prepare_features(data, feature_names=["c", "a"])
    assert features.shape == (1, 2)
    assert features[0][0] == 3
    assert features[0][1] == 1


def test_prepare_features_without_names():
    data = {"x": 10, "y": 20}
    features = prepare_features(data)
    assert features.shape == (1, 2)
