"""
Compatibility layer: the v2 model, but the response shapes your existing frontend (api.ts) already understands.

`/predict`, `/what-if`, `/model-info` and `/global-importance` therefore keep their old field names.
`/predict` also returns `ai_payload`, which the frontend echoes back to `/narrate` and `/chat`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DISCLAIMER = (
    "HealthLens is an academic screening and awareness project. It is not a "
    "medical diagnosis and does not replace advice from a qualified clinician."
)
LABELS = {
    "Pregnancies": "Number of pregnancies", "Glucose": "Glucose", "BloodPressure": "Blood pressure (diastolic)",
    "SkinThickness": "Skin fold thickness", "Insulin": "Insulin", "BMI": "BMI",
    "DiabetesPedigreeFunction": "Family history score", "Age": "Age",
}
MODEL_NAMES = {"TabPFN-3.5": "TabPFN-3.5 (pretrained transformer for tabular data)"}
OPTIONAL = ("Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI")


def predict_response(a: Dict[str, Any], inputs: Dict[str, Optional[float]], medians: Dict[str, float], top: int,
                     include_counterfactuals: bool) -> Dict[str, Any]:
    total = sum(abs(f["effect"]) for f in a["factors"]) or 1.0
    factors = []
    for f in a["factors"]:  # already sorted by size
        name = f["feature"]
        missing = inputs.get(name) is None
        factors.append({
            "feature": name, "label": LABELS.get(name, name),
            "value_used": round(float(medians[name] if missing else inputs[name]), 2),
            "was_missing": missing,
            "impact": round(f["effect"], 4),                       # probability points (0.27 = 27 points)
            "direction": "raises risk" if f["effect"] > 0 else "lowers risk",
            "share": round(abs(f["effect"]) / total, 4),
        })
    flagged = a["flagged"]
    cf_raw = a["counterfactuals"]
    return {
        "probability": a["score"], "threshold": a["threshold"], "flagged_higher_risk": flagged,
        "screening_result": ("Higher risk: consider a follow-up test with a clinician" if flagged else "Lower risk on this screen"),
        "explanation_unit": "probability",
        "base_probability": a["base_score"],                        # average score; base + sum(impact) = probability
        "factors": factors[:top],
        "features_not_used_by_model": [],
        "not_measured": [k for k in OPTIONAL if inputs.get(k) is None],
        "counterfactuals": counterfactuals(cf_raw) if (include_counterfactuals and flagged) else None,
        "disclaimer": DISCLAIMER,
        # echoed back by the frontend to /narrate and /chat so the model is not run twice
        "ai_payload": {
            "score": a["score"],
            "factors": [{"feature": f["feature"], "effect": f["effect"]} for f in a["factors"]],
            "counterfactuals": cf_raw,
        },
    }


def counterfactuals(cf: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if cf is None:
        return None
    if cf.get("already_below_threshold"):
        return {"options": [], "message": "Already below the screening threshold; no change needed."}
    options: List[Dict[str, Any]] = []
    for o in cf.get("options", []):
        if not o.get("realistic"):
            continue
        changes = []
        if o.get("glucose_change"):
            changes.append({"feature": "Glucose", "label": "Glucose", "from": round(o["Glucose"] - o["glucose_change"], 1), "to": o["Glucose"]})
        if o.get("bmi_change"):
            changes.append({"feature": "BMI", "label": "BMI", "from": round(o["BMI"] - o["bmi_change"], 1), "to": o["BMI"]})
        if changes:
            options.append({"changes": changes, "new_probability": o["new_score"]})
    if not options:
        return {"options": [], "message": "No small change in glucose or BMI would be enough on its own to bring the score under the line. Please discuss this with a clinician."}
    return {"options": options[:3]}


def model_info(card: Dict[str, Any]) -> Dict[str, Any]:
    t, at = card["test"], card["at_chosen_threshold"]
    name = card["model"]["name"]
    return {
        "model": MODEL_NAMES.get(name, name),
        "feature_set": "all 8 raw features",
        "features_used_by_model": list(card["features"]),
        "dataset": "Pima Indians Diabetes (768 women, 21+)",
        "threshold": card["threshold"], "target_recall": card["target_recall"],
        "n_train": card["n_train"], "n_test": card["n_test"],
        "test_metrics": {"roc_auc": t["test_roc_auc"], "roc_auc_95ci": t["test_roc_auc_ci95"], "pr_auc": t["test_pr_auc"],
                         "recall": at["recall"], "precision": at["precision"], "specificity": at["specificity"]},
        "limitations": list(card["limitations"]) + ["Explanations show what the model uses, not what causes diabetes."],
        "disclaimer": DISCLAIMER,
        # extra (new): model comparison and timings, for the report and dashboard
        "comparison": card.get("comparison", {}), "cv_roc_auc": card.get("cv_roc_auc"), "predict_seconds": card.get("predict_seconds"),
    }


def global_importance(card: Dict[str, Any]) -> Dict[str, Any]:
    imp = card.get("global_importance", {})
    vals = {k: max(float(v["auc_drop"]), 0.0) for k, v in imp.items()}
    total = sum(vals.values()) or 1.0
    rows = [{"feature": k, "label": LABELS.get(k, k), "mean_abs_impact": round(v, 4), "share": round(v / total, 4)}
            for k, v in sorted(vals.items(), key=lambda kv: -kv[1])]
    return {"unit": "drop in ROC-AUC when the feature is shuffled", "factors": rows}
