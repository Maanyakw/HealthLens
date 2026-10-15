"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import DailyPlan from "@/components/DailyPlan";
import TrendChart from "@/components/TrendChart";
import { Gauge, Icon } from "@/components/ui";
import { getModelInfo, type ModelInfo } from "@/lib/api";
import { clearHistory, loadHistory, type SavedAssessment } from "@/lib/history";
import "./assess.css";

const pct = (p: number) => Math.round(p * 100);
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const when = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function bmiNote(bmi: number) {
  if (bmi < 18.5) return "Underweight range";
  if (bmi < 25) return "Normal range";
  if (bmi < 30) return "Overweight range";
  return "Obese range";
}

export default function DashboardView() {
  const [history, setHistory] = useState<SavedAssessment[] | null>(null);
  const [info, setInfo] = useState<ModelInfo | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory(loadHistory());
    getModelInfo()
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  const latest = history?.[0];

  if (history === null) {
    return (
      <AppShell active="overview">
        <main className="dash" aria-busy="true" />
      </AppShell>
    );
  }

  if (!latest) {
    return (
      <AppShell active="overview">
        <main className="dash">
          <div className="dash-head">
            <div>
              <h1>Welcome to HealthLens</h1>
              <p>Your overview appears here after your first assessment.</p>
            </div>
          </div>
          <section className="card as-empty">
            <span className="insight-ico">
              <Icon name="spark" size={22} />
            </span>
            <h2>No assessment yet</h2>
            <p className="muted">
              Answer a few questions and HealthLens will estimate your diabetes screening score and explain what drives
              it.
            </p>
            <Link href="/assess" className="btn btn-primary">
              Start health assessment
              <Icon name="arrow" size={18} />
            </Link>
          </section>
          <p className="note dash-note">
            <Icon name="info" size={18} />
            HealthLens is an academic health screening and awareness project. Predictions are not medical diagnoses.
          </p>
        </main>
      </AppShell>
    );
  }

  const { input, result } = latest;
  const flagged = result.flagged_higher_risk;
  const raising = result.factors.filter((f) => f.impact > 0);
  const lowering = result.factors.filter((f) => f.impact < 0);

  const insight = raising.length
    ? `${raising[0].label} is the biggest factor raising your score${
        lowering.length ? `, while ${lowering[0].label.toLowerCase()} is helping to lower it` : ""
      }.`
    : `Nothing is pushing your score up. ${lowering[0]?.label ?? "Your values"} has the largest lowering effect.`;

  const metrics = [
    { key: "glucose", label: "Glucose", value: input.Glucose ? String(input.Glucose) : "—", note: input.Glucose ? "mg/dL" : "Not measured", icon: "drop" },
    { key: "bmi", label: "BMI", value: input.BMI ? String(input.BMI) : "—", note: input.BMI ? bmiNote(input.BMI) : "Not measured", icon: "gauge" },
    { key: "bp", label: "Blood pressure", value: input.BloodPressure ? String(input.BloodPressure) : "—", note: input.BloodPressure ? "mmHg (diastolic)" : "Not measured", icon: "heart" },
    { key: "age", label: "Age", value: String(input.Age), note: "Years", icon: "user" },
  ];

  const trend = [...history].slice(0, 8).reverse();

  return (
    <AppShell active="overview">
      <main className="dash">
        <div className="dash-head">
          <div>
            <h1>Your overview</h1>
            <p>Based on your latest assessment, {when(latest.at)}.</p>
          </div>
          <Link href="/assess" className="btn btn-primary btn-sm">
            New assessment
          </Link>
        </div>

        <div className="top-grid">
          <section className={`card risk-card ${flagged ? "is-high" : "is-low"}`} aria-labelledby="risk-h">
            <h2 id="risk-h">Diabetes screening score</h2>
            <Gauge value={pct(result.probability)} caption={flagged ? "Higher-risk screen" : "Lower-risk screen"} size={250} />
            <p className="muted">Flagged at {pct(result.threshold)}% or more. A screening estimate, not a diagnosis.</p>
          </section>

          <section className="card stat" aria-labelledby="res-h">
            <h2 id="res-h">Screening result</h2>
            <p className={`as-verdict-sm ${flagged ? "is-high" : "is-low"}`}>
              {flagged ? "Higher risk" : "Lower risk"}
            </p>
            <p className="muted">{result.screening_result}.</p>
          </section>

          <section className="card stat" aria-labelledby="rel-h">
            <h2 id="rel-h">Model reliability</h2>
            {info ? (
              <>
                <p className="stat-big">
                  {info.test_metrics.roc_auc.toFixed(2)}
                  <small>ROC-AUC</small>
                </p>
                <p className="muted">
                  Catches {pct(info.test_metrics.recall)}% of people with diabetes; {pct(1 - info.test_metrics.precision)}% of
                  those flagged do not have it. Tested on {info.n_test} unseen patients.
                </p>
              </>
            ) : (
              <p className="muted">Model details load when the HealthLens API is reachable.</p>
            )}
          </section>
        </div>

        <section aria-labelledby="metrics-h" className="block">
          <div className="block-head">
            <h2 id="metrics-h">Health metrics</h2>
            <p>Values from your latest assessment.</p>
          </div>
          <div className="metrics">
            {metrics.map((m) => (
              <article key={m.key} className="metric">
                <span className="metric-ico">
                  <Icon name={m.icon} size={20} />
                </span>
                <p className="metric-label">{m.label}</p>
                <p className="metric-val">{m.value}</p>
                <p className="muted">{m.note}</p>
              </article>
            ))}
          </div>
        </section>

        <DailyPlan input={input} result={result} />

        <div className="two-grid">
          <section className="insight" aria-labelledby="insight-h">
            <span className="insight-ico">
              <Icon name="spark" size={22} />
            </span>
            <h2 id="insight-h">HealthLens AI insight</h2>
            <p>{insight}</p>
            <Link href="/assess?view=latest" className="btn btn-invert btn-sm">
              Understand this prediction
              <Icon name="arrow" size={16} />
            </Link>
          </section>

          <section className="card reports" id="history" aria-labelledby="hist-h">
            <div className="block-head row">
              <h2 id="hist-h">Recent assessments</h2>
              <button
                type="button"
                className="link as-reset"
                onClick={() => {
                  clearHistory();
                  setHistory([]);
                }}
              >
                Clear
              </button>
            </div>
            <ul className="report-list">
              {history.slice(0, 5).map((h) => (
                <li key={h.id}>
                  <span className="report-ico">
                    <Icon name="file" size={20} />
                  </span>
                  <span className="report-t">
                    <strong>Screening score {pct(h.result.probability)}%</strong>
                    <small>{when(h.at)}</small>
                  </span>
                  <span className={`status${h.result.flagged_higher_risk ? " is-high" : ""}`}>
                    {h.result.flagged_higher_risk ? "Higher risk" : "Lower risk"}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <section className="card block" aria-labelledby="trend-h">
          <div className="block-head">
            <h2 id="trend-h">Score over time</h2>
            <p>Your screening score across assessments saved in this browser.</p>
          </div>
          {trend.length >= 2 ? (
            <TrendChart
              bounds={[0, 100]}
              months={trend.map((t) => day(t.at))}
              series={{ score: { label: "Screening score", unit: "%", values: trend.map((t) => pct(t.result.probability)) } }}
            />
          ) : (
            <p className="muted">Take another assessment to see how your score changes.</p>
          )}
        </section>

        <p className="note dash-note">
          <Icon name="info" size={18} />
          {result.disclaimer} Results are stored only in this browser.
        </p>
      </main>
    </AppShell>
  );
}
