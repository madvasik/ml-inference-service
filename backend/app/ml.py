from pathlib import Path
from typing import Any

import numpy as np
from skops.io import get_untrusted_types, load as skops_load
from sklearn.base import BaseEstimator


def validate_model_file(file_path: str) -> bool:
    model_path = Path(file_path)
    if not model_path.exists():
        return False

    try:
        if get_untrusted_types(file=model_path):
            return False

        model = skops_load(model_path, trusted=[])
        return isinstance(model, BaseEstimator)
    except Exception:
        return False


def load_model(file_path: str) -> BaseEstimator:
    model_path = Path(file_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {file_path}")

    try:
        untrusted_types = get_untrusted_types(file=model_path)
        if untrusted_types:
            raise ValueError("Model file contains untrusted types")

        model = skops_load(model_path, trusted=[])
        if not isinstance(model, BaseEstimator):
            raise ValueError("File does not contain a valid scikit-learn model")
        return model
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Failed to load model: {exc}")


def get_model_type(model: BaseEstimator) -> str:
    model_class = model.__class__.__name__.lower()
    if "classifier" in model_class or "classif" in model_class:
        return "classification"
    if "regressor" in model_class or "regress" in model_class:
        return "regression"
    if "cluster" in model_class or model_class.endswith("means"):
        return "clustering"
    return "unknown"


def get_feature_names(model: BaseEstimator) -> list[str] | None:
    if not hasattr(model, "feature_names_in_"):
        return None

    feature_names = model.feature_names_in_
    if hasattr(feature_names, "tolist"):
        feature_names = feature_names.tolist()
    return [str(name) for name in feature_names]


def validate_input_features(input_data: dict[str, Any], feature_names: list[str] | None) -> None:
    if not feature_names:
        raise ValueError("Model feature schema is unavailable")

    missing_features = [name for name in feature_names if name not in input_data]
    unexpected_features = [name for name in input_data if name not in feature_names]
    if missing_features or unexpected_features:
        details = []
        if missing_features:
            details.append(f"missing features: {', '.join(missing_features)}")
        if unexpected_features:
            details.append(f"unexpected features: {', '.join(unexpected_features)}")
        raise ValueError("; ".join(details))


def prepare_features(input_data: dict[str, Any], feature_names: list[str] | None = None) -> np.ndarray:
    validate_input_features(input_data, feature_names)
    features = [input_data[name] for name in feature_names]
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


def predict(model: BaseEstimator, input_data: dict[str, Any], feature_names: list[str] | None = None) -> dict[str, Any]:
    try:
        resolved_feature_names = feature_names or get_feature_names(model)
        features = prepare_features(input_data, resolved_feature_names)
        prediction = model.predict(features)
        result = {"prediction": _to_jsonable(prediction[0])}
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(features)
            result["probabilities"] = _to_jsonable(probabilities[0])
        return result
    except Exception as exc:
        raise ValueError(f"Prediction failed: {exc}")
