# HealthLens v2: TabPFN-3.5 + report reading + narrator + chat

Everything here is NEW files. Nothing replaces your existing files except where marked "replaces".
Free options only. Synthetic sample reports only.

## 1. What is in this zip and where it goes

| File / folder | Put it at (in your repo) | What it is |
|---|---|---|
| `ml/notebooks/HealthLens_TabPFN_Benchmark.ipynb` | `ml/notebooks/` (then open in Colab) | Compares TabPFN-3.5, XGBoost, Logistic Regression; times everything; exports the model card |
| `ml/src/explain_agnostic.py`, `ml/src/benchmark.py` | `ml/src/` | Exact SHAP for any model; counterfactual search; benchmark code |
| `ml/tests/test_explain_agnostic.py` | `ml/tests/` | 9 tests |
| `backend/hl2/*` | `backend/hl2/` | API, model loading, report reader, narrator, chat, safety checks, Gemini client |
| `backend/main.py` | `backend/main.py` (**replaces** the old one) | Starts the v2 API |
| `backend/requirements.txt` | `backend/requirements.txt` (**replaces**) | Dependencies (TabPFN 10.0.0, the version tested in Colab) |
| `backend/tests/*` | `backend/tests/` | 63 tests (stand-in model, fake AI service) |
| `Dockerfile`, `.dockerignore`, `.gcloudignore` | repo root (**replace** the old ones) | Cloud Run build |
| `tools/make_synthetic_reports.py`, `tools/eval_reader.py` | `tools/` | Makes the synthetic reports; scores the report reader |
| `samples/reports/*` | `samples/reports/` | 9 synthetic reports + `truth.json` |
| `frontend/src/lib/api.ts` | `frontend/src/lib/api.ts` (**replaces**) | Your old file plus `narrate`, `chat`, `readReport` and their types. Old exports are unchanged |
| `frontend/src/components/AssessmentResult.tsx` | same path (**replaces**) | Your step-6b version + the "In plain words" panel and "Ask HealthLens"; wording about missing values corrected |
| `frontend/src/app/assess/page.tsx` | same path (**replaces**) | Your step-6 version + report upload that pre-fills the form; glucose hint now explains the 2-hour test |
| `frontend/src/app/page.tsx` | same path (**replaces**) | Landing page: the "Report analysis" and "Ask HealthLens" tiles now describe what really exists |
| `frontend/src/components/{ReportUpload,Narrative,AskHealthLens}.tsx`, `hl2.css` | `frontend/src/components/` | New UI pieces |
| `backend/hl2/legacy.py` | (inside `backend/hl2/`) | Keeps the OLD response shapes, so `DashboardView`, `plan.ts`, `FactorBars` etc. work unchanged |

Keep your old `ml/models`, `explain.py` and old frontend files until the new version works, so you can go back.

The frontend files were built on top of YOUR step-6 / step-6b files (the ones you re-attached). If you have changed those files since,
tell me before replacing anything, and I will merge instead.

## 2. Step A: run the benchmark in Colab (about 20 minutes)
1. Open `HealthLens_TabPFN_Benchmark.ipynb` in Google Colab.
2. Left sidebar > key icon > check that `TABPFN_TOKEN` exists and "Notebook access" is ON.
3. In the cell that writes `benchmark.py`, set `RANDOM_STATE` to the same value as in your `ml/src/train.py`.
4. **Runtime > Change runtime type > CPU** (the live server has no GPU, so GPU timings would mislead you). Then Run all.
5. Read the timing section. Expected on a 2-CPU runtime: about 8 s for SHAP and about 2 s for the counterfactual search. Send me both numbers.
6. The last cell downloads `healthlens_artifacts.zip`. Unzip it and put the `artifacts` folder at `ml/artifacts/` in your repo
   (`model_card.json` and `train.csv`). Make sure `git status` shows them (check `.gitignore` does not hide `*.csv`).
7. Send me the comparison table, the timing lines and `model_card.json`. I will update the PDFs and slides with the real numbers.

Numbers will not match your earlier report exactly: this notebook compares all three models on all 8 raw features
with the same protocol, while the earlier logistic regression used 6 selected features.

## 3. Step B: test locally (about 10 minutes)
```bash
cd <repo>
source .venv/bin/activate
pip install -r backend/requirements.txt pytest
python -m pytest backend/tests ml/tests -q          # needs ml/data/pima-indians-diabetes.csv
export TABPFN_TOKEN=...        # your token, in your own terminal only
export GEMINI_API_KEY=...      # free key from https://aistudio.google.com/apikey  (optional)
uvicorn main:app --app-dir backend --port 8000
```
Check http://localhost:8000/docs . Then, with the key set, measure the report reader:
```bash
python tools/eval_reader.py --reports samples/reports
```
This is the first time the real AI service reads these reports, so the result is the true accuracy. Tell me what it prints.
Free-tier model names change: if you get "model not found", pick a current Flash model in AI Studio and `export GEMINI_MODEL=<name>`.

## 4. Step C: deploy the backend to Cloud Run (free tier, not Vercel)
Needs a Google Cloud project with billing enabled (the free tier covers a demo, but a billing account must exist).
Free-tier amounts and regions change, so check the Cloud Run pricing page, and **set a budget alert** first.
The container image (about 2 GB) sits in Artifact Registry, which gives only 0.5 GB free, so expect cents per month; delete the image after the demo.

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# store secrets (type them; they are not saved in your shell history or any file)
read -s T; printf '%s' "$T" | gcloud secrets create tabpfn-token --data-file=-; unset T
read -s K; printf '%s' "$K" | gcloud secrets create gemini-api-key --data-file=-; unset K

PN=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" --role=roles/secretmanager.secretAccessor

gcloud run deploy healthlens-api --source . --region asia-south1 --allow-unauthenticated \
  --memory 4Gi --cpu 2 --cpu-boost --min-instances 0 --max-instances 1 --concurrency 4 --timeout 300 \
  --set-secrets TABPFN_TOKEN=tabpfn-token:latest,GEMINI_API_KEY=gemini-api-key:latest
```
Skip the Gemini lines if you do not want the AI features (the app then uses fixed wording and rule-based chat; report upload is switched off).
Then open `<service-url>/health` until it says `"model_loaded": true`.

In Vercel: Project > Settings > Environment Variables: `NEXT_PUBLIC_API_URL` = the service URL (no trailing slash), for all environments, then redeploy.

Things to know:
* **Cold starts.** With `--min-instances 0` the server sleeps when idle, and the first request downloads the TabPFN weights again. Expect a wait of up to a minute or more. Open `/health` a few minutes before any demo.
* `--max-instances 1` is deliberate: it caps cost and free-tier AI usage.
* The memory (4 GiB) and CPU values are my starting guess; I could not run TabPFN-3.5 here. If the logs show out-of-memory, raise memory to 8Gi.
* TabPFN-3.5 weights have a **non-commercial licence**. Fine for coursework; do not use this deployment commercially.
* Do not make the GitHub repo include the weights or your token.

## 5. What each new feature does, and its safety rules
* **Risk score:** TabPFN-3.5 (a transformer for small tables). No separate training; it is fitted on the 614 training rows when the server starts. Missing values stay missing (TabPFN handles them).
* **Explanations:** exact Shapley values by brute force (256 feature subsets x 4 representative background rows, chosen by k-means). They always add up to the score, measured against the average of those 4 rows (so the baseline is an approximation of the population average, not exactly it). The counterfactual search is a simple grid over Glucose and BMI (lowering only, never below 70 mg/dL or BMI 18.5, searching at most 60 mg/dL and 8 BMI points down). It is **not the DiCE library**, so describe it as "a counterfactual search" in the report. Changes larger than 40 mg/dL glucose or 5 BMI points are marked "not realistic" and never presented as an easy goal.
* **Report reader:** one Gemini call returns JSON; plain Python then converts units, checks ranges and adds warnings. Fasting or random glucose is flagged, because the model learned from the 2-hour glucose-tolerance value and a fasting number can understate risk. The person must tick that they checked the values.
* **Narrator:** the AI may only rephrase numbers we computed. Any other number, any diagnosis or medicine wording, links or markdown cause the text to be rejected and a fixed template to be shown. The caution lines are added by code.
* **Chat:** answers from your result and the model card; a `what_if` tool re-scores with the real model. Emergency words never reach the AI.
* **Limits:** 8 AI calls per minute per visitor and 150 per day overall (then fixed wording is used), file limit 5 MB, PDF/PNG/JPEG only.
* **Privacy:** Google's free tier may use inputs to improve its products. That is why only synthetic reports are allowed, with a tick-box and a warning on the upload screen. Never upload a real report.

## 6. What changed in the API
`/predict`, `/what-if`, `/model-info` and `/global-importance` keep the same field names as before, so your existing pages work unchanged.
What is different:
* `factors[].impact` is now in **probability points** (0.27 = 27 points), not log-odds (`explanation_unit` says "probability").
* `features_not_used_by_model` is empty: TabPFN uses all 8 features, so the "not used by this model" line disappears.
* `counterfactuals` come from the new grid search (not DiCE). Options needing a very large change are hidden; if none are left, a message says so.
* Missing values are NOT filled with a typical value any more; TabPFN handles them natively. The result page wording was corrected.
* New fields: `base_probability`, `ai_payload` (echoed back to `/narrate` and `/chat`), and extra model-comparison data in `/model-info`.
* New endpoints: `POST /narrate`, `POST /chat`, `POST /report/read`.
* `/global-importance` is now permutation importance (how much ROC-AUC drops when a feature is shuffled).
* Results saved in the browser by older versions have no `ai_payload`; the explanation panel and chat simply do not appear for them.

## 7. What was and was not tested
Tested here (72 Python tests; TypeScript strict checks of the whole frontend with your real files; interaction tests of the 3 new components AND of your real `/assess` page, including report upload -> pre-fill -> result -> explanation panel, in a simulated browser with a fake API; the UI tests are not in the zip):
the Shapley maths (additivity, closed form, zero for unused features), counterfactual rules, unit conversion and range checks, the safety checks, rate limits, CORS, file checks, the Gemini request/response handling (against a fake server), and the UI components.
**NOT tested** (I could not reach these from my sandbox): TabPFN-3.5 itself and its speed, the real Gemini API and its extraction accuracy, the Docker build, Cloud Run, and your existing pages. The 9/9 "dry run" of `eval_reader.py` only tests the scoring script, not the AI.

## 8. Plan to finish before Nov 21
| Day | Task |
|---|---|
| Sun Nov 15 | Colab benchmark on a CPU runtime (section 2). Send me the table, timings and `model_card.json`. Then section 3 (local tests + `eval_reader.py`); send me the output. |
| Mon Nov 16 | Put the files in your repo (section 1), run the app locally against `uvicorn`, then Cloud Run deploy + Vercel env var (section 4). |
| Tue-Wed Nov 17-18 | Live test with the synthetic reports. Send me screenshots or errors; I fix them. |
| Thu Nov 19 | I update the report PDFs, roadmap and slide numbers with your real results. |
| Fri Nov 20 | Buffer + final end-to-end test on the live site. |
| Sat Nov 21 | Deadline. |

If the Colab timings are bad (SHAP over about 15 s on CPU), tell me right away: the fix (fewer background rows, a cache) is quick, but I need the numbers first.

## 9. Speed settings (measured in Colab, 2-CPU runtime, 16 Nov)
TabPFN-3.5 with its defaults took about 45 s per call on CPU, whatever the number of rows, so it was unusable live. The code now uses
`fit_mode="fit_with_cache"` and `n_estimators=1` (set in `benchmark.py` and `model_service.py`, recorded in the model card):

| Setting | Fit | 1 patient | 1,078 rows | Test ROC-AUC |
|---|---|---|---|---|
| defaults | 0.2 s | 43-48 s | not run | 0.822 |
| cache + 1 member (used) | 17 s | 0.10 s | 8.8 s | 0.822 |
| cache + 2 members | 12 s | 0.26 s | 15.8 s | 0.823 |
| cache + 4 members | 24 s | 0.27 s | 34.9 s | 0.821 |

Differences of 0.001 in AUC are noise on 154 test patients. Say in the report that TabPFN-3.5 is run with a single ensemble member
and a cached training context for CPU speed. The cross-validation numbers must be re-run with these settings (notebook, Step A).
Server start-up now takes the weight download plus about 17 s of fitting.
