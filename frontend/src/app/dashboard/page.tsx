"use client";

export default function Dashboard() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">

      {/* HEADER */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5 lg:px-8">

          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 font-bold text-white">
              H
            </div>

            <div>
              <h1 className="text-xl font-bold">
                HealthLens
              </h1>

              <p className="text-xs text-slate-500">
                AI Health Companion
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">
              Reports
            </button>

            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
              👤
            </div>
          </div>

        </div>
      </header>


      {/* MAIN CONTENT */}
      <div className="mx-auto max-w-7xl px-6 py-10 lg:px-8">

        {/* PAGE TITLE */}
        <div className="mb-8">
          <p className="text-sm font-medium text-blue-600">
            HEALTH OVERVIEW
          </p>

          <h2 className="mt-1 text-3xl font-bold">
            Welcome back
          </h2>

          <p className="mt-2 text-slate-500">
            Here's an overview of your current health information.
          </p>
        </div>


        {/* TOP CARDS */}
        <div className="grid gap-5 md:grid-cols-3">

          {/* Diabetes Risk */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-500">
                Diabetes Risk
              </p>

              <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
                Low Risk
              </span>
            </div>

            <p className="mt-4 text-4xl font-bold">
              24%
            </p>

            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full w-[24%] rounded-full bg-green-500" />
            </div>

            <p className="mt-3 text-xs text-slate-500">
              Based on your latest health assessment
            </p>

          </div>


          {/* Health Score */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

            <p className="text-sm text-slate-500">
              Health Score
            </p>

            <div className="mt-3 flex items-end gap-2">
              <p className="text-4xl font-bold">
                82
              </p>

              <p className="mb-1 text-sm text-slate-400">
                / 100
              </p>
            </div>

            <p className="mt-3 text-sm text-green-600">
              ↑ 6% from last assessment
            </p>

          </div>


          {/* Confidence */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

            <p className="text-sm text-slate-500">
              Prediction Confidence
            </p>

            <p className="mt-3 text-4xl font-bold">
              91%
            </p>

            <p className="mt-3 text-sm text-slate-500">
              Confidence of the current model prediction
            </p>

          </div>

        </div>


        {/* HEALTH METRICS */}
        <section className="mt-8">

          <div className="mb-4">
            <h3 className="text-xl font-bold">
              Health Metrics
            </h3>

            <p className="mt-1 text-sm text-slate-500">
              Latest values used for your health assessment.
            </p>
          </div>


          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">

            {/* Glucose */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">

              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">
                  Glucose
                </p>

                <span className="text-xl">
                  🩸
                </span>
              </div>

              <p className="mt-4 text-2xl font-bold">
                118
              </p>

              <p className="mt-1 text-xs text-slate-400">
                mg/dL
              </p>

            </div>


            {/* BMI */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">

              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">
                  BMI
                </p>

                <span className="text-xl">
                  ⚖️
                </span>
              </div>

              <p className="mt-4 text-2xl font-bold">
                24.8
              </p>

              <p className="mt-1 text-xs text-green-600">
                Normal range
              </p>

            </div>


            {/* Blood Pressure */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">

              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">
                  Blood Pressure
                </p>

                <span className="text-xl">
                  ❤️
                </span>
              </div>

              <p className="mt-4 text-2xl font-bold">
                118/76
              </p>

              <p className="mt-1 text-xs text-green-600">
                Within normal range
              </p>

            </div>


            {/* Age */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">

              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">
                  Age
                </p>

                <span className="text-xl">
                  👤
                </span>
              </div>

              <p className="mt-4 text-2xl font-bold">
                24
              </p>

              <p className="mt-1 text-xs text-slate-400">
                Years
              </p>

            </div>

          </div>

        </section>


        {/* LOWER SECTION */}
        <div className="mt-8 grid gap-6 lg:grid-cols-3">

          {/* AI INSIGHT */}
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-6 lg:col-span-2">

            <div className="flex gap-4">

              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white">
                ✦
              </div>

              <div>
                <p className="font-semibold text-blue-900">
                  HealthLens AI Insight
                </p>

                <p className="mt-2 text-sm leading-6 text-blue-800">
                  Your current assessment indicates a relatively
                  low diabetes risk. Glucose and BMI are among the
                  important factors considered by the model.
                </p>

                <button className="mt-4 text-sm font-semibold text-blue-700 hover:underline">
                  Understand this prediction →
                </button>
              </div>

            </div>

          </div>


          {/* RECENT REPORTS */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

            <div className="flex items-center justify-between">

              <h3 className="font-semibold">
                Recent Reports
              </h3>

              <button className="text-sm font-medium text-blue-600">
                View all
              </button>

            </div>


            <div className="mt-5 space-y-4">

              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3">

                <div className="flex items-center gap-3">

                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-50">
                    📄
                  </div>

                  <div>
                    <p className="text-sm font-medium">
                      Blood Report
                    </p>

                    <p className="text-xs text-slate-400">
                      2 days ago
                    </p>
                  </div>

                </div>

                <span className="text-xs text-green-600">
                  Analyzed
                </span>

              </div>


              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3">

                <div className="flex items-center gap-3">

                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50">
                    📄
                  </div>

                  <div>
                    <p className="text-sm font-medium">
                      Health Checkup
                    </p>

                    <p className="text-xs text-slate-400">
                      1 week ago
                    </p>
                  </div>

                </div>

                <span className="text-xs text-green-600">
                  Analyzed
                </span>

              </div>

            </div>

          </div>

        </div>


        {/* HEALTH TRENDS */}
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">

            <div>
              <h3 className="text-xl font-bold">
                Health Trends
              </h3>

              <p className="mt-1 text-sm text-slate-500">
                Track how your health measurements change over time.
              </p>
            </div>

            <button className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">
              Last 6 months
            </button>

          </div>


          {/* Simple Chart Placeholder */}
          <div className="mt-8 flex h-48 items-end gap-4 rounded-xl bg-slate-50 px-6 pb-6 pt-6">

            <div className="h-[35%] flex-1 rounded-t-lg bg-blue-200" />
            <div className="h-[45%] flex-1 rounded-t-lg bg-blue-300" />
            <div className="h-[40%] flex-1 rounded-t-lg bg-blue-300" />
            <div className="h-[58%] flex-1 rounded-t-lg bg-blue-400" />
            <div className="h-[52%] flex-1 rounded-t-lg bg-blue-400" />
            <div className="h-[70%] flex-1 rounded-t-lg bg-blue-500" />

          </div>

          <div className="mt-3 flex justify-between px-2 text-xs text-slate-400">
            <span>May</span>
            <span>Jun</span>
            <span>Jul</span>
            <span>Aug</span>
            <span>Sep</span>
            <span>Oct</span>
          </div>

        </section>


        {/* DISCLAIMER */}
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-4">

          <p className="text-xs leading-5 text-slate-500">
            <span className="font-semibold text-slate-700">
              Important:
            </span>{" "}
            HealthLens is an academic health screening and awareness
            project. The information and predictions shown here are
            not medical diagnoses and should not replace advice from
            a qualified healthcare professional.
          </p>

        </div>

      </div>

    </main>
  );
}