"""
HealthLens API.

Run locally (from the project root, venv on):
    uvicorn backend.main:app --reload --port 8000
Docs:  http://localhost:8000/docs

The model is loaded once at startup. Every endpoint is a thin layer over
ml/src/explain.py, so the API gives exactly the same numbers as the notebooks.
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "src"))  # the pickled model needs `import features`

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from explain import FEATURE_LABELS, HealthLensExplainer  # noqa: E402

DISCLAIMER = (
    "HealthLens is an academic screening and awareness project. It is not a "
    "medical diagnosis and does not replace advice from a qualified clinician."
)

DEFAULT_ORIGINS = "https://health-lens-theta.vercel.app,http://localhost:3000"
ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["ex"] = HealthLensExplainer()
    yield
    state.clear()


app = FastAPI(
    title="HealthLens API",
    version="1.0.0",
    description="Explainable diabetes-risk screening. " + DISCLAIMER,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    # Vercel preview deployments get their own URLs; allow only this project's.
    allow_origin_regex=r"https://health-lens[a-z0-9-]*\.vercel\.app",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class PatientIn(BaseModel):
    """
    The 8 inputs the model was trained on.
    Leave a field out (or send null / 0) if it was not measured. The model then
    fills it with a typical value and the response marks it as 'not measured'.
    """

    Pregnancies: int = Field(..., ge=0, le=20, description="Number of pregnancies")
    Glucose: Optional[float] = Field(None, ge=0, le=300, description="Plasma glucose, mg/dL (0 or null = not measured)")
    BloodPressure: Optional[float] = Field(None, ge=0, le=200, description="DIASTOLIC blood pressure, mmHg (0 or null = not measured)")
    SkinThickness: Optional[float] = Field(None, ge=0, le=100, description="Triceps skin-fold thickness, mm (0 or null = not measured)")
    Insulin: Optional[float] = Field(None, ge=0, le=900, description="2-hour serum insulin, mu U/ml (0 or null = not measured)")
    BMI: Optional[float] = Field(None, ge=0, le=70, description="Body mass index (0 or null = not measured)")
    DiabetesPedigreeFunction: float = Field(..., ge=0, le=2.5, description="Family-history score")
    Age: int = Field(..., ge=18, le=100, description="Age in years (the model was trained on women aged 21+)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "Pregnancies": 2,
                "Glucose": 130,
                "BloodPressure": 78,
                "SkinThickness": None,
                "Insulin": None,
                "BMI": 31.5,
                "DiabetesPedigreeFunction": 0.5,
                "Age": 41,
            }
        }
    }

    def to_record(self) -> dict:
        rec = self.model_dump()
        for k, v in rec.items():
            if v is None:
                rec[k] = 0  # model code treats 0 as "not measured"
        return rec


class WhatIfIn(BaseModel):
    patient: PatientIn
    changes: dict[str, float] = Field(
        ..., description="Fields to change, e.g. {\"Glucose\": 100, \"BMI\": 27}. Only Glucose and BMI are allowed."
    )


def _ex() -> HealthLensExplainer:
    ex = state.get("ex")
    if ex is None:
        raise HTTPException(503, "Model not loaded yet")
    return ex


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": "ex" in state}


@app.get("/model-info")
def model_info():
    ex = _ex()
    c = ex.card
    t = c["test"]
    return {
        "model": c["model"],
        "feature_set": c["feature_set"],
        "features_used_by_model": c["features_used_by_model"],
        "dataset": c["dataset"],
        "threshold": c["threshold"],
        "target_recall": c["target_recall"],
        "n_train": c["n_train"],
        "n_test": c["n_test"],
        "test_metrics": {
            "roc_auc": t["roc_auc"],
            "roc_auc_95ci": t["roc_auc_95ci"],
            "pr_auc": t["pr_auc"],
            "recall": t["at_chosen_threshold"]["recall"],
            "precision": t["at_chosen_threshold"]["precision"],
            "specificity": t["at_chosen_threshold"]["specificity"],
        },
        "limitations": [
            "Trained on 768 women aged 21+ of Pima Indian heritage; it may not transfer to other groups.",
            "Small test set (154 patients), so the metrics have wide uncertainty.",
            f"Tuned to catch most higher-risk patients, so about {round((1 - t['at_chosen_threshold']['precision']) * 100)}% of people flagged will not have diabetes.",
            "Explanations show what the model uses, not what causes diabetes.",
        ],
        "disclaimer": DISCLAIMER,
    }


@app.post("/predict")
def predict(
    patient: PatientIn,
    top: int = Query(6, ge=1, le=8, description="How many factors to return"),
    counterfactuals: bool = Query(True, description="Include 'what could lower the score' options for flagged patients"),
):
    ex = _ex()
    rec = patient.to_record()
    result = ex.explain_one(rec, top=top)
    out = {
        "probability": result["probability"],
        "threshold": result["threshold"],
        "flagged_higher_risk": result["flagged_higher_risk"],
        "screening_result": (
            "Higher risk: consider a follow-up test with a clinician"
            if result["flagged_higher_risk"]
            else "Lower risk on this screen"
        ),
        "explanation_unit": result["unit"],
        "factors": result["factors"],
        "features_not_used_by_model": result["features_not_used_by_model"],
        "not_measured": [k for k in ("Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI") if not rec[k]],
        "counterfactuals": None,
        "disclaimer": DISCLAIMER,
    }
    if counterfactuals and result["flagged_higher_risk"]:
        try:
            out["counterfactuals"] = ex.counterfactuals(rec, n=3)
        except Exception as e:  # never let the optional part break the main answer
            out["counterfactuals"] = {"options": [], "message": f"Unavailable ({type(e).__name__})"}
    return out


@app.post("/what-if")
def what_if(body: WhatIfIn):
    bad = [k for k in body.changes if k not in ("Glucose", "BMI")]
    if bad:
        raise HTTPException(422, f"Only Glucose and BMI can be changed, got: {bad}")
    return _ex().what_if(body.patient.to_record(), body.changes)


@app.get("/global-importance")
def global_importance():
    imp, _ = _ex().global_importance()
    return {"unit": _ex().unit, "factors": imp.round(4).to_dict(orient="records")}
