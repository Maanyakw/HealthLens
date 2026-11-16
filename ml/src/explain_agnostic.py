"""
Model-agnostic explanations for HealthLens (works with TabPFN, XGBoost, LogReg ...).

Why this file exists
--------------------
LinearExplainer is only exact for linear models. With TabPFN we need something that
only needs a `predict_proba` function. With 8 features there are just 2^8 = 256
feature subsets, so we can compute *exact* (interventional) Shapley values by
brute force instead of using a sampling approximation:

    value(S) = average prediction when the features in S take the patient's values
               and the other features are taken from a small background sample.

Additivity always holds:  sum(shap values) == prediction(patient) - average background prediction.
The cost is one batched predict call of 256 x len(background) rows per patient.

Counterfactuals
---------------
`find_counterfactuals` is a simple, deterministic grid search over Glucose and BMI
(the only two features a person can plausibly change). It is NOT the DiCE library.
It needs ONE batched predict call, which is what makes it usable with a slow model.
"""
from __future__ import annotations

from itertools import combinations
from math import factorial
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

PredictFn = Callable[[np.ndarray], np.ndarray]  # (n, d) float array -> (n,) P(diabetes)


# --------------------------------------------------------------------------------------
# Shapley values
# --------------------------------------------------------------------------------------
class ShapleyExplainer:
    def __init__(
        self,
        predict_fn: PredictFn,
        background: np.ndarray,
        feature_names: Sequence[str],
        chunk_rows: int = 4096,
    ):
        background = np.asarray(background, dtype=float)
        if background.ndim != 2 or background.shape[1] != len(feature_names):
            raise ValueError("background must be (k, n_features)")
        self.predict_fn = predict_fn
        self.background = background
        self.names = list(feature_names)
        self.d = len(self.names)
        self.chunk_rows = chunk_rows
        if self.d > 12:
            raise ValueError("Exact enumeration is only meant for <= 12 features")

        # all subsets as a boolean matrix (2^d, d); row index == bitmask
        masks = ((np.arange(2**self.d)[:, None] >> np.arange(self.d)) & 1).astype(bool)
        self._masks = masks
        self._sizes = masks.sum(axis=1)

    def _predict_chunked(self, X: np.ndarray) -> np.ndarray:
        out = []
        for i in range(0, len(X), self.chunk_rows):
            out.append(np.asarray(self.predict_fn(X[i : i + self.chunk_rows]), dtype=float))
        return np.concatenate(out)

    def explain(self, x: Sequence[float]) -> Dict:
        """Return exact Shapley values (in probability units) for one patient."""
        x = np.asarray(x, dtype=float)
        if x.shape != (self.d,):
            raise ValueError(f"x must have {self.d} values")
        k = len(self.background)
        n_sub = len(self._masks)

        # Build (n_sub * k, d): for each subset take x where mask is True, else background row.
        X = np.where(
            self._masks[:, None, :],  # (n_sub, 1, d)
            x[None, None, :],
            self.background[None, :, :],  # (1, k, d)
        ).reshape(n_sub * k, self.d)

        preds = self._predict_chunked(X).reshape(n_sub, k)
        v = preds.mean(axis=1)  # value of every subset

        base_value = float(v[0])  # empty subset = average background prediction
        full_value = float(v[-1])  # all features = the patient's own prediction

        d = self.d
        phi = np.zeros(d)
        for i in range(d):
            bit = 1 << i
            for mask_idx in range(n_sub):
                if mask_idx & bit:
                    continue  # subset must NOT contain i
                s = int(self._sizes[mask_idx])
                w = factorial(s) * factorial(d - s - 1) / factorial(d)
                phi[i] += w * (v[mask_idx | bit] - v[mask_idx])

        return {
            "unit": "probability",
            "base_value": base_value,
            "prediction": full_value,
            "values": {n: float(p) for n, p in zip(self.names, phi)},
            "additivity_error": float(abs(base_value + phi.sum() - full_value)),
        }


def top_factors(explanation: Dict, k: int = 6) -> List[Dict]:
    """Sorted list of {feature, effect} by absolute effect. `effect` is in probability points (0-1)."""
    items = sorted(explanation["values"].items(), key=lambda kv: abs(kv[1]), reverse=True)
    return [
        {"feature": f, "effect": e, "direction": "raises" if e > 0 else "lowers"}
        for f, e in items[:k]
    ]


def choose_background(X, k: int, random_state: int = 0) -> np.ndarray:
    """
    k REAL rows that summarise X: the row nearest to each k-means centre.
    A small background (k = 4) is used because every extra row costs 256 model calls per patient;
    choosing representative rows keeps the baseline close to the population average.
    Missing values are only filled for the clustering; the returned rows keep their blanks.
    """
    from sklearn.cluster import KMeans

    A = np.asarray(X, dtype=float)
    if k >= len(A):
        return A.copy()
    B = np.where(np.isnan(A), np.nanmedian(A, axis=0), A)
    sd = B.std(axis=0); sd[sd == 0] = 1.0
    Z = (B - B.mean(axis=0)) / sd
    centres = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(Z).cluster_centers_
    idx: List[int] = []
    for c in centres:
        for j in np.argsort(((Z - c) ** 2).sum(axis=1)):
            if int(j) not in idx:
                idx.append(int(j)); break
    return A[idx]


# --------------------------------------------------------------------------------------
# Counterfactuals (grid search over Glucose and BMI)
# --------------------------------------------------------------------------------------
def find_counterfactuals(
    x: Sequence[float],
    feature_names: Sequence[str],
    predict_fn: PredictFn,
    threshold: float,
    glucose_floor: float = 70.0,
    bmi_floor: float = 18.5,
    glucose_step: float = 5.0,
    bmi_step: float = 0.5,
    max_results: int = 3,
    max_glucose_drop: float = 60.0,
    max_bmi_drop: float = 8.0,
) -> Dict:
    """
    Smallest changes in Glucose and/or BMI that bring the score below `threshold`.

    Only LOWERING is considered, and never below `glucose_floor` / `bmi_floor`
    (we do not want to suggest unhealthy low values). Features that are missing (NaN)
    are left unchanged and are not varied.

    The search window is limited to `max_glucose_drop` mg/dL and `max_bmi_drop` BMI points below the
    current values (at most about 13 x 17 = 221 model rows, one batched call). Options beyond the
    40 mg/dL / 5 BMI-point limits below are still marked `realistic: False`.
    """
    names = list(feature_names)
    x = np.asarray(x, dtype=float)
    gi, bi = names.index("Glucose"), names.index("BMI")
    g0, b0 = x[gi], x[bi]

    g_lo = max(glucose_floor, g0 - max_glucose_drop) if not np.isnan(g0) else 0.0
    b_lo = max(bmi_floor, b0 - max_bmi_drop) if not np.isnan(b0) else 0.0
    g_vals = [g0] if np.isnan(g0) else sorted({g0, *np.arange(g_lo, g0, glucose_step)} if g0 > g_lo else {g0})
    b_vals = [b0] if np.isnan(b0) else sorted({b0, *np.arange(b_lo, b0, bmi_step)} if b0 > b_lo else {b0})

    grid = np.array([[g, b] for g in g_vals for b in b_vals], dtype=float)
    X = np.tile(x, (len(grid), 1))
    X[:, gi] = grid[:, 0]
    X[:, bi] = grid[:, 1]
    p = np.asarray(predict_fn(X), dtype=float)  # ONE batched call

    current_p = float(np.asarray(predict_fn(x[None, :]), dtype=float)[0])

    # change "cost": how far each value moves, relative to a plausible range
    g_range, b_range = 100.0, 15.0
    dg = np.zeros(len(grid)) if np.isnan(g0) else g0 - grid[:, 0]
    db = np.zeros(len(grid)) if np.isnan(b0) else b0 - grid[:, 1]
    cost = dg / g_range + db / b_range
    g_unchanged = (dg == 0)
    b_unchanged = (db == 0)

    ok = np.where(p < threshold)[0]
    result = {
        "unit": "probability",
        "current_score": current_p,
        "threshold": threshold,
        "already_below_threshold": current_p < threshold,
        "options": [],
        "achievable": bool(len(ok)) and current_p >= threshold,
        "lowest_reachable_score": float(p.min()),
        "method": "grid search over Glucose and BMI (lowering only, limited window), one batched model call",
    }
    if current_p < threshold:
        return result

    if len(ok) == 0:
        best = int(np.argmin(p))
        result["lowest_reachable_option"] = _option(grid[best], p[best], g0, b0)
        return result

    # three diverse options: glucose only, BMI only, cheapest mix
    picks: Dict[str, int] = {}
    g_only = ok[b_unchanged[ok]]  # only glucose moved
    if len(g_only):
        picks["glucose_only"] = int(g_only[np.argmin(cost[g_only])])
    b_only = ok[g_unchanged[ok]]  # only BMI moved
    if len(b_only):
        picks["bmi_only"] = int(b_only[np.argmin(cost[b_only])])
    picks["smallest_combined_change"] = int(ok[np.argmin(cost[ok])])

    seen = set()
    for label, idx in picks.items():
        key = (round(grid[idx, 0], 3), round(grid[idx, 1], 3))
        if key in seen:
            continue
        seen.add(key)
        opt = _option(grid[idx], p[idx], g0, b0)
        opt["kind"] = label
        result["options"].append(opt)
        if len(result["options"]) >= max_results:
            break
    return result


# Design choice (not a clinical rule): changes bigger than this are flagged as "not realistic",
# so the narrator never presents them as an easy goal.
MAX_REALISTIC_GLUCOSE_DROP = 40.0  # mg/dL
MAX_REALISTIC_BMI_DROP = 5.0       # BMI points


def _option(row: np.ndarray, score: float, g0: float, b0: float) -> Dict:
    dg = 0.0 if np.isnan(g0) or np.isnan(row[0]) else g0 - row[0]
    db = 0.0 if np.isnan(b0) or np.isnan(row[1]) else b0 - row[1]
    return {
        "realistic": bool(dg <= MAX_REALISTIC_GLUCOSE_DROP and db <= MAX_REALISTIC_BMI_DROP),
        "Glucose": None if np.isnan(row[0]) else float(row[0]),
        "BMI": None if np.isnan(row[1]) else float(round(row[1], 1)),
        "glucose_change": None if np.isnan(g0) else float(round(row[0] - g0, 1)),
        "bmi_change": None if np.isnan(b0) else float(round(row[1] - b0, 1)),
        "new_score": float(score),
    }
