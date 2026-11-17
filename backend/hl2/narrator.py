"""
Explanation narrator: turns the model's numbers into two short written summaries
(one for the patient, one for a clinician).

The LLM is optional. A deterministic template always produces a correct text from the same facts;
the LLM version is only used if it passes the guardrails in guard.py.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import guard
from .llm import LLMError

NICE = {"Pregnancies": "Pregnancies", "Glucose": "Glucose", "BloodPressure": "Blood pressure",
        "SkinThickness": "Skin thickness", "Insulin": "Insulin", "BMI": "BMI",
        "DiabetesPedigreeFunction": "Family-history score", "Age": "Age"}

PATIENT_MAX_WORDS, CLINICIAN_MAX_WORDS = 170, 140


def pct(x: float) -> int:
    return int(round(x * 100))


# ----------------------------------------------------------------------------- facts
def build_facts(result: Dict[str, Any], card: Dict[str, Any]) -> Dict[str, Any]:
    """
    result = {"inputs": {feature: value or None}, "score": 0-1, "threshold": 0-1, "factors": [{"feature","effect"}...],
              "counterfactuals": {...} (from explain_agnostic), "glucose_comparable": True/False/None}
    """
    factors = [{"feature": f["feature"], "label": NICE.get(f["feature"], f["feature"]),
                "entered": result["inputs"].get(f["feature"]), "effect_points": pct(f["effect"])}
               for f in result["factors"]
               if abs(f["effect"]) >= 0.01 and result["inputs"].get(f["feature"]) is not None][:5]
    cf = result.get("counterfactuals") or {}
    options = [o for o in cf.get("options", []) if o.get("realistic")]
    t = card.get("at_chosen_threshold", {})
    prec = t.get("precision")
    return {
        "score_percent": pct(result["score"]),
        "threshold_percent": pct(result["threshold"]),
        "flagged": result["score"] >= result["threshold"],
        "raising": [f for f in factors if f["effect_points"] > 0],
        "lowering": [f for f in factors if f["effect_points"] < 0],
        "not_entered": [NICE[k] for k, v in result["inputs"].items() if v is None],
        "options": [{"kind": o.get("kind"), "glucose": o.get("Glucose"), "bmi": o.get("BMI"),
                     "glucose_change": o.get("glucose_change"), "bmi_change": o.get("bmi_change"),
                     "new_score_percent": pct(o["new_score"])} for o in options],
        "no_realistic_option": bool(cf) and not cf.get("already_below_threshold") and not options,
        "glucose_comparable": result.get("glucose_comparable"),
        "false_alarm_percent": round((1 - prec) * 100) if prec else None,
        "recall_percent": pct(t["recall"]) if t.get("recall") is not None else None,
        "inputs": {k: v for k, v in result["inputs"].items() if v is not None},
    }


def allowed_numbers(facts: Dict[str, Any]) -> set:
    vals = [facts["score_percent"], facts["threshold_percent"], facts["false_alarm_percent"], facts["recall_percent"]]
    for f in facts["raising"] + facts["lowering"]:
        vals += [f["effect_points"], f["entered"]]
    for o in facts["options"]:
        vals += [o["glucose"], o["bmi"], o["glucose_change"], o["bmi_change"], o["new_score_percent"]]
    vals += list(facts["inputs"].values())
    return guard.allowed_set(vals)


# ----------------------------------------------------------------------------- template (always available)
def _num(x) -> str:
    return f"{x:g}" if x is not None else "?"


def template_texts(facts: Dict[str, Any]) -> Dict[str, str]:
    s, t = facts["score_percent"], facts["threshold_percent"]
    verdict = (f"above the {t}% line, so HealthLens marks this as higher risk" if facts["flagged"]
               else f"below the {t}% line, so HealthLens does not mark this as higher risk")
    up = ", ".join(f"{f['label']} ({_num(f['entered'])}) adds about {f['effect_points']} points" for f in facts["raising"]) or "no single factor stood out upward"
    down = ", ".join(f"{f['label']} ({_num(f['entered'])}) lowers it by about {abs(f['effect_points'])} points" for f in facts["lowering"])
    p = [f"Your screening score is {s}%, which is {verdict}."]
    p.append(f"What pushed the score up: {up}." + (f" What pulled it down: {down}." if down else ""))
    if facts["flagged"] and facts["options"]:
        o = facts["options"][0]
        bits = []
        if o["glucose_change"]:
            bits.append(f"glucose around {_num(o['glucose'])} instead of {_num(facts['inputs'].get('Glucose'))}")
        if o["bmi_change"]:
            bits.append(f"BMI around {_num(o['bmi'])} instead of {_num(facts['inputs'].get('BMI'))}")
        p.append(f"For example, with {' and '.join(bits)}, the model's score would be about {o['new_score_percent']}%. "
                 "This shows how the model behaves; it is not a treatment plan.")
    elif facts["flagged"] and facts["no_realistic_option"]:
        p.append("No small change in glucose or BMI would be enough on its own to bring the score under the line, so it is worth discussing with a clinician.")
    if facts["not_entered"]:
        p.append(f"Not entered: {', '.join(facts['not_entered'])}. The model can still score without them, but the result is less certain.")
    if facts["glucose_comparable"] is False:
        p.append("The glucose value is not a 2-hour glucose tolerance test result, which is what the model learned from, so the score may be too low.")
    if facts["false_alarm_percent"] is not None:
        p.append(f"In testing, about {facts['false_alarm_percent']}% of people flagged did not have diabetes.")
    patient = " ".join(p)

    c = [f"Score {s}% against a screening threshold of {t}% ({'flagged' if facts['flagged'] else 'not flagged'}). Drivers (probability points): "
         + ("; ".join(f"{f['label']} {_num(f['entered'])}: {f['effect_points']:+d}" for f in facts["raising"] + facts["lowering"]) or "none above 1 point") + "."]
    if facts["not_entered"]:
        c.append(f"Inputs not provided (the model handles missing values natively): {', '.join(facts['not_entered'])}.")
    if facts["glucose_comparable"] is False:
        c.append("Glucose is not a 2-hour OGTT value; the model was trained on OGTT values, so risk may be underestimated.")
    if facts["recall_percent"] is not None and facts["false_alarm_percent"] is not None:
        c.append(f"Test performance at this threshold: recall {facts['recall_percent']}%, about {facts['false_alarm_percent']}% of flags are false alarms.")
    return {"patient_summary": patient, "clinician_summary": " ".join(c)}


# ----------------------------------------------------------------------------- LLM version
SYSTEM = (
    "You write short explanations of a diabetes-risk screening result. Use ONLY the facts in the JSON the user sends. "
    "Do not add any number that is not in the facts. Do not diagnose, do not tell anyone they have or do not have diabetes, "
    "and do not mention medicines, doses or treatments. Do not use markdown, lists or links. "
    "patient_summary: plain English for a non-expert, second person, at most 120 words. "
    "clinician_summary: neutral and concise, at most 90 words, include the score, the threshold and the main drivers."
)
SCHEMA = {"type": "object", "properties": {"patient_summary": {"type": "string"}, "clinician_summary": {"type": "string"}},
          "required": ["patient_summary", "clinician_summary"]}


def narrate(facts: Dict[str, Any], client=None) -> Dict[str, Any]:
    base = template_texts(facts)
    out = {**base, "source": "template", "llm_rejected_reason": None, "disclaimer": guard.DISCLAIMER}
    if client is None or not getattr(client, "available", False):
        return out
    try:
        raw = client.generate_json(SYSTEM, "Facts:\n" + json.dumps(facts, default=str), SCHEMA)
    except LLMError as e:
        out["llm_rejected_reason"] = f"llm unavailable: {e}"
        return out
    allowed = allowed_numbers(facts)
    p, c = str(raw.get("patient_summary", "")), str(raw.get("clinician_summary", ""))
    reason = guard.validate(p, allowed, PATIENT_MAX_WORDS) or guard.validate(c, allowed, CLINICIAN_MAX_WORDS)
    if reason:
        out["llm_rejected_reason"] = reason
        return out
    # The caution lines are added by code, never left to the LLM.
    extra = []
    if facts["glucose_comparable"] is False:
        extra.append("Note: the glucose value is not a 2-hour glucose tolerance test result, so this score may be too low.")
    if facts["not_entered"]:
        extra.append(f"Not entered: {', '.join(facts['not_entered'])} (the model can score without them, but the result is less certain).")
    out.update(patient_summary=" ".join([p] + extra), clinician_summary=c, source="llm")
    return out
