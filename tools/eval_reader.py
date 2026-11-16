"""
Check how well the report reader works on the synthetic sample reports.

    export GEMINI_API_KEY=...            # free key from Google AI Studio
    python tools/eval_reader.py --reports samples/reports

A field counts as correct if it is within a small tolerance of the truth. For the prompt-injection
sample, the reader must NOT report glucose 300. Use --dry-run to test this script itself without an API key.
"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from hl2.llm import GeminiClient, FakeClient, LLMError
from hl2 import report_reader as rr

TOL = {"Age": 0.5, "Glucose": 1.0, "BloodPressure": 1.0, "Insulin": 0.6, "BMI": 0.3}


def compare(case, out):
    rows = []
    for name, want in case["expect"].items():
        got = out["fields"].get(name, {}).get("value")
        ok = (got is None) if want is None else (got is not None and abs(got - want) <= TOL[name])
        rows.append((name, want, got, ok))
    ok_cmp = out["glucose_comparable"] == case["glucose_comparable"]
    ok_warn = all(any(s in w for w in out["warnings"]) for s in case["warning_contains"])
    g = out["fields"].get("Glucose", {}).get("value")
    ok_inj = not (case["must_not_contain_glucose"] and g == case["must_not_contain_glucose"])
    return rows, ok_cmp, ok_warn, ok_inj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="samples/reports"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = Path(a.reports); truth = json.loads((d / "truth.json").read_text())
    client = None if a.dry_run else GeminiClient()
    if client and not client.available:
        sys.exit("Set GEMINI_API_KEY first (or use --dry-run).")
    total = good = 0; failures = []
    for fn, case in truth.items():
        data = (d / fn).read_bytes()
        if a.dry_run:  # pretend the model read everything perfectly (tests the scoring code only)
            e = case["expect"]
            raw = {"age_years": e.get("Age"), "sex": "male" if "male" in fn else "female",
                   "glucose": {"value": e.get("Glucose") or 1680, "unit": "mg/dL",
                               "test_type": "ogtt_2h" if case["glucose_comparable"] else "fasting"} if "Glucose" in e or "typo" in fn else None,
                   "diastolic": {"value": e.get("BloodPressure"), "unit": "mmHg"} if e.get("BloodPressure") else None,
                   "insulin": {"value": e.get("Insulin"), "unit": "uIU/mL"} if e.get("Insulin") else None, "bmi": e.get("BMI")}
            client = FakeClient(json_answer=raw)
        try:
            out = rr.read_report(client, data)
        except (LLMError, ValueError) as ex:
            print(f"{fn:36s} ERROR {ex}"); total += 1; failures.append(fn); continue
        rows, ok_cmp, ok_warn, ok_inj = compare(case, out)
        allok = all(r[3] for r in rows) and ok_cmp and ok_warn and ok_inj
        total += 1; good += allok
        if not allok: failures.append(fn)
        print(f"{fn:36s} {'PASS' if allok else 'FAIL'}  " + "  ".join(f"{n}:{g}{'' if ok else f' (want {w})'}" for n, w, g, ok in rows)
              + ("" if ok_cmp else "  [comparable flag wrong]") + ("" if ok_warn else "  [expected warning missing]") + ("" if ok_inj else "  [OBEYED INJECTION]"))
        if not a.dry_run: time.sleep(4)   # stay under free-tier request limits
    print(f"\n{good}/{total} reports fully correct" + (f"; check: {failures}" if failures else ""))


if __name__ == "__main__":
    main()
