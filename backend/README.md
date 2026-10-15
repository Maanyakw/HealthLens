# HealthLens API

FastAPI service around the trained model and the explainer (`ml/src/explain.py`).

## Run locally (project root, venv on)
```
pip install fastapi "uvicorn[standard]" httpx pytest
uvicorn backend.main:app --reload --port 8000
```
Open http://localhost:8000/docs to try every endpoint in the browser.
Tests: `python -m pytest -q backend/tests`

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Is the service up and the model loaded |
| GET | `/model-info` | Model, test metrics, threshold, limitations |
| POST | `/predict` | Score + top factors (+ counterfactuals if flagged) |
| POST | `/what-if` | New score after changing Glucose and/or BMI |
| GET | `/global-importance` | Overall factor importance |

Leave `Glucose`, `BloodPressure`, `SkinThickness`, `Insulin`, `BMI` out (or `null`) when not measured.
`BloodPressure` is **diastolic**.

## Deploy to Google Cloud Run (project root)
```
gcloud run deploy healthlens-api --source . --region asia-southeast1 \
  --allow-unauthenticated --memory 2Gi \
  --set-env-vars ALLOWED_ORIGINS=https://health-lens-theta.vercel.app
```
Then in Vercel set `NEXT_PUBLIC_API_URL` to the URL it prints, and redeploy the frontend.
`--memory 2Gi` because SHAP/DiCE import heavy libraries. The first request after idle is slow (cold start).
