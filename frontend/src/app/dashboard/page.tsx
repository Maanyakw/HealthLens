import Link from "next/link";
import { Gauge, Icon, Logo } from "@/components/ui";
import ThemeSwitcher from "@/components/ThemeSwitcher";
import TrendChart from "@/components/TrendChart";

// Sample values. Replace with your real data / API response later.
const ASSESSMENT = {
  riskPercent: 24,
  riskLabel: "Low risk",
  healthScore: 82,
  scoreChange: "6% from last assessment",
  confidence: 91,
};

const METRICS = [
  { key: "glucose", label: "Glucose", value: "118", note: "mg/dL", icon: "drop" },
  { key: "bmi", label: "BMI", value: "24.8", note: "Normal range", icon: "gauge" },
  { key: "bp", label: "Blood pressure", value: "118/76", note: "Within normal range", icon: "heart" },
  { key: "age", label: "Age", value: "24", note: "Years", icon: "user" },
];

const REPORTS = [
  { title: "Blood Report", when: "2 days ago", status: "Analyzed" },
  { title: "Health Checkup", when: "1 week ago", status: "Analyzed" },
];

const MONTHS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct"];

const TRENDS = {
  glucose: { label: "Glucose", unit: "mg/dL", values: [126, 122, 121, 124, 120, 118] },
  bmi: { label: "BMI", unit: "", values: [25.6, 25.4, 25.2, 25.1, 24.9, 24.8] },
  score: { label: "Health score", unit: "/100", values: [68, 71, 74, 76, 77, 82] },
};

export const metadata = { title: "Dashboard | HealthLens" };

export default function Dashboard() {
  return (
    <div className="app">
      <aside className="side">
        <Logo tagline />
        <nav className="side-nav" aria-label="Dashboard">
          <Link href="/dashboard" className="side-link is-on" aria-current="page">
            <Icon name="grid" size={20} />
            Overview
          </Link>
          <a href="#reports" className="side-link">
            <Icon name="file" size={20} />
            Reports
          </a>
        </nav>
        <div className="side-foot">
          <ThemeSwitcher />
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-logo">
            <Logo />
          </div>
          <div className="topbar-right">
            <span className="topbar-theme">
              <ThemeSwitcher />
            </span>
            <span className="avatar" aria-label="Your profile">
              <Icon name="user" size={20} />
            </span>
          </div>
        </header>

        <main className="dash">
          <div className="dash-head">
            <div>
              <h1>Welcome back</h1>
              <p>Here&apos;s an overview of your current health information.</p>
            </div>
            <span className="avatar avatar-lg" aria-label="Your profile">
              <Icon name="user" size={24} />
            </span>
          </div>

          <div className="top-grid">
            <section className="card risk-card" aria-labelledby="risk-h">
              <h2 id="risk-h">Diabetes risk</h2>
              <Gauge value={ASSESSMENT.riskPercent} caption={ASSESSMENT.riskLabel} size={250} />
              <p className="muted">Based on your latest health assessment</p>
            </section>

            <section className="card stat score-card" aria-labelledby="score-h">
              <h2 id="score-h">Health score</h2>
              <p className="stat-big">
                {ASSESSMENT.healthScore}
                <small>/ 100</small>
              </p>
              <p className="delta">
                <Icon name="up" size={16} />
                {ASSESSMENT.scoreChange}
              </p>
            </section>

            <section className="card stat conf-card" aria-labelledby="conf-h">
              <h2 id="conf-h">Prediction confidence</h2>
              <p className="stat-big">{ASSESSMENT.confidence}%</p>
              <div className="meter" role="img" aria-label={`${ASSESSMENT.confidence} percent confidence`}>
                <i style={{ width: `${ASSESSMENT.confidence}%` }} />
              </div>
              <p className="muted">Confidence of the current model prediction</p>
            </section>
          </div>

          <section aria-labelledby="metrics-h" className="block">
            <div className="block-head">
              <h2 id="metrics-h">Health metrics</h2>
              <p>Latest values used for your health assessment.</p>
            </div>
            <div className="metrics">
              {METRICS.map((m) => (
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

          <div className="two-grid">
            <section className="insight" aria-labelledby="insight-h">
              <span className="insight-ico">
                <Icon name="spark" size={22} />
              </span>
              <h2 id="insight-h">HealthLens AI insight</h2>
              <p>
                Your current assessment indicates a relatively low diabetes risk. Glucose and BMI are among the
                important factors considered by the model.
              </p>
              <Link href="/dashboard" className="btn btn-invert btn-sm">
                Understand this prediction
                <Icon name="arrow" size={16} />
              </Link>
            </section>

            <section className="card reports" id="reports" aria-labelledby="reports-h">
              <div className="block-head row">
                <h2 id="reports-h">Recent reports</h2>
                <Link href="/dashboard" className="link">
                  View all
                </Link>
              </div>
              <ul className="report-list">
                {REPORTS.map((r) => (
                  <li key={r.title}>
                    <span className="report-ico">
                      <Icon name="file" size={20} />
                    </span>
                    <span className="report-t">
                      <strong>{r.title}</strong>
                      <small>{r.when}</small>
                    </span>
                    <span className="status">
                      <Icon name="check" size={14} />
                      {r.status}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section className="card block" aria-labelledby="trend-h">
            <div className="block-head">
              <h2 id="trend-h">Health trends</h2>
              <p>Track how your health measurements change over time. Last 6 months.</p>
            </div>
            <TrendChart months={MONTHS} series={TRENDS} />
          </section>

          <p className="note dash-note">
            <Icon name="info" size={18} />
            HealthLens is an academic health screening and awareness project. The information and predictions shown here
            are not medical diagnoses and should not replace advice from a qualified healthcare professional.
          </p>
        </main>
      </div>
    </div>
  );
}
