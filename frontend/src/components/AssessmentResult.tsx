"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Gauge, Icon } from "@/components/ui";
import DailyPlan from "@/components/DailyPlan";
import FactorBars from "@/components/FactorBars";
import { getModelInfo, whatIf, type ModelInfo, type PatientInput, type PredictResponse, type WhatIfResponse } from "@/lib/api";
import "./assess.css";

const pct = (p: number) => Math.round(p * 100);

function WhatIf({ input, result }: { input: PatientInput; result: PredictResponse }) {
  const hasGlucose = !!input.Glucose;
  const hasBmi = !!input.BMI;
  const [glucose, setGlucose] = useState(input.Glucose ?? 0);
  const [bmi, setBmi] = useState(input.BMI ?? 0);
  const [out, setOut] = useState<WhatIfResponse | null>(null);
  const [err, setErr] = useState("");
  const seq = useRef(0);

  const changed = (hasGlucose && glucose !== input.Glucose) || (hasBmi && bmi !== input.BMI);

  useEffect(() => {
    if (!changed) return;
    const id = ++seq.current;
    const t = setTimeout(async () => {
      const changes: Record<string, number> = {};
      if (hasGlucose) changes.Glucose = glucose;
      if (hasBmi) changes.BMI = bmi;
      try {
        const r = await whatIf(input, changes);
        if (id === seq.current) {
          setOut(r);
          setErr("");
        }
      } catch (e) {
        if (id === seq.current) setErr(e instanceof Error ? e.message : "Could not update.");
      }
    }, 300);
    return () => clearTimeout(t);
  }, [changed, glucose, bmi, hasGlucose, hasBmi, input]);

  if (!hasGlucose && !hasBmi) return null;

  const shown = changed && out ? out.after : result.probability;
  const flagged = shown >= result.threshold;

  return (
    <section className="card as-card" aria-labelledby="wi-h">
      <h2 id="wi-h">Try a what-if</h2>
      <p className="muted">Move a slider to see how the model&apos;s score would respond. This only shows how the model behaves.</p>
      <div className="wi-grid">
        {hasGlucose && (
          <label className="wi-slider">
            <span>
              Glucose <strong>{glucose} mg/dL</strong>
            </span>
            <input
              type="range"
              min={Math.min(70, input.Glucose ?? 70)}
              max={Math.max(250, input.Glucose ?? 250)}
              step={1}
              value={glucose}
              onChange={(e) => setGlucose(Number(e.target.value))}
            />
          </label>
        )}
        {hasBmi && (
          <label className="wi-slider">
            <span>
              BMI <strong>{bmi.toFixed(1)}</strong>
            </span>
            <input
              type="range"
              min={Math.min(18.5, input.BMI ?? 18.5)}
              max={Math.max(50, input.BMI ?? 50)}
              step={0.1}
              value={bmi}
              onChange={(e) => setBmi(Number(e.target.value))}
            />
          </label>
        )}
      </div>
      <p className={`wi-out ${flagged ? "is-high" : "is-low"}`}>
        Estimated score: <strong>{pct(shown)}%</strong>{" "}
        <span>{flagged ? "(above the screening threshold)" : "(below the screening threshold)"}</span>
        {changed && (
          <button
            type="button"
            className="link as-reset"
            onClick={() => {
              setGlucose(input.Glucose ?? 0);
              setBmi(input.BMI ?? 0);
              setOut(null);
            }}
          >
            Reset
          </button>
        )}
      </p>
      {err && <p className="as-error">{err}</p>}
    </section>
  );
}

export default function AssessmentResult({
  input,
  result,
  onNew,
}: {
  input: PatientInput;
  result: PredictResponse;
  onNew: () => void;
}) {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  useEffect(() => {
    getModelInfo()
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  const flagged = result.flagged_higher_risk;
  const options = result.counterfactuals?.options ?? [];
  const notUsed = result.features_not_used_by_model;

  return (
    <div className="as-result">
      <div className="as-top">
        <section className={`card as-hero ${flagged ? "is-high" : "is-low"}`} aria-labelledby="res-h">
          <h2 id="res-h">Your screening result</h2>
          <Gauge value={pct(result.probability)} caption={flagged ? "Higher-risk screen" : "Lower-risk screen"} size={240} />
          <p className="as-verdict">{result.screening_result}</p>
          <p className="muted">
            The model flags scores of {pct(result.threshold)}% or more. This is a screening estimate, not a diagnosis.
            {flagged && " A clinician can confirm with a blood test."}
          </p>
        </section>

        <section className="card as-card" aria-labelledby="why-h">
          <h2 id="why-h">Why this score?</h2>
          <p className="muted">
            What pushed the score up (red) or down (green) compared with a typical patient. These show what the model
            uses, not what causes diabetes.
          </p>
          <FactorBars factors={result.factors} />
          {notUsed.length > 0 && (
            <p className="muted as-foot">
              Not used by this model: {notUsed.map((f) => (f === "BloodPressure" ? "blood pressure" : f === "SkinThickness" ? "skin thickness" : f)).join(", ")}.
            </p>
          )}
          {result.not_measured.length > 0 && (
            <p className="muted as-foot">
              <Icon name="info" size={16} /> Not measured: {result.not_measured.length} value(s) were filled with typical values,
              so the score is less certain.
            </p>
          )}
        </section>
      </div>

      {flagged && (
        <section className="card as-card" aria-labelledby="cf-h">
          <h2 id="cf-h">What could lower the score</h2>
          {options.length > 0 ? (
            <>
              <p className="muted">
                Smallest changes to glucose and/or BMI that would bring the model&apos;s score under the threshold. They
                show how the model behaves and are not medical advice.
              </p>
              <ul className="cf-list">
                {options.map((o, i) => (
                  <li key={i}>
                    <span className="cf-changes">
                      {o.changes.map((c) => (
                        <span key={c.feature} className="cf-chip">
                          {c.label} {c.from} <Icon name="arrow" size={14} /> {c.to}
                        </span>
                      ))}
                    </span>
                    <span className="cf-new">score would be about {pct(o.new_probability)}%</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">{result.counterfactuals?.message ?? "No simple change was found within plausible limits."}</p>
          )}
        </section>
      )}

      <DailyPlan input={input} result={result} />

      <WhatIf input={input} result={result} />

      <section className="card as-card" aria-labelledby="rel-h">
        <h2 id="rel-h">How reliable is this?</h2>
        {info ? (
          <>
            <ul className="rel-grid">
              <li>
                <strong>{info.test_metrics.roc_auc.toFixed(2)}</strong>
                <span>ROC-AUC on unseen patients (range {info.test_metrics.roc_auc_95ci[0].toFixed(2)} to {info.test_metrics.roc_auc_95ci[1].toFixed(2)})</span>
              </li>
              <li>
                <strong>{pct(info.test_metrics.recall)}%</strong>
                <span>of people with diabetes are caught</span>
              </li>
              <li>
                <strong>{pct(1 - info.test_metrics.precision)}%</strong>
                <span>of people flagged do not have diabetes</span>
              </li>
            </ul>
            <ul className="lim-list">
              {info.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">Model details are not available right now.</p>
        )}
      </section>

      <div className="as-actions">
        <button type="button" className="btn btn-primary" onClick={onNew}>
          New assessment
        </button>
        <Link href="/dashboard" className="btn btn-ghost">
          View dashboard
        </Link>
      </div>

      <p className="note dash-note">
        <Icon name="info" size={18} />
        {result.disclaimer}
      </p>
    </div>
  );
}
