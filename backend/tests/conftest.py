"""Builds small test artifacts (model_card.json + train.csv) from the Pima CSV, using a stand-in model."""
import os, pathlib, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend")); sys.path.insert(0, str(ROOT / "ml" / "src"))
import benchmark as b

CSV = pathlib.Path(os.environ.get("PIMA_CSV", ROOT / "ml" / "data" / "pima-indians-diabetes.csv"))
_tmp = tempfile.mkdtemp(prefix="hl_test_")
if "HL_TEST_ART" not in os.environ:
    res = b.run_benchmark(str(CSV), _tmp, {"LogReg": b.make_logreg()}, n_boot=50, log=lambda s: None)
    os.environ["HL_TEST_ART"] = str(b.export_artifacts(res, "LogReg", _tmp))


import pytest


@pytest.fixture(autouse=True)
def _no_real_ai_service(monkeypatch):
    """Tests must never use a real Gemini key from your terminal (they would make real calls and change the results)."""
    for name in ("GEMINI_API_KEY", "GEMINI_MODEL", "HEALTHLENS_USE_LLM", "LLM_PER_MINUTE", "LLM_DAILY_CAP"):
        monkeypatch.delenv(name, raising=False)
