import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.base import BaseEstimator


def validate_model_file(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as file:
            model = pickle.load(file)
            return isinstance(model, BaseEstimator)
    except Exception:
        return False


def load_model(file_path: str) -> Optional[BaseEstimator]:
    model_path = Path(file_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {file_path}")

    try:
        with open(model_path, "rb") as file:
            model = pickle.load(file)
            if not isinstance(model, BaseEstimator):
                raise ValueError("File does not contain a valid scikit-learn model")
            return model
    except Exception as exc:
        raise ValueError(f"Failed to load model: {exc}")


def save_model(model: BaseEstimator, file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as file:
        pickle.dump(model, file)


def get_model_type(model: BaseEstimator) -> str:
    model_class = model.__class__.__name__.lower()
    if "classifier" in model_class or "classif" in model_class:
        return "classification"
    if "regressor" in model_class or "regress" in model_class:
        return "regression"
    if "cluster" in model_class:
        return "clustering"
    return "unknown"


def prepare_features(input_data: Dict[str, Any], feature_names: List[str] = None) -> np.ndarray:
    features = [input_data.get(name, 0) for name in feature_names] if feature_names else list(input_data.values())
    return np.array(features).reshape(1, -1)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_to_jsonable(item) for item in value.tolist()]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def predict(model: BaseEstimator, input_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        feature_names = model.feature_names_in_.tolist() if hasattr(model, "feature_names_in_") else None
        features = prepare_features(input_data, feature_names)
        prediction = model.predict(features)
        result = {"prediction": _to_jsonable(prediction[0])}
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(features)
            result["probabilities"] = _to_jsonable(probabilities[0])
        return result
    except Exception as exc:
        raise ValueError(f"Prediction failed: {exc}")
