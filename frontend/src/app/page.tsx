import Link from "next/link";
import { Gauge, Icon, Logo } from "@/components/ui";
import ThemeSwitcher from "@/components/ThemeSwitcher";

const STEPS = [
  { title: "Add health data", text: "Enter your health information manually or upload a health report." },
  { title: "AI analysis", text: "HealthLens processes the available data and evaluates relevant health patterns." },
  { title: "Understand results", text: "View risk predictions, confidence information, and explanations of important factors." },
  { title: "Track progress", text: "Monitor health trends and follow useful recommendations over time." },
];

export default function Home() {
  return (
    <>
      <header className="nav">
        <div className="wrap nav-in">
          <Logo />
          <nav className="nav-links" aria-label="Sections">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#about">About</a>
          </nav>
          <div className="nav-actions">
            <ThemeSwitcher />
            <Link href="/dashboard" className="btn btn-primary btn-sm">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="hero wrap">
          <div className="hero-copy">
            <p className="pill">
              <Icon name="spark" size={16} />
              AI-powered health insights
            </p>
            <h1>Understand your health with clarity.</h1>
            <p className="lead">
              HealthLens helps you understand health data, identify chronic disease risk, explain AI predictions, and
              track health trends over time.
            </p>
            <div className="cta-row">
              <Link href="/dashboard" className="btn btn-primary">
                Start health assessment
                <Icon name="arrow" size={18} />
              </Link>
              <Link href="/dashboard" className="btn btn-ghost">
                <Icon name="upload" size={18} />
                Upload report
              </Link>
            </div>
            <p className="note">
              <Icon name="info" size={18} />
              HealthLens is designed as a health screening and awareness tool. It does not replace professional medical
              advice or diagnosis.
            </p>
          </div>

          <div className="lens" aria-label="Sample health overview">
            <span className="lens-ring" />
            <span className="lens-ring" />
            <span className="lens-ring" />
            <div className="lens-core">
              <Gauge value={24} caption="Diabetes risk: low" size={300} />
            </div>
            <div className="chip chip-a">
              <span className="chip-ico">
                <Icon name="drop" size={18} />
              </span>
              <span>
                <small>Glucose</small>
                <strong>118 mg/dL</strong>
              </span>
            </div>
            <div className="chip chip-b">
              <span className="chip-ico">
                <Icon name="gauge" size={18} />
              </span>
              <span>
                <small>BMI</small>
                <strong>24.8</strong>
              </span>
            </div>
            <div className="chip chip-c">
              <span className="chip-ico">
                <Icon name="up" size={18} />
              </span>
              <span>
                <small>Health score</small>
                <strong>82 / 100</strong>
              </span>
            </div>
            <p className="lens-tag">Sample preview</p>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="section wrap">
          <div className="section-head">
            <h2>Everything you need to understand your health data</h2>
            <p>A simple interface backed by explainable machine learning and health trend analysis.</p>
          </div>

          <div className="bento">
            <article className="tile t-risk">
              <span className="tile-ico">
                <Icon name="shield" size={22} />
              </span>
              <h3>Risk assessment</h3>
              <p>Estimate chronic disease risk using machine learning models trained on clinical health data.</p>
              <div className="risk-strip" aria-hidden="true">
                <span style={{ width: "24%" }} />
              </div>
              <div className="risk-scale" aria-hidden="true">
                <small>Low</small>
                <small>Moderate</small>
                <small>High</small>
              </div>
            </article>

            <article className="tile t-xai">
              <span className="tile-ico">
                <Icon name="search" size={22} />
              </span>
              <h3>Explainable AI</h3>
              <p>Understand which health factors contribute to an AI prediction using explainable AI techniques.</p>
              <ul className="bars" aria-hidden="true">
                <li>
                  <small>Glucose</small>
                  <i style={{ width: "78%" }} />
                </li>
                <li>
                  <small>BMI</small>
                  <i style={{ width: "46%" }} />
                </li>
                <li>
                  <small>Age</small>
                  <i style={{ width: "22%" }} />
                </li>
              </ul>
            </article>

            <article className="tile t-report">
              <span className="tile-ico">
                <Icon name="file" size={22} />
              </span>
              <h3>Report analysis</h3>
              <p>Upload health reports and extract relevant health information for easier understanding.</p>
            </article>

            <article className="tile t-trend">
              <span className="tile-ico">
                <Icon name="trend" size={22} />
              </span>
              <h3>Health trends</h3>
              <p>Track changes in your health measurements over time and identify unusual patterns.</p>
              <svg className="spark" viewBox="0 0 160 48" aria-hidden="true">
                <path d="M2 36 C 24 34, 30 20, 52 24 S 88 40, 106 22 S 140 8, 158 12" />
              </svg>
            </article>

            <article className="tile t-ask">
              <span className="tile-ico">
                <Icon name="chat" size={22} />
              </span>
              <h3>Ask HealthLens</h3>
              <p>Get simple explanations of your health results and AI-generated insights.</p>
            </article>

            <article className="tile t-insight">
              <span className="tile-ico">
                <Icon name="spark" size={22} />
              </span>
              <div>
                <h3>Personalized insights</h3>
                <p>Receive practical health recommendations based on your available health information.</p>
              </div>
            </article>
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="section wrap">
          <div className="section-head">
            <h2>How HealthLens works</h2>
            <p>From health data to understandable insights in a few simple steps.</p>
          </div>
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <span className="step-n">{i + 1}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* About */}
        <section id="about" className="section wrap about">
          <div>
            <h2>Making AI health insights easier to understand</h2>
            <p className="lead">
              HealthLens combines machine learning, explainable AI, report analysis, and health trend tracking into one
              simple platform designed to help people better understand their health information.
            </p>
          </div>
          <aside className="callout">
            <Icon name="info" size={22} />
            <p>
              <strong>Important:</strong> HealthLens is an academic AI healthcare project intended for screening and
              health awareness. Its predictions should not be treated as a medical diagnosis or a replacement for
              professional medical advice.
            </p>
          </aside>
        </section>

        {/* CTA */}
        <section className="wrap cta-wrap">
          <div className="cta">
            <span className="cta-ring" />
            <span className="cta-ring" />
            <h2>Start understanding your health</h2>
            <p>Explore your health data with a simple, explainable AI-powered experience.</p>
            <Link href="/dashboard" className="btn btn-invert">
              Get started
              <Icon name="arrow" size={18} />
            </Link>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="wrap foot-in">
          <Logo />
          <p>© 2026 HealthLens. AI-powered health insights, built as an academic project.</p>
        </div>
      </footer>
    </>
  );
}
