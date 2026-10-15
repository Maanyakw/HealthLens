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
  const max = Math.max(...factors.map((f) => Math.abs(f.impact)), 0.0001);
  return (
    <ul className="fbars" aria-label="Factors behind this score">
      {factors.map((f) => {
        const pct = (Math.abs(f.impact) / max) * 100;
        const up = f.impact > 0;
        return (
          <li key={f.feature} className="fbar">
            <div className="fbar-name">
              <strong>{f.label}</strong>
              <small>
                {f.was_missing
                  ? `not measured, typical value (${f.value_used}) used`
                  : `${f.value_used}${UNITS[f.feature] ?? ""}`}
              </small>
            </div>
            <div className="fbar-track" role="img" aria-label={`${f.label} ${f.direction}`}>
              <i className="fbar-mid" />
              <i
                className={`fbar-fill ${up ? "up" : "down"}`}
                style={{ width: `${pct / 2}%`, [up ? "left" : "right"]: "50%" }}
              />
            </div>
            <span className={`fbar-tag ${up ? "up" : "down"}`}>{up ? "Raises" : "Lowers"}</span>
          </li>
        );
      })}
    </ul>
  );
}
