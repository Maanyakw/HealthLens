import type { Factor } from "@/lib/api";

const UNITS: Record<string, string> = {
  Glucose: " mg/dL",
  BloodPressure: " mmHg",
  SkinThickness: " mm",
  Insulin: " mu U/ml",
  Age: " yrs",
};

/** Diverging bars: green to the left lowers the score, red to the right raises it. */
export default function FactorBars({ factors }: { factors: Factor[] }) {
  // Blank values are shown as "Not entered" without a direction: the model handles a blank natively and it is
  // not replaced by an average, so a red or green bar for it would suggest something that was never measured.
  const max = Math.max(...factors.filter((f) => !f.was_missing).map((f) => Math.abs(f.impact)), 0.0001);
  return (
    <ul className="fbars" aria-label="Factors behind this score">
      {factors.map((f) => {
        const missing = !!f.was_missing;
        const pct = missing ? 0 : (Math.abs(f.impact) / max) * 100;
        const up = f.impact > 0;
        return (
          <li key={f.feature} className="fbar">
            <div className="fbar-name">
              <strong>{f.label}</strong>
              <small>
                {missing ? "not entered (left blank)" : `${f.value_used}${UNITS[f.feature] ?? ""}`}
              </small>
            </div>
            <div className="fbar-track" role="img" aria-label={missing ? `${f.label} not entered` : `${f.label} ${f.direction}`}>
              <i className="fbar-mid" />
              <i
                className={`fbar-fill ${up ? "up" : "down"}`}
                style={{ width: `${pct / 2}%`, [up ? "left" : "right"]: "50%" }}
              />
            </div>
            {missing ? (
              <span className="fbar-tag" style={{ opacity: 0.7 }}>Not entered</span>
            ) : (
              <span className={`fbar-tag ${up ? "up" : "down"}`}>{up ? "Raises" : "Lowers"}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
