"""
HealthLens model benchmark: TabPFN-3.5 (primary) vs XGBoost vs Logistic Regression.

Protocol (same as the earlier project work, so numbers are comparable):
  * Pima Indians Diabetes, 768 rows, stratified 80/20 split  ->  614 train / 154 test
  * Zeros in Glucose, BloodPressure, SkinThickness, Insulin, BMI mean "not measured" -> NaN
  * Model selection and thresholds use TRAIN data only (5-fold CV, out-of-fold predictions)
  * The 154 test rows are touched once, at the end
  * Decision threshold = highest-precision threshold that still reaches recall >= 0.80
    on the train out-of-fold predictions

Run in Colab (notebook calls `run_benchmark`) or locally:
    python benchmark.py --data ../data/pima-indians-diabetes.csv --out results --no-tabpfn
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Callable, Dict

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# IMPORTANT: set this to the same value as RANDOM_STATE in your ml/src/train.py
# so the train/test split matches your earlier results.
RANDOM_STATE = 42
TARGET_RECALL = 0.80

FEATURES = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
    "Insulin", "BMI", "DiabetesPedigreeFunction", "Age",
]
ZERO_MEANS_MISSING = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]


# ----------------------------------------------------------------------------- data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=FEATURES + ["Outcome"])
    for c in ZERO_MEANS_MISSING:
        df[c] = df[c].replace(0, np.nan)
    assert len(df) == 768 and df.Outcome.sum() == 268, "unexpected dataset"
    return df


def split(df: pd.DataFrame):
    X, y = df[FEATURES], df["Outcome"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)


# ----------------------------------------------------------------------------- models
# TabPFN settings used everywhere (benchmark AND server). On a CPU, the defaults take about 45 s per call;
# caching the training context at fit time and using one ensemble member brings one patient to ~0.1 s
# (measured on a 2-CPU Colab runtime: test ROC-AUC 0.822 with and without these settings).
TABPFN_SETTINGS = {"fit_mode": "fit_with_cache", "n_estimators": 1}


def make_tabpfn():
    """TabPFN-3.5. Reads the token from the TABPFN_TOKEN environment variable (never hard-code it)."""
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion

    return TabPFNClassifier.create_default_for_version(ModelVersion.V3_5, random_state=RANDOM_STATE, **TABPFN_SETTINGS)


def make_xgboost():
    from xgboost import XGBClassifier

    base = XGBClassifier(
        eval_metric="logloss", subsample=0.8, colsample_bytree=0.8,
        random_state=RANDOM_STATE, n_jobs=1, tree_method="hist",
    )
    grid = {"max_depth": [2, 3, 4], "n_estimators": [100, 300], "learning_rate": [0.03, 0.1]}
    return GridSearchCV(base, grid, cv=StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE),
                        scoring="roc_auc", n_jobs=1)


def make_logreg():
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("lr", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
    ])
    grid = {"lr__C": [0.01, 0.03, 0.1, 0.3, 1, 3, 10]}
    return GridSearchCV(pipe, grid, cv=StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE),
                        scoring="roc_auc", n_jobs=1)


def default_models(include_tabpfn: bool = True) -> Dict[str, object]:
    models = {}
    if include_tabpfn:
        models["TabPFN-3.5"] = make_tabpfn()
    models["XGBoost"] = make_xgboost()
    models["LogReg"] = make_logreg()
    return models


# ----------------------------------------------------------------------------- metrics
def choose_threshold(y_true, proba, target_recall=TARGET_RECALL) -> float:
    """Highest-precision threshold that still reaches target_recall (ties -> higher threshold)."""
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    precision, recall = precision[:-1], recall[:-1]
    ok = np.where(recall >= target_recall)[0]
    if len(ok) == 0:
        return float(thresholds[0])
    idx = ok[np.lexsort((thresholds[ok], precision[ok]))[-1]]
    return float(thresholds[idx])


def metrics_at(y_true, proba, thr) -> Dict:
    pred = (np.asarray(proba) >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(thr), 4),
        "recall": round(tp / (tp + fn), 3),
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else None,
        "specificity": round(tn / (tn + fp), 3),
        "accuracy": round((tp + tn) / len(pred), 3),
        "tp": int(tp), "fn": int(fn), "fp": int(fp), "tn": int(tn),
    }


def bootstrap_auc_ci(y, p, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        vals.append(roc_auc_score(y[i], p[i]))
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def time_predict(fitted, X: pd.DataFrame, repeats=3) -> Dict[str, float]:
    """Seconds to score 1 row, 625 rows (counterfactual grid) and 5120 rows (one Shapley explanation)."""
    out = {}
    for n in (1, 625, 5120):
        Xn = pd.concat([X] * (n // len(X) + 1), ignore_index=True).iloc[:n]
        ts = []
        for _ in range(repeats):
            t = time.perf_counter(); fitted.predict_proba(Xn); ts.append(time.perf_counter() - t)
        out[f"rows_{n}"] = round(float(np.median(ts)), 3)
    return out


# ----------------------------------------------------------------------------- main
def run_benchmark(data_path: str, out_dir: str, models: Dict[str, object] | None = None,
                  n_boot: int = 2000, log: Callable[[str], None] = print) -> Dict:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    df = load_data(data_path)
    Xtr, Xte, ytr, yte = split(df)
    log(f"train {len(Xtr)} ({int(ytr.sum())} positive) | test {len(Xte)} ({int(yte.sum())} positive)")
    models = models or default_models()
    cv = StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE)

    results, test_proba, fitted_models = {}, {}, {}
    for name, est in models.items():
        log(f"\n=== {name} ===")
        t0 = time.perf_counter()
        # honest CV score of the whole procedure (including any tuning) on TRAIN only
        cv_auc = cross_val_score(clone(est), Xtr, ytr, cv=cv, scoring="roc_auc")
        oof = cross_val_predict(clone(est), Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
        thr = choose_threshold(ytr, oof)
        log(f"CV ROC-AUC {cv_auc.mean():.3f} +/- {cv_auc.std():.3f} | threshold {thr:.3f} | {time.perf_counter()-t0:.0f}s")

        fit_t = time.perf_counter()
        final = clone(est).fit(Xtr, ytr)
        fit_s = time.perf_counter() - fit_t
        p = final.predict_proba(Xte)[:, 1]
        test_proba[name], fitted_models[name] = p, final

        res = {
            "cv_roc_auc_mean": round(float(cv_auc.mean()), 4),
            "cv_roc_auc_std": round(float(cv_auc.std()), 4),
            "test_roc_auc": round(float(roc_auc_score(yte, p)), 4),
            "test_roc_auc_ci95": bootstrap_auc_ci(yte, p, n_boot),
            "test_pr_auc": round(float(average_precision_score(yte, p)), 4),
            "test_brier": round(float(brier_score_loss(yte, p)), 4),
            "at_chosen_threshold": metrics_at(yte, p, thr),
            "at_0.5": metrics_at(yte, p, 0.5),
            "fit_seconds": round(fit_s, 2),
            "predict_seconds": time_predict(final, Xte),
        }
        results[name] = res
        log(json.dumps({k: res[k] for k in ("test_roc_auc", "test_roc_auc_ci95", "test_pr_auc", "test_brier")}))
        log("at threshold: " + json.dumps(res["at_chosen_threshold"]))
        log("predict seconds: " + json.dumps(res["predict_seconds"]))

    majority = round(1 - float(yte.mean()), 3)
    summary = {
        "n_train": int(len(Xtr)), "n_test": int(len(Xte)), "random_state": RANDOM_STATE,
        "target_recall": TARGET_RECALL, "majority_class_accuracy": majority, "models": results,
    }
    (out / "benchmark_results.json").write_text(json.dumps(summary, indent=2))
    _plots(out, yte, test_proba, results)
    _table(out, results)
    # train/test CSVs (the backend needs the 614 training rows; the test rows are for your own checks)
    pd.concat([Xtr, ytr], axis=1).to_csv(out / "train.csv", index=False)
    pd.concat([Xte, yte], axis=1).to_csv(out / "test.csv", index=False)
    return {"summary": summary, "fitted": fitted_models, "test_proba": test_proba, "X_train": Xtr, "y_train": ytr,
            "X_test": Xte, "y_test": yte}


def _table(out: Path, results: Dict):
    rows = []
    for n, r in results.items():
        t = r["at_chosen_threshold"]
        rows.append({"Model": n, "CV AUC": f"{r['cv_roc_auc_mean']:.3f} ± {r['cv_roc_auc_std']:.3f}",
                     "Test AUC": f"{r['test_roc_auc']:.3f}", "95% CI": f"{r['test_roc_auc_ci95'][0]:.2f}-{r['test_roc_auc_ci95'][1]:.2f}",
                     "PR-AUC": f"{r['test_pr_auc']:.3f}", "Brier": f"{r['test_brier']:.3f}",
                     "Recall": f"{t['recall']:.2f}", "Precision": f"{t['precision']:.2f}", "Specificity": f"{t['specificity']:.2f}",
                     "1-row s": r["predict_seconds"]["rows_1"], "5120-row s": r["predict_seconds"]["rows_5120"]})
    pd.DataFrame(rows).to_csv(out / "comparison_table.csv", index=False)


def _plots(out: Path, y, proba: Dict[str, np.ndarray], results: Dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import roc_curve

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    for n, p in proba.items():
        fpr, tpr, _ = roc_curve(y, p)
        ax[0].plot(fpr, tpr, label=f"{n} (AUC {results[n]['test_roc_auc']:.3f})")
        frac, mean = calibration_curve(y, p, n_bins=5, strategy="quantile")
        ax[1].plot(mean, frac, marker="o", label=n)
    ax[0].plot([0, 1], [0, 1], "k--", lw=.8); ax[0].set(title="ROC curve (154 test patients)", xlabel="False positive rate", ylabel="True positive rate")
    ax[1].plot([0, 1], [0, 1], "k--", lw=.8); ax[1].set(title="Calibration (reliability)", xlabel="Predicted probability", ylabel="Observed fraction")
    ax[0].legend(); ax[1].legend(); fig.tight_layout(); fig.savefig(out / "roc_calibration.png", dpi=150); plt.close(fig)


# ----------------------------------------------------------------------------- export for the backend
BACKGROUND_K = 4  # rows used as the SHAP background (256 x 4 = 1,024 model rows per patient); read by the backend from the model card


def global_importance(fitted, X_test: pd.DataFrame, y_test, n_repeats: int = 10) -> Dict[str, Dict[str, float]]:
    """Permutation importance on the test set: how much ROC-AUC drops when one feature is shuffled."""
    from sklearn.inspection import permutation_importance

    r = permutation_importance(fitted, X_test, y_test, scoring="roc_auc", n_repeats=n_repeats, random_state=RANDOM_STATE)
    return {f: {"auc_drop": round(float(m), 4), "std": round(float(s), 4)}
            for f, m, s in sorted(zip(X_test.columns, r.importances_mean, r.importances_std), key=lambda t: -t[1])}


def export_artifacts(res: Dict, primary: str, out_dir: str, package_version: str = "") -> Path:
    """Write artifacts/model_card.json + artifacts/train.csv that the backend loads at start-up."""
    art = Path(out_dir) / "artifacts"; art.mkdir(parents=True, exist_ok=True)
    summ = res["summary"]; m = summ["models"][primary]; t = m["at_chosen_threshold"]
    fa = round((1 - t["precision"]) * 100) if t["precision"] else None
    card = {
        "model": {"name": primary, "tabpfn_package_version": package_version,
                  "settings": TABPFN_SETTINGS if primary.startswith("TabPFN") else {}},
        "features": FEATURES,
        "zero_means_missing": ZERO_MEANS_MISSING,
        "threshold": t["threshold"],
        "target_recall": summ["target_recall"],
        "n_train": summ["n_train"], "n_test": summ["n_test"], "random_state": summ["random_state"],
        "background_k": BACKGROUND_K,
        "cv_roc_auc": {"mean": m["cv_roc_auc_mean"], "std": m["cv_roc_auc_std"]},
        "test": {k: m[k] for k in ("test_roc_auc", "test_roc_auc_ci95", "test_pr_auc", "test_brier")},
        "at_chosen_threshold": t,
        "at_0.5": m["at_0.5"],
        "majority_class_accuracy": summ["majority_class_accuracy"],
        "comparison": {n: {"cv_roc_auc": r["cv_roc_auc_mean"], "test_roc_auc": r["test_roc_auc"]}
                       for n, r in summ["models"].items()},
        "predict_seconds": m["predict_seconds"],
        "global_importance": global_importance(res["fitted"][primary], res["X_test"], res["y_test"]),
        "limitations": [
            "Trained on 768 women (Pima Indian heritage, age 21+) from one study; it may not transfer to other groups.",
            "The test set is small (154 patients), so every metric has wide uncertainty.",
            f"Tuned to catch most higher-risk patients, so about {fa}% of people flagged will not have diabetes." if fa is not None else "",
            "Glucose in this dataset is a 2-hour oral glucose tolerance test value, not a fasting or random reading.",
            "This is a screening aid, not a diagnosis. Talk to a clinician about any result.",
        ],
    }
    card["limitations"] = [x for x in card["limitations"] if x]
    (art / "model_card.json").write_text(json.dumps(card, indent=2))
    pd.concat([res["X_train"], res["y_train"]], axis=1).to_csv(art / "train.csv", index=False)
    return art


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--no-tabpfn", action="store_true")
    a = ap.parse_args()
    run_benchmark(a.data, a.out, default_models(include_tabpfn=not a.no_tabpfn))
