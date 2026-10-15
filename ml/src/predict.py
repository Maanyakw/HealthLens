"""
Load the saved HealthLens model and score one patient.

    python ml/src/predict.py

The same predict_one() function is what the FastAPI endpoint will call later.
"""

import json
from pathlib import Path

import joblib
import pandas as pd

import features  # noqa: F401  (the pickled model needs this module importable)
from features import BASE_FEATURES

MODELS_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"


def load_model():
    model = joblib.load(MODELS_DIR / "model.joblib")
    with open(MODELS_DIR / "model_card.json") as f:
        card = json.load(f)
    return model, card


def predict_one(record, model=None, card=None):
    """record: dict with the 8 input fields. Zeros in Glucose/BP/Skin/Insulin/BMI are treated as 'not measured'."""
    if model is None or card is None:
        model, card = load_model()
    missing = [c for c in BASE_FEATURES if c not in record]
    if missing:
        raise ValueError(f"Missing fields: {missing}")
    row = pd.DataFrame([record])[BASE_FEATURES]
    probability = float(model.predict_proba(row)[0, 1])
    return {
        "probability": probability,
        "threshold": card["threshold"],
        "flagged_higher_risk": probability >= card["threshold"],
    }


if __name__ == "__main__":
    example = {
        "Pregnancies": 1,
        "Glucose": 118,
        "BloodPressure": 76,
        "SkinThickness": 25,
        "Insulin": 0,  # 0 = not measured -> imputed
        "BMI": 24.8,
        "DiabetesPedigreeFunction": 0.35,
        "Age": 24,
    }
    print(predict_one(example))
