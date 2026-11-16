"use client";
import { useEffect, useState } from "react";
import "./hl2.css";
import { narrate, type Narration, type PatientInput, type PredictResponse } from "@/lib/api";

/** Plain-language explanation of a result. Written by the AI service when possible, otherwise from fixed wording. */
export default function Narrative({
  input,
  result,
  glucoseComparable = null,
}: {
  input: PatientInput;
  result: PredictResponse;
  glucoseComparable?: boolean | null;
}) {
  const [data, setData] = useState<Narration | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"patient" | "clinician">("patient");
  const payload = result.ai_payload;

  // Re-run only when the actual content changes (not on every re-render), to avoid wasting free-tier AI calls.
  const key = JSON.stringify([input, payload?.score, payload?.factors, glucoseComparable]);
  useEffect(() => {
    if (!payload) return;
    let alive = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData(null);
    setError(null);
    narrate(input, result, glucoseComparable)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e instanceof Error ? e.message : "The explanation could not be loaded."));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!payload) return null; // results saved by an older version have nothing to explain from

  return (
    <section className="hl2-card" aria-labelledby="hl2-narr-h">
      <div className="hl2-row" style={{ justifyContent: "space-between" }}>
        <h2 id="hl2-narr-h" style={{ fontSize: "1.05rem", margin: 0 }}>In plain words</h2>
        {data && <span className="hl2-badge">{data.source === "llm" ? "Written by AI, numbers checked" : "Standard wording"}</span>}
      </div>
      {!data && !error && (
        <div role="status" aria-label="Loading explanation">
          <div className="hl2-skel" />
          <div className="hl2-skel" style={{ width: "80%" }} />
        </div>
      )}
      {error && <div className="hl2-error" role="alert">{error}</div>}
      {data && (
        <>
          <div className="hl2-tabs" role="group" aria-label="Audience">
            <button type="button" className="hl2-btn" aria-pressed={tab === "patient"} onClick={() => setTab("patient")}>For you</button>
            <button type="button" className="hl2-btn" aria-pressed={tab === "clinician"} onClick={() => setTab("clinician")}>For a clinician</button>
          </div>
          <p style={{ lineHeight: 1.55 }}>{tab === "patient" ? data.patient_summary : data.clinician_summary}</p>
          <p className="hl2-muted">{data.disclaimer}</p>
        </>
      )}
    </section>
  );
}
