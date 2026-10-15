"""
Explain HealthLens predictions: which factors pushed a patient's risk up or
down (SHAP), and what changes would bring a flagged patient below the
screening threshold (DiCE what-ifs).

Run from the project root to create the plots and the saved explainer data:

    python ml/src/explain.py

Use from code (this is what the FastAPI app will call):

    from explain import HealthLensExplainer
    ex = HealthLensExplainer()
    ex.explain_one(record)                 # top factors for one patient
    ex.what_if(record, {"Glucose": 100})   # probability before / after an edit
    ex.counterfactuals(record)             # smallest changes that drop below the threshold

Important notes
- Requires `python ml/src/train.py` to have been run first.
- SHAP explains the UNCALIBRATED pipeline (models/pipeline_uncalibrated.joblib).
  The probability shown to users comes from the calibrated model, which is just
  a rising S-curve on top, so a factor that raises the pipeline's score also
  raises the calibrated probability. Ranking and direction carry over.
- For logistic regression (the current winner) the impact of a factor is in
  log-odds: how far that factor moves this patient away from the average
  training patient. Positive = raises risk, negative = lowers it.
- These explain what the MODEL does. They are not medical causes or advice.
"""

import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import LogisticRegression

import features  # noqa: F401  (saved models need this module importable)
from features import BASE_FEATURES, ZERO_AS_MISSING

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "ml" / "models"
REPORTS_DIR = ROOT / "ml" / "reports"

FEATURE_LABELS = {
    "Pregnancies": "Number of pregnancies",
    "Glucose": "Glucose",
    "BloodPressure": "Blood pressure (diastolic)",
    "SkinThickness": "Skin fold thickness",
    "Insulin": "Insulin",
    "BMI": "BMI",
    "DiabetesPedigreeFunction": "Family history score",
    "Age": "Age",
}

# Only these can reasonably change, so only these appear in what-if suggestions.
# The value is the lowest number a suggestion may propose (a plausible floor).
MODIFIABLE_FLOORS = {"Glucose": 70.0, "BMI": 18.5}


class _ThresholdAligned:
    """
    DiCE decides 'low risk' using a 0.5 cut-off. Our screening threshold is
    lower (about 0.28). This wrapper rescales probabilities so that 0.5 here
    means 'exactly at our threshold', so DiCE's counterfactuals really land
    below the threshold the app uses.
    """

    def __init__(self, model, threshold):
        self.model = model
        self.shift = float(np.log(threshold / (1 - threshold)))

    def predict_proba(self, X):
        p = np.clip(self.model.predict_proba(X)[:, 1], 1e-6, 1 - 1e-6)
        q = 1 / (1 + np.exp(-(np.log(p / (1 - p)) - self.shift)))
        return np.column_stack([1 - q, q])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


class HealthLensExplainer:
    def __init__(self, models_dir=MODELS_DIR):
        models_dir = Path(models_dir)
        self.model = joblib.load(models_dir / "model.joblib")
        self.pipeline = joblib.load(models_dir / "pipeline_uncalibrated.joblib")
        with open(models_dir / "model_card.json") as f:
            self.card = json.load(f)
        self.threshold = float(self.card["threshold"])

        data_path = models_dir / "explainer_data.joblib"
        if data_path.exists():
            data = joblib.load(data_path)
            self.X_train, self.y_train = data["X_train"], data["y_train"]
        else:
            # First run: rebuild the training split and save it for later use
            from train import get_split

            self.X_train, _, self.y_train, _ = get_split()
            joblib.dump({"X_train": self.X_train, "y_train": self.y_train}, data_path)

        self._preprocess = self.pipeline[:-1]  # zeros -> impute -> engineer -> scale -> select
        self._estimator = self.pipeline[-1]
        self.used_features = list(self._preprocess.get_feature_names_out(BASE_FEATURES))
        self.not_used_features = [f for f in BASE_FEATURES if f not in self.used_features]

        self._background = np.asarray(self._preprocess.transform(self.X_train), dtype=float)
        self._build_shap()
        self._dice = None

    # ------------------------------------------------------------------ SHAP
    def _build_shap(self):
        est = self._estimator
        if isinstance(est, LogisticRegression):
            self._shap = shap.LinearExplainer(est, self._background)
            self.unit = "log-odds"
            self.base_value = float(np.ravel(self._shap.expected_value)[0])
        else:
            # Any other model: model-agnostic explainer on the probability output
            def predict_fn(X):
                return est.predict_proba(X)[:, 1]

            sample = shap.sample(self._background, 100, random_state=0)
            self._shap = shap.Explainer(predict_fn, sample)
            self.unit = "probability"
            self.base_value = float(np.mean(predict_fn(sample)))

    def _shap_values(self, X):
        if self.unit == "log-odds":
            return np.asarray(self._shap.shap_values(X))
        return np.asarray(self._shap(X).values)

    def _check_record(self, record):
        missing = [c for c in BASE_FEATURES if c not in record]
        if missing:
            raise ValueError(f"Missing fields: {missing}")
        return pd.DataFrame([record])[BASE_FEATURES]

    def probability(self, record):
        return float(self.model.predict_proba(self._check_record(record))[0, 1])

    def explain_one(self, record, top=None):
        """Factors behind one patient's score, strongest first."""
        row = self._check_record(record)
        probability = float(self.model.predict_proba(row)[0, 1])
        x = np.asarray(self._preprocess.transform(row), dtype=float)
        values = self._shap_values(x)[0]

        # Values the model actually saw (after filling in 'not measured' zeros)
        seen = row
        for step_name in ("zeros", "impute", "engineer"):
            seen = self.pipeline.named_steps[step_name].transform(seen)
            if not isinstance(seen, pd.DataFrame):
                seen = pd.DataFrame(seen, columns=BASE_FEATURES)
        seen = seen.iloc[0]

        total = float(np.abs(values).sum()) or 1.0
        out = []
        for name, impact in zip(self.used_features, values):
            out.append(
                {
                    "feature": name,
                    "label": FEATURE_LABELS.get(name, name),
                    "value_used": round(float(seen[name]), 2),
                    "was_missing": bool(name in ZERO_AS_MISSING and record[name] == 0),
                    "impact": round(float(impact), 4),
                    "direction": "raises risk" if impact > 0 else "lowers risk",
                    "share": round(abs(float(impact)) / total, 4),
                }
            )
        out.sort(key=lambda d: abs(d["impact"]), reverse=True)
        return {
            "probability": probability,
            "threshold": self.threshold,
            "flagged_higher_risk": probability >= self.threshold,
            "unit": self.unit,
            "factors": out[:top] if top else out,
            "features_not_used_by_model": self.not_used_features,
        }

    def global_importance(self):
        """Average size of each factor's impact across the training patients."""
        values = self._shap_values(self._background)
        mean_abs = np.abs(values).mean(axis=0)
        df = pd.DataFrame(
            {
                "feature": self.used_features,
                "label": [FEATURE_LABELS.get(f, f) for f in self.used_features],
                "mean_abs_impact": mean_abs,
                "share": mean_abs / mean_abs.sum(),
            }
        ).sort_values("mean_abs_impact", ascending=False)
        return df.reset_index(drop=True), values

    def save_global_plots(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        imp, values = self.global_importance()

        plt.figure(figsize=(6.5, 4))
        order = imp.iloc[::-1]
        plt.barh(order["label"], order["mean_abs_impact"], color="#0b7a75")
        plt.xlabel(f"Average impact on risk ({self.unit})")
        plt.title("What drives the model's predictions")
        plt.tight_layout()
        plt.savefig(REPORTS_DIR / "shap_global_importance.png", dpi=150)
        plt.close()

        labels = [FEATURE_LABELS.get(f, f) for f in self.used_features]
        plt.figure()
        shap.summary_plot(values, self._background, feature_names=labels, show=False)
        plt.title("How each factor moves risk (each dot is one patient)")
        plt.tight_layout()
        plt.savefig(REPORTS_DIR / "shap_summary.png", dpi=150, bbox_inches="tight")
        plt.close()
        return imp

    # --------------------------------------------------------------- what-ifs
    def what_if(self, record, changes):
        """Probability before and after editing some inputs, e.g. {"Glucose": 100}."""
        before = self.probability(record)
        edited = {**record, **changes}
        after = self.probability(edited)
        return {
            "changes": dict(changes),
            "before": before,
            "after": after,
            "threshold": self.threshold,
            "flagged_before": before >= self.threshold,
            "flagged_after": after >= self.threshold,
        }

    def _get_dice(self):
        if self._dice is None:
            import dice_ml

            data = dice_ml.Data(
                dataframe=self.X_train.assign(Outcome=self.y_train.values),
                continuous_features=list(BASE_FEATURES),
                outcome_name="Outcome",
            )
            model = dice_ml.Model(
                model=_ThresholdAligned(self.model, self.threshold), backend="sklearn"
            )
            self._dice = dice_ml.Dice(data, model, method="random")
        return self._dice

    def counterfactuals(self, record, n=3, seed=42):
        """
        For a flagged patient: smallest Glucose / BMI reductions (within plausible
        limits) that bring the model's risk below the screening threshold.
        """
        row = self._check_record(record)
        p0 = float(self.model.predict_proba(row)[0, 1])
        if p0 < self.threshold:
            return {
                "flagged_higher_risk": False,
                "probability": p0,
                "options": [],
                "message": "Already below the screening threshold; no change needed.",
            }

        vary, ranges = [], {}
        for feat, floor in MODIFIABLE_FLOORS.items():
            current = float(record[feat])
            # skip features the model ignores, or that were not measured (0)
            if feat in self.used_features and current > floor + 0.5:
                vary.append(feat)
                ranges[feat] = [floor, current]
        if not vary:
            return {
                "flagged_higher_risk": True,
                "probability": p0,
                "options": [],
                "message": "No adjustable factor with room to change.",
            }

        try:
            res = self._get_dice().generate_counterfactuals(
                row,
                total_CFs=max(n * 3, 6),
                desired_class=0,
                features_to_vary=vary,
                permitted_range=ranges,
                random_seed=seed,
            )
            cfs = res.cf_examples_list[0].final_cfs_df
        except Exception as e:  # DiCE raises when it cannot find any option
            return {
                "flagged_higher_risk": True,
                "probability": p0,
                "options": [],
                "message": f"No option found within plausible limits ({type(e).__name__}).",
            }
        if cfs is None or len(cfs) == 0:
            return {
                "flagged_higher_risk": True,
                "probability": p0,
                "options": [],
                "message": "No option found within plausible limits.",
            }

        options, seen = [], set()
        for _, cf in cfs.iterrows():
            edited = dict(record)
            changes = []
            for feat in vary:
                new = round(float(cf[feat]), 0 if feat == "Glucose" else 1)
                old = float(record[feat])
                if abs(new - old) > 1e-9:
                    edited[feat] = new
                    changes.append(
                        {
                            "feature": feat,
                            "label": FEATURE_LABELS[feat],
                            "from": old,
                            "to": new,
                        }
                    )
            key = tuple((c["feature"], c["to"]) for c in changes)
            if not changes or key in seen:
                continue
            new_p = float(self.model.predict_proba(self._check_record(edited))[0, 1])
            if new_p >= self.threshold:  # keep only true successes
                continue
            seen.add(key)
            size = sum(abs(c["to"] - c["from"]) / c["from"] for c in changes)
            options.append({"changes": changes, "new_probability": new_p, "_size": size})

        options.sort(key=lambda o: o["_size"])
        for o in options:
            o.pop("_size")
        return {
            "flagged_higher_risk": True,
            "probability": p0,
            "threshold": self.threshold,
            "options": options[:n],
            "message": "" if options else "No option found within plausible limits.",
        }


def main():
    ex = HealthLensExplainer()
    imp = ex.save_global_plots()
    print(f"Explaining: {ex.card['model']} on {ex.card['feature_set']} features ({ex.unit})")
    print("\nGlobal importance (average impact across training patients):")
    print(imp[["label", "mean_abs_impact", "share"]].round(3).to_string(index=False))
    print(f"\nNot used by the model: {ex.not_used_features}")

    example = {
        "Pregnancies": 6,
        "Glucose": 170,
        "BloodPressure": 80,
        "SkinThickness": 35,
        "Insulin": 200,
        "BMI": 36,
        "DiabetesPedigreeFunction": 0.9,
        "Age": 50,
    }
    e = ex.explain_one(example)
    print(f"\nExample patient: probability {e['probability']:.2f}, flagged: {e['flagged_higher_risk']}")
    for f in e["factors"]:
        print(f"  {f['label']:<24} {f['value_used']:>7}  {f['impact']:+.2f}  ({f['direction']})")
    print("\nWhat would bring this patient below the threshold:")
    for o in ex.counterfactuals(example)["options"]:
        ch = ", ".join(f"{c['label']} {c['from']:g} -> {c['to']:g}" for c in o["changes"])
        print(f"  {ch}  =>  probability {o['new_probability']:.2f}")
    print(f"\nSaved plots to {REPORTS_DIR}")


if __name__ == "__main__":
    sys.exit(main())
