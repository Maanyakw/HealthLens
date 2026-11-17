"use client";
import { useState } from "react";
import "./hl2.css";
import { FIELD_NAMES, type FieldName, type ReportResult, readReport } from "@/lib/api";

const LABEL: Record<FieldName, string> = {
  Pregnancies: "Pregnancies", Glucose: "Glucose (mg/dL)", BloodPressure: "Blood pressure, diastolic (mmHg)", SkinThickness: "Skin thickness (mm)",
  Insulin: "Insulin (µIU/mL)", BMI: "BMI", DiabetesPedigreeFunction: "Family-history score", Age: "Age (years)",
};
const MAX_BYTES = 5 * 1024 * 1024;
const OK_TYPES = ["application/pdf", "image/png", "image/jpeg"];

export type ConfirmedValues = Partial<Record<FieldName, number>>;

/** Upload a SYNTHETIC lab report, review what was read, fix anything, confirm, and pre-fill the form. */
export default function ReportUpload({ onConfirm }: { onConfirm: (values: ConfirmedValues, meta: { glucoseComparable: boolean }) => void }) {
  const [synthetic, setSynthetic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);
  const [glucoseAck, setGlucoseAck] = useState(false);
  const [fileName, setFileName] = useState("");

  async function onFile(file: File | undefined) {
    setError(null); setResult(null); setChecked(false); setGlucoseAck(false);
    if (!file) return;
    if (!OK_TYPES.includes(file.type)) return setError("Please choose a PDF, PNG or JPEG file.");
    if (file.size > MAX_BYTES) return setError("That file is larger than 5 MB.");
    setBusy(true);
    try {
      const r = await readReport(file);
      setResult(r);
      setValues(Object.fromEntries(Object.entries(r.fields).map(([k, v]) => [k, String(v!.value)])));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The report could not be read. Please enter the values by hand.");
    } finally { setBusy(false); }
  }

  const glucoseShown = result && "Glucose" in result.fields;
  const needsGlucoseAck = !!glucoseShown && !result!.glucose_comparable;
  const parsed: ConfirmedValues = {};
  let invalid = false;
  for (const k of FIELD_NAMES) {
    if (values[k] === undefined || values[k] === "") continue;
    const n = Number(values[k]);
    if (!Number.isFinite(n)) invalid = true; else parsed[k] = n;
  }
  const canUse = !!result && checked && !invalid && Object.keys(parsed).length > 0 && (!needsGlucoseAck || glucoseAck);

  return (
    <section className="hl2-card" aria-labelledby="hl2-report-h">
      <h3 id="hl2-report-h">Read values from a lab report</h3>
      <label className="hl2-row">
        <input type="checkbox" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} />
        <span>This is a synthetic sample report.&apos;</span>
      </label>
      {/* <p className="hl2-muted hl2-note">
        Use sample reports only. The file is sent to Google Gemini (free tier), which may keep it. 
      </p> */}
      <div className="hl2-pickrow">
        <input id="hl2-file" className="hl2-sr" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
               disabled={!synthetic || busy} onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; setFileName(f ? f.name : ""); onFile(f); }} />
        <label htmlFor="hl2-file" className="hl2-btn primary hl2-pick" aria-disabled={!synthetic || busy}>
          <span aria-hidden="true">⬆</span> {fileName ? "Choose a different file" : "Choose report file"}
        </label>
        <span className="hl2-muted">{fileName ? fileName : synthetic ? "PDF, PNG or JPEG, up to 5 MB" : "Tick the box above first"}</span>
      </div>
      {busy && <p role="status">Reading the report… this can take up to a minute.</p>}
      {error && <div className="hl2-error" role="alert">{error}</div>}

      {result && (
        <>
          {result.warnings.map((w) => <div key={w} className="hl2-warn" role="alert">{w}</div>)}
          <table className="hl2-table">
            <thead><tr><th>Field</th><th>Value read</th><th>Note</th></tr></thead>
            <tbody>
              {FIELD_NAMES.filter((k) => k in result.fields).map((k) => (
                <tr key={k}>
                  <td><label htmlFor={`hl2-f-${k}`}>{LABEL[k]}</label></td>
                  <td><input id={`hl2-f-${k}`} type="number" step="any" value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })} /></td>
                  <td className="hl2-muted">{result.fields[k]!.note}{k === "Glucose" && result.glucose_evidence ? ` Printed as: “${result.glucose_evidence}”` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {Object.keys(result.fields).length === 0 && <p>No usable values were found. Please enter them by hand.</p>}
          <p className="hl2-muted">
            Not on the report, enter by hand: {result.needs_manual.join(", ")}.
            {result.not_found.filter((k) => !result.needs_manual.includes(k)).length > 0 && <> Also not found: {result.not_found.filter((k) => !result.needs_manual.includes(k)).join(", ")}.</>}
          </p>
          <label className="hl2-row"><input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            <span>I checked these values against the report.</span></label>
          {needsGlucoseAck && (
            <label className="hl2-row"><input type="checkbox" checked={glucoseAck} onChange={(e) => setGlucoseAck(e.target.checked)} />
              <span>I understand this glucose is not a 2-hour tolerance-test value, so the score may be too low.</span></label>
          )}
          {invalid && <div className="hl2-error" role="alert">One of the values is not a number.</div>}
          <p><button type="button" className="hl2-btn primary" disabled={!canUse} onClick={() => onConfirm(parsed, { glucoseComparable: result.glucose_comparable })}>
            Use these values
          </button></p>
        </>
      )}
    </section>
  );
}
