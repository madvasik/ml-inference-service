#!/usr/bin/env python3
"""Обучает демо-модель sklearn и сохраняет в scripts/sample_models/ (для загрузки в ML Inference)."""

from pathlib import Path

import joblib
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

OUT = Path(__file__).resolve().parent / "sample_models" / "example_model.joblib"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = RandomForestClassifier(n_estimators=15, max_depth=4, random_state=42)
    model.fit(X_train, y_train)
    joblib.dump(model, OUT)
    print(f"Сохранено: {OUT}")
    print("Вход для predict: 4 признака (как в Iris), например [5.1, 3.5, 1.4, 0.2]")
    print(f"Точность на отложенной выборке: {model.score(X_test, y_test):.3f}")


if __name__ == "__main__":
    main()
