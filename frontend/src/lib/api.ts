// Talks to the HealthLens API. Set NEXT_PUBLIC_API_URL in Vercel
// (Project -> Settings -> Environment Variables), e.g. https://healthlens-api-xxxx.a.run.app
// Locally, put NEXT_PUBLIC_API_URL=http://localhost:8000 in frontend/.env.local

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type PatientInput = {
  Pregnancies: number;
  Glucose: number | null;
  BloodPressure: number | null; // diastolic
  SkinThickness: number | null;
  Insulin: number | null;
  BMI: number | null;
  DiabetesPedigreeFunction: number;
  Age: number;
};

export type Factor = {
  feature: string;
  label: string;
  value_used: number;
  was_missing: boolean;
  impact: number;
  direction: "raises risk" | "lowers risk";
  share: number;
};

export type CounterfactualOption = {
  changes: { feature: string; label: string; from: number; to: number }[];
  new_probability: number;
};

export type PredictResponse = {
  probability: number;
  threshold: number;
  flagged_higher_risk: boolean;
  screening_result: string;
  factors: Factor[];
  features_not_used_by_model: string[];
  not_measured: string[];
  counterfactuals: { options: CounterfactualOption[]; message?: string } | null;
  disclaimer: string;
};

export type WhatIfResponse = {
  changes: Record<string, number>;
  before: number;
  after: number;
  threshold: number;
  flagged_before: boolean;
  flagged_after: boolean;
};

export type ModelInfo = {
  model: string;
  features_used_by_model: string[];
  dataset: string;
  threshold: number;
  n_train: number;
  n_test: number;
  test_metrics: {
    roc_auc: number;
    roc_auc_95ci: [number, number];
    pr_auc: number;
    recall: number;
    precision: number;
    specificity: number;
  };
  limitations: string[];
  disclaimer: string;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(
      `Could not reach the HealthLens API at ${API_URL}. If you are testing locally, start it with: uvicorn backend.main:app --port 8000`,
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = Array.isArray(body.detail)
        ? body.detail.map((d: { loc?: string[]; msg?: string }) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join("; ")
        : String(body.detail ?? "");
    } catch {
      /* ignore */
    }
    throw new Error(detail || `The API returned an error (${res.status}).`);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const predict = (patient: PatientInput) => call<PredictResponse>("/predict", json(patient));

export const whatIf = (patient: PatientInput, changes: Record<string, number>) =>
  call<WhatIfResponse>("/what-if", json({ patient, changes }));

export const getModelInfo = () => call<ModelInfo>("/model-info");
