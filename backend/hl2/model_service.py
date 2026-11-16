"""
Loads the model artifacts and answers scoring questions.

Artifacts (made by the Colab notebook, folder `artifacts/`):
    model_card.json   threshold, metrics, limitations, global importance
    train.csv         the 614 training rows (zeros already turned into blanks)

TabPFN has no separate "training" step: it is created and `fit` on train.csv when the server starts
(a quick operation), using the TABPFN_TOKEN environment variable to download the weights.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml" / "src"))  # explain_agnostic.py lives in ml/src
from explain_agnostic import ShapleyExplainer, choose_background, find_counterfactuals, top_factors  # noqa: E402

FEATURES = ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"]
OPTIONAL = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]   # 0 / null = not measured


TABPFN_SETTINGS = {"fit_mode": "fit_with_cache", "n_estimators": 1}   # same as benchmark.py; the model card records the settings used


def _default_factory(settings=None):
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion

    return TabPFNClassifier.create_default_for_version(ModelVersion.V3_5, random_state=42, **(settings or TABPFN_SETTINGS))


class ModelService:
    def __init__(self, card: Dict[str, Any], train: pd.DataFrame, estimator):
        self.card = card
        self.threshold: float = float(card["threshold"])
        self._lock = threading.Lock()          # one prediction at a time (model objects are not guaranteed thread-safe)
        self.medians: Dict[str, float] = {f: float(train[f].median()) for f in FEATURES}   # shown for "not measured" fields
        self.estimator = estimator.fit(train[FEATURES], train["Outcome"])
        self.predict(train[FEATURES].iloc[:1].values)   # warm-up call, so the first visitor does not pay for it
        bg = choose_background(train[FEATURES].values, int(card.get("background_k", 4)))   # same rule as the notebook
        self.explainer = ShapleyExplainer(self.predict, bg, FEATURES)

    @classmethod
    def load(cls, art_dir: Optional[str] = None, factory: Optional[Callable[[], Any]] = None) -> "ModelService":
        art = Path(art_dir or os.environ.get("ARTIFACT_DIR", "artifacts"))
        card = json.loads((art / "model_card.json").read_text())
        train = pd.read_csv(art / "train.csv")
        settings = (card.get("model") or {}).get("settings") or None
        return cls(card, train, factory() if factory else _default_factory(settings))

    # ------------------------------------------------------------------ scoring
    def predict(self, X: np.ndarray) -> np.ndarray:
        with self._lock:
            return np.asarray(self.estimator.predict_proba(pd.DataFrame(np.asarray(X, dtype=float), columns=FEATURES))[:, 1], dtype=float)

    @staticmethod
    def row(inputs: Dict[str, Optional[float]]) -> np.ndarray:
        return np.array([np.nan if inputs.get(f) is None else float(inputs[f]) for f in FEATURES], dtype=float)

    def score(self, inputs: Dict[str, Optional[float]]) -> float:
        return float(self.predict(self.row(inputs)[None, :])[0])

    def assess(self, inputs: Dict[str, Optional[float]]) -> Dict[str, Any]:
        x = self.row(inputs)
        score = float(self.predict(x[None, :])[0])
        flagged = score >= self.threshold
        expl = self.explainer.explain(x)
        factors = [{**f, "entered": inputs.get(f["feature"]) is not None, "value": inputs.get(f["feature"])}
                   for f in top_factors(expl, k=len(FEATURES))]
        cf = find_counterfactuals(x, FEATURES, self.predict, self.threshold) if flagged else None
        return {
            "score": score, "threshold": self.threshold, "flagged": flagged,
            "base_score": expl["base_value"], "factors": factors,
            "counterfactuals": cf,
            "not_entered": [f for f in OPTIONAL if inputs.get(f) is None],
        }
