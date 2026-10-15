import type { PatientInput, PredictResponse } from "./api";

// Assessments are kept only in this browser (localStorage). Nothing is stored on a server.
export type SavedAssessment = {
  id: string;
  at: string; // ISO date
  input: PatientInput;
  result: PredictResponse;
};

const KEY = "healthlens-assessments";
const MAX = 20;

export function loadHistory(): SavedAssessment[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function saveAssessment(input: PatientInput, result: PredictResponse): SavedAssessment {
  const entry: SavedAssessment = {
    id: String(Date.now()),
    at: new Date().toISOString(),
    input,
    result,
  };
  try {
    localStorage.setItem(KEY, JSON.stringify([entry, ...loadHistory()].slice(0, MAX)));
  } catch {
    /* storage unavailable: the result is still shown on screen */
  }
  return entry;
}

export function clearHistory() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
