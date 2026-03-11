import numpy as np
from typing import Dict, Any, List
from sklearn.base import BaseEstimator


def prepare_features(input_data: Dict[str, Any], feature_names: List[str] = None) -> np.ndarray:
    """Подготовка фичей из JSON словаря в numpy array"""
    if feature_names:
        # Если указаны названия фичей, используем их порядок
        features = [input_data.get(name, 0) for name in feature_names]
    else:
        # Иначе используем порядок ключей в словаре
        features = list(input_data.values())
    
    return np.array(features).reshape(1, -1)


def predict(model: BaseEstimator, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Выполнение предсказания"""
    try:
        # Получение названий фичей из модели (если доступно)
        feature_names = None
        if hasattr(model, 'feature_names_in_'):
            feature_names = model.feature_names_in_.tolist()
        
        # Подготовка фичей
        features = prepare_features(input_data, feature_names)
        
        # Выполнение предсказания
        prediction = model.predict(features)
        
        # Получение вероятностей (если доступно)
        result = {"prediction": prediction[0].tolist() if isinstance(prediction[0], np.ndarray) else float(prediction[0])}
        
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(features)
            result["probabilities"] = probabilities[0].tolist()
        
        return result
        
    except Exception as e:
        raise ValueError(f"Prediction failed: {str(e)}")
