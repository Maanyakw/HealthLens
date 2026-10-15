"""
Train, compare, calibrate and save the HealthLens diabetes-risk model.

Run from the project root:

    python ml/src/train.py

What it does (in order):
  1. Stratified 80/20 train/test split. The test set is not touched until the end.
  2. For each feature set (baseline 8 features vs. 12 engineered features) and each
     model (Logistic Regression, SVM-RBF, MLP, and XGBoost if installed), tune
     hyperparameters with repeated stratified cross-validation on TRAIN only.
     Imputation, scaling and RFE are inside the Pipeline, so they are re-learned
     on every training fold (no leakage).
  3. Pick the winner by cross-validated ROC-AUC, preferring the simpler model
     when scores are within PREFER_SIMPLER_WITHIN of each other.
  4. Calibrate its probabilities (sigmoid) and choose a decision threshold from
     out-of-fold TRAIN predictions so that recall >= TARGET_RECALL.
  5. Evaluate once on the held-out test set and save the model, a model card
     (JSON), a CV results table (CSV) and plots.
"""

import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_selection import RFE
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    make_scorer,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (
    GridSearchCV,
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_val_predict,
    train_test_split,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from features import (
    BASE_FEATURES,
    TARGET,
    FeatureEngineer,
    ZerosToNaN,
)
from load_data import load_dataset

try:
    from xgboost import XGBClassifier

    HAS_XGBOOST = True
except Exception:  # xgboost is optional (missing install or missing libomp on Mac)
    HAS_XGBOOST = False

# --------------------------------------------------------------------------- #
# Settings you may want to change (and justify in your report)
# --------------------------------------------------------------------------- #
RANDOM_STATE = 42
TEST_SIZE = 0.20
CV_SPLITS = 5
CV_REPEATS = 2

# Screening: missing a diabetic patient costs more than a false alarm, so we ask
# the threshold to catch at least this share of true diabetics (on train OOF).
TARGET_RECALL = 0.80

# If a simpler model is within this ROC-AUC of the best, prefer the simpler one.
# Set to 0 to always take the single best score.
PREFER_SIMPLER_WITHIN = 0.005

COMPLEXITY = {"logreg": 0, "svm": 1, "mlp": 2, "xgboost": 3}
FEATURE_SET_ORDER = {"baseline": 0, "engineered": 1}

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "ml" / "models"
REPORTS_DIR = ROOT / "ml" / "reports"


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def get_split():
    """Return X_train, X_test, y_train, y_test (same split every time)."""
    df = load_dataset()
    X = df[BASE_FEATURES]
    y = df[TARGET]
    return train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )


# --------------------------------------------------------------------------- #
# Pipelines
# --------------------------------------------------------------------------- #
def build_pipeline(model, engineered):
    return Pipeline(
        [
            ("zeros", ZerosToNaN()),
            ("impute", SimpleImputer(strategy="median").set_output(transform="pandas")),
            ("engineer", FeatureEngineer(add_features=engineered)),
            ("scale", StandardScaler()),
            ("select", "passthrough"),  # grid decides: passthrough or RFE
            ("model", model),
        ]
    )


def rfe_selector():
    # RFE ranks features with a logistic regression and keeps the top 75%.
    return RFE(
        LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
        n_features_to_select=0.75,
    )


def model_specs(y_train):
    """name -> (estimator, param_grid). Grid keys use Pipeline step names."""
    select = ["passthrough", rfe_selector()]
    specs = {
        "logreg": (
            LogisticRegression(
                max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE
            ),
            {"select": select, "model__C": [0.001, 0.01, 0.1, 1, 10]},
        ),
        "svm": (
            SVC(kernel="rbf", class_weight="balanced", random_state=RANDOM_STATE),
            {
                "select": select,
                "model__C": [0.5, 1, 5],
                "model__gamma": ["scale", 0.01, 0.05],
            },
        ),
        "mlp": (
            MLPClassifier(max_iter=800, random_state=RANDOM_STATE),
            {
                "select": select,
                "model__hidden_layer_sizes": [(8,), (16, 8)],
                "model__alpha": [1e-2, 1e-1],
            },
        ),
    }
    if HAS_XGBOOST:
        pos = int((y_train == 1).sum())
        neg = int((y_train == 0).sum())
        specs["xgboost"] = (
            XGBClassifier(
                eval_metric="logloss",
                scale_pos_weight=neg / pos,
                random_state=RANDOM_STATE,
                n_jobs=1,
            ),
            {
                "select": ["passthrough"],
                "model__n_estimators": [100, 300],
                "model__max_depth": [2, 3],
                "model__learning_rate": [0.03, 0.1],
            },
        )
    return specs


SCORING = {
    "roc_auc": "roc_auc",
    "pr_auc": "average_precision",
    "recall": make_scorer(recall_score, zero_division=0),
    "precision": make_scorer(precision_score, zero_division=0),
    "f1": make_scorer(f1_score, zero_division=0),
    "accuracy": "accuracy",
}


# --------------------------------------------------------------------------- #
# Model comparison (cross-validation on TRAIN only)
# --------------------------------------------------------------------------- #
def compare_models(X_train, y_train):
    cv = RepeatedStratifiedKFold(
        n_splits=CV_SPLITS, n_repeats=CV_REPEATS, random_state=RANDOM_STATE
    )
    rows, searches = [], {}

    for fs_name, engineered in [("baseline", False), ("engineered", True)]:
        for m_name, (estimator, grid) in model_specs(y_train).items():
            t0 = time.time()
            search = GridSearchCV(
                build_pipeline(estimator, engineered),
                grid,
                scoring=SCORING,
                refit="roc_auc",
                cv=cv,
                n_jobs=-1,
            )
            search.fit(X_train, y_train)
            i = search.best_index_
            r = search.cv_results_
            row = {"feature_set": fs_name, "model": m_name}
            for metric in SCORING:
                row[f"cv_{metric}"] = r[f"mean_test_{metric}"][i]
                row[f"cv_{metric}_std"] = r[f"std_test_{metric}"][i]
            row["best_params"] = {
                k: ("RFE(75%)" if isinstance(v, RFE) else v)
                for k, v in search.best_params_.items()
            }
            rows.append(row)
            searches[(fs_name, m_name)] = search
            print(
                f"  {fs_name:<10} {m_name:<8} "
                f"ROC-AUC {row['cv_roc_auc']:.3f} +/- {row['cv_roc_auc_std']:.3f}  "
                f"recall@0.5 {row['cv_recall']:.3f}  ({time.time() - t0:.0f}s)"
            )

    results = pd.DataFrame(rows)
    return results, searches


def pick_winner(results):
    best_auc = results["cv_roc_auc"].max()
    close = results[results["cv_roc_auc"] >= best_auc - PREFER_SIMPLER_WITHIN].copy()
    close["_c"] = close["model"].map(COMPLEXITY)
    close["_f"] = close["feature_set"].map(FEATURE_SET_ORDER)
    close = close.sort_values(["_c", "_f", "cv_roc_auc"], ascending=[True, True, False])
    win = close.iloc[0]
    return win["feature_set"], win["model"]


# --------------------------------------------------------------------------- #
# Threshold, calibration, evaluation
# --------------------------------------------------------------------------- #
def choose_threshold(y_true, proba, target_recall):
    """Highest-precision threshold that still reaches target_recall."""
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    precision, recall = precision[:-1], recall[:-1]
    ok = recall >= target_recall
    if not ok.any():
        return 0.5
    best = np.where(ok)[0]
    # among thresholds meeting the recall target, take max precision (ties -> higher threshold)
    idx = best[np.lexsort((thresholds[best], precision[best]))[-1]]
    return float(thresholds[idx])


def metrics_at(y_true, proba, threshold):
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred).ravel()
    return {
        "threshold": round(float(threshold), 4),
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred),
        "specificity": tn / (tn + fp),
        "f1": f1_score(y_true, pred),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def bootstrap_auc_ci(y_true, proba, n=1000):
    rng = np.random.default_rng(RANDOM_STATE)
    y_true = np.asarray(y_true)
    aucs = []
    for _ in range(n):
        idx = rng.integers(0, len(y_true), len(y_true))
        if len(np.unique(y_true[idx])) < 2:
            continue
        aucs.append(roc_auc_score(y_true[idx], proba[idx]))
    return [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))]


def save_plots(y_test, proba, threshold, test_metrics, results):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    fpr, tpr, _ = roc_curve(y_test, proba)
    plt.figure(figsize=(5, 5))
    plt.plot(fpr, tpr, label=f"AUC = {roc_auc_score(y_test, proba):.3f}")
    plt.plot([0, 1], [0, 1], "--", color="grey")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate (recall)")
    plt.title("ROC curve (test set)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "roc_curve.png", dpi=150)
    plt.close()

    p, r, _ = precision_recall_curve(y_test, proba)
    plt.figure(figsize=(5, 5))
    plt.plot(r, p, label=f"AP = {average_precision_score(y_test, proba):.3f}")
    plt.axhline(float(np.mean(y_test)), ls="--", color="grey", label="prevalence")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-recall curve (test set)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "pr_curve.png", dpi=150)
    plt.close()

    cm = np.array(
        [
            [test_metrics["tn"], test_metrics["fp"]],
            [test_metrics["fn"], test_metrics["tp"]],
        ]
    )
    plt.figure(figsize=(4.5, 4))
    plt.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        plt.text(j, i, v, ha="center", va="center", fontsize=14)
    plt.xticks([0, 1], ["No diabetes", "Diabetes"])
    plt.yticks([0, 1], ["No diabetes", "Diabetes"])
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title(f"Confusion matrix (threshold {threshold:.2f})")
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "confusion_matrix.png", dpi=150)
    plt.close()

    frac_pos, mean_pred = calibration_curve(y_test, proba, n_bins=5, strategy="quantile")
    plt.figure(figsize=(5, 5))
    plt.plot(mean_pred, frac_pos, "o-", label="Model")
    plt.plot([0, 1], [0, 1], "--", color="grey", label="Perfectly calibrated")
    plt.xlabel("Predicted probability")
    plt.ylabel("Observed share with diabetes")
    plt.title("Calibration (test set)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "calibration_curve.png", dpi=150)
    plt.close()

    labels = results["feature_set"] + " / " + results["model"]
    order = results["cv_roc_auc"].argsort()
    plt.figure(figsize=(7, 4.5))
    plt.barh(
        labels.iloc[order],
        results["cv_roc_auc"].iloc[order],
        xerr=results["cv_roc_auc_std"].iloc[order],
        color="#0b7a75",
    )
    plt.xlim(0.6, 0.95)
    plt.xlabel("Cross-validated ROC-AUC (train only)")
    plt.title("Model comparison")
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "model_comparison.png", dpi=150)
    plt.close()


def main():
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test = get_split()
    print(
        f"Train: {len(X_train)} rows ({y_train.mean():.1%} diabetic) | "
        f"Test: {len(X_test)} rows ({y_test.mean():.1%} diabetic)"
    )

    print(f"\n[1/4] Cross-validated comparison ({CV_SPLITS}-fold x {CV_REPEATS}, train only)")
    if not HAS_XGBOOST:
        print("  (xgboost not installed - skipping it)")
    results, searches = compare_models(X_train, y_train)
    results.drop(columns=["best_params"]).assign(
        best_params=results["best_params"].astype(str)
    ).sort_values("cv_roc_auc", ascending=False).to_csv(
        REPORTS_DIR / "cv_results.csv", index=False
    )

    fs_name, m_name = pick_winner(results)
    winner_search = searches[(fs_name, m_name)]
    winner_row = results[
        (results["feature_set"] == fs_name) & (results["model"] == m_name)
    ].iloc[0]
    print(f"\n[2/4] Selected: {m_name} on {fs_name} features")

    print("\n[3/4] Calibrating and choosing the decision threshold (train out-of-fold)")
    base = clone(winner_search.best_estimator_)
    calibrated = CalibratedClassifierCV(base, method="sigmoid", cv=5, ensemble=False)
    oof = cross_val_predict(
        clone(calibrated),
        X_train,
        y_train,
        cv=StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE),
        method="predict_proba",
    )[:, 1]
    threshold = choose_threshold(y_train, oof, TARGET_RECALL)
    print(f"  Threshold {threshold:.3f} (recall >= {TARGET_RECALL:.0%} on train out-of-fold)")

    calibrated.fit(X_train, y_train)
    raw_pipeline = clone(winner_search.best_estimator_).fit(X_train, y_train)

    print("\n[4/4] One-time evaluation on the held-out test set")
    proba = calibrated.predict_proba(X_test)[:, 1]
    test = {
        "roc_auc": roc_auc_score(y_test, proba),
        "roc_auc_95ci": bootstrap_auc_ci(y_test, proba),
        "pr_auc": average_precision_score(y_test, proba),
        "brier": brier_score_loss(y_test, proba),
        "at_chosen_threshold": metrics_at(y_test, proba, threshold),
        "at_0.5": metrics_at(y_test, proba, 0.5),
        "majority_class_accuracy": float(1 - y_test.mean()),
    }
    save_plots(y_test, proba, threshold, test["at_chosen_threshold"], results)

    t = test["at_chosen_threshold"]
    print(f"  ROC-AUC {test['roc_auc']:.3f}  (95% CI {test['roc_auc_95ci'][0]:.3f}-{test['roc_auc_95ci'][1]:.3f})")
    print(f"  PR-AUC  {test['pr_auc']:.3f}   Brier {test['brier']:.3f}")
    print(
        f"  @threshold {threshold:.2f}: recall {t['recall']:.3f}  precision {t['precision']:.3f}  "
        f"specificity {t['specificity']:.3f}  accuracy {t['accuracy']:.3f}  "
        f"(TP {t['tp']} FN {t['fn']} FP {t['fp']} TN {t['tn']})"
    )
    print(f"  Majority-class baseline accuracy: {test['majority_class_accuracy']:.3f}")

    kept = raw_pipeline[:-1].get_feature_names_out(BASE_FEATURES)
    card = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "random_state": RANDOM_STATE,
        "dataset": "Pima Indians Diabetes (768 rows, women 21+, Pima Indian heritage)",
        "input_features": BASE_FEATURES,
        "model": m_name,
        "feature_set": fs_name,
        "best_params": winner_row["best_params"],
        "features_used_by_model": [str(f) for f in kept],
        "threshold": threshold,
        "target_recall": TARGET_RECALL,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "cv": {
            k: float(winner_row[k])
            for k in winner_row.index
            if k.startswith("cv_")
        },
        "test": test,
        "files": {
            "calibrated_model": "model.joblib",
            "uncalibrated_pipeline": "pipeline_uncalibrated.joblib",
        },
    }
    joblib.dump(calibrated, MODELS_DIR / "model.joblib")
    joblib.dump(raw_pipeline, MODELS_DIR / "pipeline_uncalibrated.joblib")
    with open(MODELS_DIR / "model_card.json", "w") as f:
        json.dump(card, f, indent=2, default=float)

    print(f"\nSaved model + card to {MODELS_DIR}")
    print(f"Saved CV table + plots to {REPORTS_DIR}")


if __name__ == "__main__":
    sys.exit(main())
