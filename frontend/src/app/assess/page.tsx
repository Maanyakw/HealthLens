"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import AssessmentResult from "@/components/AssessmentResult";
import { Icon } from "@/components/ui";
import { predict, type PatientInput, type PredictResponse } from "@/lib/api";
import { loadHistory, saveAssessment } from "@/lib/history";
import "@/components/assess.css";

type Key = keyof PatientInput;

const FIELDS: {
  key: Key;
  label: string;
  unit: string;
  hint: string;
  min: number;
  max: number;
  step: number;
  optional: boolean;
}[] = [
  { key: "Age", label: "Age", unit: "years", hint: "The model was trained on women aged 21 and over.", min: 18, max: 100, step: 1, optional: false },
  { key: "Pregnancies", label: "Pregnancies", unit: "number", hint: "How many times you have been pregnant (0 if none).", min: 0, max: 20, step: 1, optional: false },
  { key: "Glucose", label: "Glucose", unit: "mg/dL", hint: "Plasma glucose from a blood test. Leave blank if not measured.", min: 1, max: 300, step: 1, optional: true },
  { key: "BMI", label: "BMI", unit: "kg/m²", hint: "Body mass index. Leave blank if not measured.", min: 1, max: 70, step: 0.1, optional: true },
  { key: "BloodPressure", label: "Blood pressure (diastolic)", unit: "mmHg", hint: "Only the lower number, e.g. 76 in 118/76.", min: 1, max: 200, step: 1, optional: true },
  { key: "SkinThickness", label: "Skin-fold thickness", unit: "mm", hint: "Triceps skin-fold. Rarely known, leave blank if so.", min: 1, max: 100, step: 1, optional: true },
  { key: "Insulin", label: "Insulin (2-hour)", unit: "mu U/ml", hint: "2-hour serum insulin. Rarely known, leave blank if so.", min: 1, max: 900, step: 1, optional: true },
  { key: "DiabetesPedigreeFunction", label: "Family-history score", unit: "0 to 2.5", hint: "Pedigree function. If unsure, 0.4 is a typical value.", min: 0, max: 2.5, step: 0.01, optional: false },
];

const EXAMPLES: Record<string, Record<Key, string>> = {
  low: { Age: "24", Pregnancies: "1", Glucose: "105", BMI: "24.8", BloodPressure: "72", SkinThickness: "", Insulin: "", DiabetesPedigreeFunction: "0.3" },
  high: { Age: "50", Pregnancies: "6", Glucose: "170", BMI: "36", BloodPressure: "80", SkinThickness: "35", Insulin: "200", DiabetesPedigreeFunction: "0.9" },
};

const EMPTY = Object.fromEntries(FIELDS.map((f) => [f.key, ""])) as Record<Key, string>;

export default function AssessPage() {
  const [values, setValues] = useState<Record<Key, string>>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<Key, string>>>({});
  const [apiError, setApiError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState<{ input: PatientInput; result: PredictResponse } | null>(null);

  // /assess?view=latest shows the most recent saved result (used by the dashboard link)
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("view") !== "latest") return;
    const last = loadHistory()[0];
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (last) setDone({ input: last.input, result: last.result });
  }, []);

  function validate() {
    const errs: Partial<Record<Key, string>> = {};
    const input: Partial<PatientInput> = {};
    for (const f of FIELDS) {
      const raw = values[f.key].trim();
      if (raw === "") {
        if (f.optional) {
          (input as Record<string, number | null>)[f.key] = null;
        } else errs[f.key] = "Required";
        continue;
      }
      const n = Number(raw);
      if (!Number.isFinite(n)) errs[f.key] = "Enter a number";
      else if (n < f.min || n > f.max) errs[f.key] = `Between ${f.min} and ${f.max}${f.optional ? " (or leave blank)" : ""}`;
      else if ((f.key === "Age" || f.key === "Pregnancies") && !Number.isInteger(n)) errs[f.key] = "Whole number";
      else (input as Record<string, number | null>)[f.key] = n;
    }
    return { errs, input: input as PatientInput };
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApiError("");
    const { errs, input } = validate();
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true);
    try {
      const result = await predict(input);
      saveAssessment(input, result);
      setDone({ input, result });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell active="assess">
      <main className="dash">
        {done ? (
          <>
            <div className="dash-head">
              <div>
                <h1>Assessment result</h1>
                <p>Here is what the model found and why.</p>
              </div>
            </div>
            <AssessmentResult
              input={done.input}
              result={done.result}
              onNew={() => {
                setDone(null);
                window.scrollTo({ top: 0 });
              }}
            />
          </>
        ) : (
          <>
            <div className="dash-head">
              <div>
                <h1>Health assessment</h1>
                <p>Enter what you know. Blank fields are treated as &ldquo;not measured&rdquo;. It takes about a minute.</p>
              </div>
            </div>

            <form className="card as-form" onSubmit={onSubmit} noValidate>
              <div className="as-examples">
                <span className="muted">Just exploring?</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setValues(EXAMPLES.low)}>
                  Fill a lower-risk example
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setValues(EXAMPLES.high)}>
                  Fill a higher-risk example
                </button>
                <button type="button" className="link as-reset" onClick={() => { setValues(EMPTY); setErrors({}); }}>
                  Clear
                </button>
              </div>

              <div className="as-fields">
                {FIELDS.map((f) => (
                  <div key={f.key} className={`as-field${errors[f.key] ? " has-error" : ""}`}>
                    <label htmlFor={f.key}>
                      {f.label}
                      {f.optional && <em>optional</em>}
                    </label>
                    <div className="as-input">
                      <input
                        id={f.key}
                        name={f.key}
                        type="number"
                        inputMode="decimal"
                        min={f.min}
                        max={f.max}
                        step={f.step}
                        value={values[f.key]}
                        onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                        aria-describedby={`${f.key}-hint`}
                        aria-invalid={!!errors[f.key]}
                      />
                      <span>{f.unit}</span>
                    </div>
                    <small id={`${f.key}-hint`}>{errors[f.key] ?? f.hint}</small>
                  </div>
                ))}
              </div>

              {Number(values.Age) > 0 && Number(values.Age) < 21 && (
                <p className="note">
                  <Icon name="info" size={18} />
                  The model was trained on women aged 21 and over, so results for younger ages are less reliable.
                </p>
              )}
              {apiError && (
                <p className="as-error" role="alert">
                  {apiError}
                </p>
              )}

              <div className="as-actions">
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? "Analysing…" : "Get my screening result"}
                  {!loading && <Icon name="arrow" size={18} />}
                </button>
              </div>
              <p className="muted">
                Your answers are sent to the HealthLens model to calculate the score. Results are saved only in this
                browser.
              </p>
            </form>
          </>
        )}
      </main>
    </AppShell>
  );
}
