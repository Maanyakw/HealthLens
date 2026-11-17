import sys, time, pathlib
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from explain_agnostic import ShapleyExplainer, find_counterfactuals, top_factors

COLS = ["Pregnancies","Glucose","BloodPressure","SkinThickness","Insulin","BMI","DiabetesPedigreeFunction","Age"]
DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "pima-indians-diabetes.csv"

def load():
    df = pd.read_csv(DATA, header=None, names=COLS + ["Outcome"])
    for c in ["Glucose","BloodPressure","SkinThickness","Insulin","BMI"]:
        df[c] = df[c].replace(0, np.nan)
    return df

def fitted():
    df = load()
    Xtr, Xte, ytr, yte = train_test_split(df[COLS].values, df.Outcome.values, test_size=0.2, stratify=df.Outcome, random_state=42)
    m = HistGradientBoostingClassifier(max_depth=3, random_state=0).fit(Xtr, ytr)  # handles NaN, non-linear
    return m, Xtr, Xte

def test_additivity_exact_nonlinear_model_with_nans():
    m, Xtr, Xte = fitted()
    f = lambda X: m.predict_proba(X)[:, 1]
    ex = ShapleyExplainer(f, Xtr[:20], COLS)
    for x in Xte[:15]:                       # includes rows with missing values
        out = ex.explain(x)
        assert out["additivity_error"] < 1e-9
        assert abs(out["base_value"] + sum(out["values"].values()) - out["prediction"]) < 1e-9

def test_unused_feature_gets_zero():
    m, Xtr, Xte = fitted()
    # wrapper that ignores BloodPressure (col 2) entirely
    def f(X):
        X = X.copy(); X[:, 2] = 70.0
        return m.predict_proba(X)[:, 1]
    ex = ShapleyExplainer(f, Xtr[:20], COLS)
    out = ex.explain(Xte[0])
    assert abs(out["values"]["BloodPressure"]) < 1e-12

def test_matches_known_linear_closed_form():
    # f(x) = 0.1*x0 + 0.3*x1 (+0 for others): Shapley_i = w_i * (x_i - mean_background_i)
    rng = np.random.default_rng(0)
    bg = rng.normal(size=(30, 8)); x = rng.normal(size=8)
    w = np.array([0.1, 0.3, 0, 0, 0, 0, 0, 0])
    f = lambda X: X @ w
    out = ShapleyExplainer(f, bg, COLS).explain(x)
    for i, n in enumerate(COLS):
        assert abs(out["values"][n] - w[i] * (x[i] - bg[:, i].mean())) < 1e-9

def test_counterfactuals_are_valid_and_lower_only():
    m, Xtr, Xte = fitted()
    f = lambda X: m.predict_proba(X)[:, 1]
    thr = 0.30
    n_checked = 0
    for x in Xte:
        p = f(x[None, :])[0]
        if p < thr: continue
        res = find_counterfactuals(x, COLS, f, thr)
        assert abs(res["current_score"] - p) < 1e-12
        for o in res["options"]:
            assert o["new_score"] < thr
            # recompute independently
            x2 = x.copy()
            if o["Glucose"] is not None: x2[1] = o["Glucose"]
            if o["BMI"] is not None: x2[5] = o["BMI"]
            assert abs(f(x2[None, :])[0] - o["new_score"]) < 1e-9
            assert (o["glucose_change"] or 0) <= 0 and (o["bmi_change"] or 0) <= 0
            assert o["Glucose"] is None or o["Glucose"] >= 70
            assert o["BMI"] is None or o["BMI"] >= 18.5 - 1e-9
        if not res["options"]:
            assert not res["achievable"] and "lowest_reachable_option" in res
        n_checked += 1
    assert n_checked > 10

def test_already_below_threshold_returns_no_options():
    m, Xtr, Xte = fitted()
    f = lambda X: m.predict_proba(X)[:, 1]
    x = Xte[np.argmin(f(Xte))]
    res = find_counterfactuals(x, COLS, f, 0.99)
    assert res["already_below_threshold"] and res["options"] == []

def test_missing_glucose_is_not_varied():
    m, Xtr, Xte = fitted()
    f = lambda X: m.predict_proba(X)[:, 1]
    x = Xte[0].copy(); x[1] = np.nan
    res = find_counterfactuals(x, COLS, f, 0.01)
    for o in res["options"]:
        assert o["Glucose"] is None

def test_speed_standin():
    m, Xtr, Xte = fitted()
    f = lambda X: m.predict_proba(X)[:, 1]
    ex = ShapleyExplainer(f, Xtr[:20], COLS)
    t = time.time(); ex.explain(Xte[0]); dt = time.time() - t
    print(f"\nShapley (5120 rows) with HistGB stand-in: {dt:.2f}s")
    assert dt < 20

def test_top_factors_sorted():
    ex = {"values": {"a": 0.1, "b": -0.3, "c": 0.05}}
    t = top_factors(ex, 2)
    assert [x["feature"] for x in t] == ["b", "a"] and t[0]["direction"] == "lowers"


def test_realistic_flag():
    from explain_agnostic import _option
    big = _option(np.array([70.0, 30.0]), 0.2, 180.0, 36.0)
    small = _option(np.array([150.0, 33.0]), 0.2, 170.0, 35.0)
    assert big["realistic"] is False and small["realistic"] is True


def test_choose_background_returns_real_rows_and_keeps_blanks():
    from explain_agnostic import choose_background
    rng = np.random.default_rng(1)
    A = rng.normal(size=(200, 8)); A[::7, 4] = np.nan
    bg = choose_background(A, 4)
    assert bg.shape == (4, 8)
    # every background row is an actual row of the data (not an average)
    for r in bg:
        assert any(np.array_equal(r, a, equal_nan=True) for a in A)
    assert np.array_equal(choose_background(A, 4), bg)             # deterministic
    assert choose_background(A[:3], 4).shape == (3, 8)              # k >= n returns all rows


def test_counterfactual_window_is_limited():
    m, Xtr, Xte = fitted()
    calls = []
    f = lambda X: (calls.append(len(X)), m.predict_proba(X)[:, 1])[1]
    x = Xte[0].copy(); x[1] = 190.0; x[5] = 38.0
    res = find_counterfactuals(x, COLS, f, 0.01)
    assert max(calls) <= 14 * 18                                     # window: <=13 glucose x <=17 BMI values (+ current)
    for o in res["options"] + ([res["lowest_reachable_option"]] if "lowest_reachable_option" in res else []):
        assert (o["glucose_change"] or 0) >= -60 - 1e-9 and (o["bmi_change"] or 0) >= -8 - 1e-9
