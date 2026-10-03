"use client";

import Link from "next/link";

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-2xl">
        {icon}
      </div>

      <h3 className="mb-2 text-lg font-semibold text-slate-900">{title}</h3>

      <p className="text-sm leading-6 text-slate-600">{description}</p>
    </div>
  );
}

function StepCard({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="relative rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 font-bold text-white">
        {number}
      </div>

      <h3 className="mb-2 text-lg font-semibold text-slate-900">{title}</h3>

      <p className="text-sm leading-6 text-slate-600">{description}</p>
    </div>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      {/* NAVBAR */}
      <nav className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-8">
          
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-lg font-bold text-white">
              H
            </div>

            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900">
                HealthLens
              </h1>
              <p className="text-xs text-slate-500">
                AI Health Companion
              </p>
            </div>
          </Link>

          {/* Navigation */}
          <div className="hidden items-center gap-8 md:flex">
            <a
              href="#features"
              className="text-sm font-medium text-slate-600 transition hover:text-blue-600"
            >
              Features
            </a>

            <a
              href="#how-it-works"
              className="text-sm font-medium text-slate-600 transition hover:text-blue-600"
            >
              How It Works
            </a>

            <a
              href="#about"
              className="text-sm font-medium text-slate-600 transition hover:text-blue-600"
            >
              About
            </a>

            <a
              href="/dashboard"
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700"
              >
              Get Started
            </a>
          </div>
        </div>
      </nav>

      {/* HERO SECTION */}
      <section className="relative overflow-hidden bg-white">
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 py-20 lg:grid-cols-2 lg:px-8 lg:py-28">

          {/* Hero Text */}
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700">
              <span>✦</span>
              AI-powered health insights
            </div>

            <h2 className="max-w-3xl text-5xl font-bold leading-tight tracking-tight text-slate-900 md:text-6xl">
              Understand your health
              <span className="block text-blue-600">
                with clarity.
              </span>
            </h2>

            <p className="mt-6 max-w-xl text-lg leading-8 text-slate-600">
              HealthLens helps you understand health data, identify
              chronic disease risk, explain AI predictions, and track
              health trends over time.
            </p>

            <div className="mt-8 flex flex-col gap-4 sm:flex-row">
              <a
                href="/dashboard"
                className="inline-block rounded-xl bg-blue-600 px-6 py-3.5 font-semibold text-white shadow-sm transition hover:bg-blue-700"
                >
                Start Health Assessment →
              </a>

              <button className="rounded-xl border border-slate-300 bg-white px-6 py-3.5 font-semibold text-slate-700 transition hover:border-blue-400 hover:text-blue-600">
                Upload Report
              </button>
            </div>

            <div className="mt-6 flex items-start gap-2 text-xs leading-5 text-slate-500">
              <span className="mt-0.5">ⓘ</span>

              <p>
                HealthLens is designed as a health screening and
                awareness tool. It does not replace professional
                medical advice or diagnosis.
              </p>
            </div>
          </div>

          {/* Dashboard Preview */}
          <div className="relative">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 shadow-xl">

              {/* Preview Header */}
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
                    Health Overview
                  </p>

                  <h3 className="mt-1 text-xl font-bold text-slate-900">
                    Welcome back
                  </h3>
                </div>

                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-700">
                  👤
                </div>
              </div>

              {/* Cards */}
              <div className="grid grid-cols-2 gap-4">

                {/* Risk */}
                <div className="rounded-2xl bg-white p-5 shadow-sm">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm text-slate-500">
                      Diabetes Risk
                    </span>

                    <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-semibold text-green-700">
                      Low
                    </span>
                  </div>

                  <p className="text-3xl font-bold text-slate-900">
                    24%
                  </p>

                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full w-[24%] rounded-full bg-green-500" />
                  </div>
                </div>

                {/* Health Score */}
                <div className="rounded-2xl bg-white p-5 shadow-sm">
                  <p className="text-sm text-slate-500">
                    Health Score
                  </p>

                  <p className="mt-2 text-3xl font-bold text-slate-900">
                    82
                    <span className="text-base font-medium text-slate-400">
                      /100
                    </span>
                  </p>

                  <p className="mt-2 text-xs text-green-600">
                    ↑ 6% this month
                  </p>
                </div>

                {/* Reports */}
                <div className="rounded-2xl bg-white p-5 shadow-sm">
                  <p className="text-sm text-slate-500">
                    Reports
                  </p>

                  <p className="mt-2 text-3xl font-bold text-slate-900">
                    08
                  </p>

                  <p className="mt-2 text-xs text-slate-400">
                    Last uploaded 2 days ago
                  </p>
                </div>

                {/* Trends */}
                <div className="rounded-2xl bg-white p-5 shadow-sm">
                  <p className="text-sm text-slate-500">
                    Health Trends
                  </p>

                  <div className="mt-4 flex h-12 items-end gap-1.5">
                    <div className="h-5 w-2 rounded bg-blue-200" />
                    <div className="h-7 w-2 rounded bg-blue-300" />
                    <div className="h-6 w-2 rounded bg-blue-300" />
                    <div className="h-9 w-2 rounded bg-blue-400" />
                    <div className="h-8 w-2 rounded bg-blue-500" />
                    <div className="h-11 w-2 rounded bg-blue-600" />
                    <div className="h-10 w-2 rounded bg-blue-500" />
                  </div>
                </div>
              </div>

              {/* AI Insight */}
              <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-5">
                <div className="flex gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white">
                    ✦
                  </div>

                  <div>
                    <p className="font-semibold text-blue-900">
                      HealthLens Insight
                    </p>

                    <p className="mt-1 text-sm leading-6 text-blue-800">
                      Your glucose and BMI values are important
                      factors in your current risk assessment.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="bg-slate-50 py-20">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">

          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-blue-600">
              What HealthLens offers
            </p>

            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
              Everything you need to understand your health data
            </h2>

            <p className="mt-4 text-slate-600">
              A simple interface backed by explainable machine
              learning and health trend analysis.
            </p>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">

            <FeatureCard
              icon="🩺"
              title="Risk Assessment"
              description="Estimate chronic disease risk using machine learning models trained on clinical health data."
            />

            <FeatureCard
              icon="📄"
              title="Report Analysis"
              description="Upload health reports and extract relevant health information for easier understanding."
            />

            <FeatureCard
              icon="🔍"
              title="Explainable AI"
              description="Understand which health factors contribute to an AI prediction using explainable AI techniques."
            />

            <FeatureCard
              icon="📈"
              title="Health Trends"
              description="Track changes in your health measurements over time and identify unusual patterns."
            />

            <FeatureCard
              icon="🤖"
              title="Ask HealthLens"
              description="Get simple explanations of your health results and AI-generated insights."
            />

            <FeatureCard
              icon="💡"
              title="Personalized Insights"
              description="Receive practical health recommendations based on your available health information."
            />

          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how-it-works" className="bg-white py-20">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">

          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-wider text-blue-600">
              Simple process
            </p>

            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
              How HealthLens works
            </h2>

            <p className="mt-4 text-slate-600">
              From health data to understandable insights in a few
              simple steps.
            </p>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">

            <StepCard
              number="1"
              title="Add Health Data"
              description="Enter your health information manually or upload a health report."
            />

            <StepCard
              number="2"
              title="AI Analysis"
              description="HealthLens processes the available data and evaluates relevant health patterns."
            />

            <StepCard
              number="3"
              title="Understand Results"
              description="View risk predictions, confidence information, and explanations of important factors."
            />

            <StepCard
              number="4"
              title="Track Progress"
              description="Monitor health trends and follow useful recommendations over time."
            />

          </div>
        </div>
      </section>

      {/* ABOUT */}
      <section id="about" className="bg-slate-900 py-20 text-white">
        <div className="mx-auto max-w-5xl px-6 text-center lg:px-8">

          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-2xl font-bold">
            H
          </div>

          <h2 className="mt-6 text-3xl font-bold md:text-4xl">
            Making AI health insights easier to understand
          </h2>

          <p className="mx-auto mt-5 max-w-2xl leading-7 text-slate-300">
            HealthLens combines machine learning, explainable AI,
            report analysis, and health trend tracking into one
            simple platform designed to help people better
            understand their health information.
          </p>

          <div className="mx-auto mt-8 max-w-3xl rounded-2xl border border-slate-700 bg-slate-800 p-6 text-left">
            <p className="text-sm leading-6 text-slate-300">
              <span className="font-semibold text-white">
                Important:
              </span>{" "}
              HealthLens is an academic AI healthcare project
              intended for screening and health awareness. Its
              predictions should not be treated as a medical
              diagnosis or a replacement for professional medical
              advice.
            </p>
          </div>

        </div>
      </section>

      {/* GET STARTED */}
      <section id="get-started" className="bg-blue-600 py-16">
        <div className="mx-auto max-w-4xl px-6 text-center lg:px-8">

          <h2 className="text-3xl font-bold text-white md:text-4xl">
            Start understanding your health
          </h2>

          <p className="mx-auto mt-4 max-w-2xl text-blue-100">
            Explore your health data with a simple, explainable
            AI-powered experience.
          </p>

          <button className="mt-8 rounded-xl bg-white px-7 py-3.5 font-semibold text-blue-700 shadow-sm transition hover:bg-blue-50">
            Get Started →
          </button>

        </div>
      </section>

      {/* FOOTER */}
      <footer className="bg-slate-950 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 text-sm text-slate-400 md:flex-row lg:px-8">

          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
              H
            </div>

            <span>
              © 2026 HealthLens
            </span>
          </div>

          <p>
            AI-powered health insights • Academic Project
          </p>

        </div>
      </footer>
    </main>
  );
}