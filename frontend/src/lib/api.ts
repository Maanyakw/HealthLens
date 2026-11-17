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

export type AiPayload = {
  score: number;
  factors: { feature: string; effect: number }[];
  counterfactuals: unknown | null;
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
  base_probability?: number; // average score; base + sum(impact) = probability
  ai_payload?: AiPayload; // echoed back to /narrate and /chat (missing in results saved before this version)
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
  comparison?: Record<string, { cv_roc_auc: number; test_roc_auc: number }>;
};

async function call<T>(path: string, init?: RequestInit, timeoutMs = 90_000): Promise<T> {
  let res: Response;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, signal: ctrl.signal });
  } catch {
    throw new Error(
      `Could not reach the HealthLens API at ${API_URL}. If it is hosted on Cloud Run, the first request after a quiet period can take a minute, so please try again. Locally, start it with: uvicorn main:app --app-dir backend --port 8000`,
    );
  } finally {
    clearTimeout(timer);
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

// ---------------------------------------------------------------- v2 features: narrator, chat, report reading
export const FIELD_NAMES = [
  "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI", "DiabetesPedigreeFunction", "Age",
] as const;
export type FieldName = (typeof FIELD_NAMES)[number];

export type Narration = {
  patient_summary: string;
  clinician_summary: string;
  source: "llm" | "template";
  disclaimer: string;
  llm_rejected_reason: string | null;
};
export type ChatReply = { answer: string; source: "llm" | "rules" | "safety"; tools_used: string[]; disclaimer: string };
export type ChatTurn = { role: "user" | "assistant"; text: string };

export type ReportField = { value: number; note: string };
export type ReportResult = {
  fields: Partial<Record<FieldName, ReportField>>;
  not_found: FieldName[];
  needs_manual: FieldName[];
  glucose_comparable: boolean;
  glucose_test_type: string | null;
  glucose_evidence: string | null;
  warnings: string[];
};

// What /narrate and /chat need: the inputs plus the `ai_payload` that /predict returned.
const aiBody = (input: PatientInput, result: PredictResponse, glucoseComparable: boolean | null) => ({
  inputs: input,
  ...result.ai_payload,
  glucose_comparable: glucoseComparable,
});

export const narrate = (input: PatientInput, result: PredictResponse, glucoseComparable: boolean | null = null) =>
  call<Narration>("/narrate", json(aiBody(input, result, glucoseComparable)), 60_000);

export const chat = (
  message: string,
  history: ChatTurn[],
  input?: PatientInput,
  result?: PredictResponse | null,
  glucoseComparable: boolean | null = null,
) =>
  call<ChatReply>(
    "/chat",
    json({
      message,
      history: history.slice(-8),
      result: input && result?.ai_payload ? aiBody(input, result, glucoseComparable) : null,
    }),
    60_000,
  );

export const readReport = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return call<ReportResult>("/report/read", { method: "POST", body: fd }, 90_000);
};
