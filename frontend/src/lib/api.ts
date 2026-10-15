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

export async function predict(patient: PatientInput): Promise<PredictResponse> {
  const res = await fetch(`${API_URL}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patient),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}
