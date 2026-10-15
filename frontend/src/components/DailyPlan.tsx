"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/ui";
import type { PatientInput, PredictResponse } from "@/lib/api";
import { buildPlan } from "@/lib/plan";
import "./assess.css";

const todayKey = () => `healthlens-plan-${new Date().toISOString().slice(0, 10)}`;

export default function DailyPlan({ input, result }: { input: PatientInput; result: PredictResponse }) {
  const plan = useMemo(() => buildPlan(input, result), [input, result]);
  const [done, setDone] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(todayKey());
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDone(raw ? JSON.parse(raw) : []);
    } catch {
      setDone([]);
    }
  }, []);

  function toggle(id: string) {
    const next = done.includes(id) ? done.filter((d) => d !== id) : [...done, id];
    setDone(next);
    try {
      localStorage.setItem(todayKey(), JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }

  const count = plan.daily.filter((d) => done.includes(d.id)).length;
  const pct = Math.round((count / plan.daily.length) * 100);

  return (
    <section className="card as-card" aria-labelledby="plan-h">
      <div className="plan-head">
        <div>
          <h2 id="plan-h">Your daily plan</h2>
          <p className="muted">
            General healthy-habit guidance chosen from your result. It is not medical advice and it does not come from
            the AI model.
          </p>
        </div>
        <div className="plan-prog" role="img" aria-label={`${count} of ${plan.daily.length} done today`}>
          <strong>
            {count}/{plan.daily.length}
          </strong>
          <span>done today</span>
        </div>
      </div>
      <div className="meter" aria-hidden="true">
        <i style={{ width: `${pct}%` }} />
      </div>

      <ul className="plan-list">
        {plan.daily.map((d) => (
          <li key={d.id} className={done.includes(d.id) ? "is-done" : ""}>
            <label>
              <input type="checkbox" checked={done.includes(d.id)} onChange={() => toggle(d.id)} />
              <span className="plan-box" aria-hidden="true">
                <Icon name="check" size={16} />
              </span>
              <span className="plan-text">
                <strong>{d.title}</strong>
                <small>{d.why}</small>
              </span>
            </label>
          </li>
        ))}
      </ul>

      <div className="plan-cols">
        <div>
          <h3>Next steps</h3>
          <ul className="plan-bullets">
            {plan.soon.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3>See a doctor if you notice</h3>
          <ul className="plan-bullets">
            {plan.precautions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="as-error plan-urgent" role="note">
        {plan.urgent}
      </p>
    </section>
  );
}
