import pickle
import os
from typing import Optional
from sklearn.base import BaseEstimator
from backend.app.config import settings


def validate_model_file(file_path: str) -> bool:
    """Валидация pickle файла модели"""
    try:
        with open(file_path, 'rb') as f:
            model = pickle.load(f)
            if not isinstance(model, BaseEstimator):
                return False
        return True
    except Exception:
        return False


def load_model(file_path: str) -> Optional[BaseEstimator]:
    """Загрузка модели из файла"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Model file not found: {file_path}")
    
    try:
        with open(file_path, 'rb') as f:
            model = pickle.load(f)
            if not isinstance(model, BaseEstimator):
                raise ValueError("File does not contain a valid scikit-learn model")
            return model
    except Exception as e:
        raise ValueError(f"Failed to load model: {str(e)}")


def save_model(model: BaseEstimator, file_path: str) -> None:
    """Сохранение модели в файл"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb') as f:
        pickle.dump(model, f)


def get_model_type(model: BaseEstimator) -> str:
    """Определение типа модели"""
    model_class = model.__class__.__name__.lower()
    
    if 'classifier' in model_class or 'classif' in model_class:
        return "classification"
    elif 'regressor' in model_class or 'regress' in model_class:
        return "regression"
    elif 'cluster' in model_class:
        return "clustering"
    else:
        return "unknown"
