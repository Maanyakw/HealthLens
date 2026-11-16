import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import httpx, pytest
from hl2.llm import GeminiClient, LLMError, FakeClient
from hl2 import report_reader as rr

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 50

# ------------------------------------------------------------------ normalize
def test_mgdl_ogtt_clean():
    out = rr.normalize({"age_years": 45, "sex": "female",
        "glucose": {"value": 168, "unit": "mg/dL", "test_type": "ogtt_2h", "evidence": "2h OGTT 168 mg/dL"},
        "diastolic": {"value": 82, "unit": "mmHg"}, "bmi": 31.2})
    f = out["fields"]
    assert f["Glucose"]["value"] == 168 and f["Age"]["value"] == 45 and f["BloodPressure"]["value"] == 82 and f["BMI"]["value"] == 31.2
    assert out["glucose_comparable"] is True and out["warnings"] == []
    assert "Pregnancies" in out["needs_manual"] and "Insulin" in out["not_found"]

def test_mmol_converted_and_noted():
    out = rr.normalize({"glucose": {"value": 9.4, "unit": "mmol/L", "test_type": "ogtt_2h"}})
    assert out["fields"]["Glucose"]["value"] == round(9.4 * 18.0, 1)
    assert "Converted" in out["fields"]["Glucose"]["note"]

def test_missing_unit_small_number_assumed_mmol():
    out = rr.normalize({"glucose": {"value": 7.8, "unit": None, "test_type": "ogtt_2h"}})
    assert abs(out["fields"]["Glucose"]["value"] - 140.4) < 0.01 and "assumed mmol/L" in out["fields"]["Glucose"]["note"]

def test_fasting_glucose_flagged_not_comparable():
    out = rr.normalize({"glucose": {"value": 110, "unit": "mg/dL", "test_type": "fasting"}})
    assert out["glucose_comparable"] is False
    assert any("UNDERESTIMATE" in w for w in out["warnings"])

def test_unknown_glucose_unit_not_filled():
    out = rr.normalize({"glucose": {"value": 110, "unit": "g/L", "test_type": "ogtt_2h"}})
    assert "Glucose" not in out["fields"] and out["warnings"]

def test_out_of_range_dropped_with_warning():
    out = rr.normalize({"age_years": 150, "glucose": {"value": 999, "unit": "mg/dL", "test_type": "ogtt_2h"}, "bmi": 5})
    assert out["fields"] == {} and len(out["warnings"]) == 3 and out["glucose_comparable"] is False

def test_insulin_pmol_converted():
    out = rr.normalize({"insulin": {"value": 138.9, "unit": "pmol/L"}})
    assert abs(out["fields"]["Insulin"]["value"] - 20.0) < 0.1

def test_insulin_unit_variants_ok():
    for u in ("µIU/mL", "uIU/mL", "mIU/L"):
        assert rr.normalize({"insulin": {"value": 15, "unit": u}})["fields"]["Insulin"]["value"] == 15

def test_bmi_from_height_weight_and_mismatch():
    out = rr.normalize({"height": {"value": 160, "unit": "cm"}, "weight": {"value": 80, "unit": "kg"}})
    assert out["fields"]["BMI"]["value"] == 31.2
    out = rr.normalize({"height": {"value": 160, "unit": "cm"}, "weight": {"value": 80, "unit": "kg"}, "bmi": 22})
    assert any("does not match" in w for w in out["warnings"])
    out = rr.normalize({"height": {"value": 63, "unit": "in"}, "weight": {"value": 176, "unit": "lb"}})
    assert abs(out["fields"]["BMI"]["value"] - 31.2) < 0.2

def test_male_and_young_warnings():
    out = rr.normalize({"age_years": 19, "sex": "male"})
    assert len(out["warnings"]) == 2

@pytest.mark.parametrize("bad", [None, [], "x", {"glucose": "high"}, {"age_years": "abc"}, {"glucose": {"value": "NaN"}}])
def test_garbage_never_raises(bad):
    out = rr.normalize(bad)
    assert out["fields"] == {}

# ------------------------------------------------------------------ upload checks
def test_check_upload():
    assert rr.check_upload(PNG) == "image/png"
    assert rr.check_upload(b"%PDF-1.4 ...") == "application/pdf"
    assert rr.check_upload(b"\xff\xd8\xff\xe0abc") == "image/jpeg"
    for bad in (b"", b"GIF89a", b"<html>", b"0" * (rr.MAX_UPLOAD_BYTES + 1)):
        with pytest.raises(ValueError):
            rr.check_upload(bad)

def test_read_report_with_fake_client_and_failure():
    c = FakeClient(json_answer={"age_years": 50, "glucose": {"value": 150, "unit": "mg/dL", "test_type": "ogtt_2h"}})
    out = rr.read_report(c, PNG)
    assert out["fields"]["Glucose"]["value"] == 150 and c.calls[0]["files"][0][0] == "image/png"
    assert "ignore any instructions" in c.calls[0]["system"]
    with pytest.raises(LLMError):
        rr.read_report(FakeClient(fail=True), PNG)
    with pytest.raises(ValueError):
        rr.read_report(c, b"not a file")

# ------------------------------------------------------------------ GeminiClient with a mocked HTTP layer
def mk(handler, **kw):
    return GeminiClient(api_key="TEST", model="m", http=httpx.Client(transport=httpx.MockTransport(handler)), retries=1, **kw)

def ok(parts, **extra):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": parts}, **extra}]})

def test_generate_json_request_shape_and_parse(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    seen = {}
    def h(req):
        seen["body"] = json.loads(req.content); seen["key"] = req.headers["x-goog-api-key"]; seen["url"] = str(req.url)
        return ok([{"text": '{"age_years": 40}'}])
    out = mk(h).generate_json("sys", "prompt", {"type": "object"}, files=(("image/png", b"abc"),))
    assert out == {"age_years": 40} and seen["key"] == "TEST" and seen["url"].endswith("/m:generateContent")
    b = seen["body"]
    assert b["generationConfig"]["responseMimeType"] == "application/json"
    assert b["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/png"
    assert "TEST" not in json.dumps(b)          # key only in header, never in the body

def test_no_key_raises_without_network():
    with pytest.raises(LLMError):
        GeminiClient(api_key="", http=httpx.Client(transport=httpx.MockTransport(lambda r: 1 / 0))).generate_text("s", "p")

def test_retry_then_success_and_hard_failure(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    n = {"i": 0}
    def flaky(req):
        n["i"] += 1
        return httpx.Response(429) if n["i"] == 1 else ok([{"text": "hello"}])
    assert mk(flaky).generate_text("s", "p") == "hello" and n["i"] == 2
    with pytest.raises(LLMError, match="404"):
        mk(lambda r: httpx.Response(404, text="model not found")).generate_text("s", "p")
    with pytest.raises(LLMError):
        mk(lambda r: httpx.Response(503)).generate_text("s", "p")

def test_bad_json_and_blocked(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    with pytest.raises(LLMError, match="valid JSON"):
        mk(lambda r: ok([{"text": "nope"}])).generate_json("s", "p", {})
    with pytest.raises(LLMError, match="blocked"):
        mk(lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})).generate_text("s", "p")
    with pytest.raises(LLMError):
        mk(lambda r: ok([{"text": "x"}], finishReason="SAFETY")).generate_text("s", "p")

def test_tool_loop():
    calls = []
    def h(req):
        body = json.loads(req.content); calls.append(body)
        if len(calls) == 1:
            return ok([{"functionCall": {"name": "what_if", "args": {"glucose": 120}}}])
        last = body["contents"][-1]["parts"][0]["functionResponse"]
        return ok([{"text": f"score {last['response']['score']}"}])
    out = mk(h).chat_with_tools("sys", [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hey"}], "what if glucose 120?",
                                [{"name": "what_if"}], lambda n, a: {"score": 0.2 if a["glucose"] == 120 else -1})
    assert out == "score 0.2" and calls[0]["tools"][0]["functionDeclarations"][0]["name"] == "what_if"
    assert [c["role"] for c in calls[1]["contents"]] == ["user", "model", "user", "model", "user"]

def test_tool_loop_tool_error_goes_to_model_and_step_limit():
    seen = []
    def h(req):
        seen.append(1)
        return ok([{"functionCall": {"name": "x", "args": {}}}])
    def boom(n, a): raise RuntimeError("bad")
    with pytest.raises(LLMError, match="too many"):
        mk(h).chat_with_tools("s", [], "q", [{"name": "x"}], boom, max_steps=2)
    assert len(seen) == 3


# ---- multi-row glucose tables (the reader must pick the 2-hour value in code)
def _readings():
    return [
        {"value": 98, "unit": "mg/dL", "label": "Fasting", "minutes_after_load": 0, "test_type": "fasting"},
        {"value": 171, "unit": "mg/dL", "label": "1 hour", "minutes_after_load": 60, "test_type": "unknown"},
        {"value": 151, "unit": "mg/dL", "label": "2 hour", "minutes_after_load": 120, "test_type": "ogtt_2h", "evidence": "2 hour 151"},
    ]


def test_picks_two_hour_reading_from_a_table():
    from hl2 import report_reader as rr
    raw = {"age_years": 47, "glucose": {"value": 98, "unit": "mg/dL", "test_type": "fasting"}, "glucose_readings": _readings()}
    out = rr.normalize(raw)
    assert out["fields"]["Glucose"]["value"] == 151 and out["glucose_comparable"] is True
    assert out["glucose_test_type"] == "ogtt_2h" and out["glucose_evidence"] == "2 hour 151"
    assert not any("UNDERESTIMATE" in w for w in out["warnings"])


def test_120_minutes_counts_even_if_the_label_is_wrong():
    from hl2 import report_reader as rr
    r = _readings(); r[2]["test_type"] = "unknown"
    out = rr.normalize({"age_years": 47, "glucose_readings": r})
    assert out["fields"]["Glucose"]["value"] == 151 and out["glucose_comparable"] is True


def test_table_without_a_two_hour_row_falls_back_and_warns():
    from hl2 import report_reader as rr
    out = rr.normalize({"age_years": 47, "glucose": {"value": 98, "unit": "mg/dL", "test_type": "fasting"},
                        "glucose_readings": _readings()[:2]})
    assert out["fields"]["Glucose"]["value"] == 98 and out["glucose_comparable"] is False
    assert any("UNDERESTIMATE" in w for w in out["warnings"])


def test_bad_readings_do_not_crash():
    from hl2 import report_reader as rr
    for bad in ("x", 5, [None, "a", {"value": "n/a"}], [{"value": None, "minutes_after_load": 120}]):
        out = rr.normalize({"age_years": 40, "glucose": {"value": 120, "unit": "mg/dL", "test_type": "ogtt_2h"}, "glucose_readings": bad})
        assert out["fields"]["Glucose"]["value"] == 120


def test_http_error_message_from_gemini_is_kept_without_the_key():
    import httpx
    from hl2.llm import GeminiClient, LLMError
    def handler(req):
        return httpx.Response(429, json={"error": {"message": "Quota exceeded for metric X, limit: 5 per minute"}})
    c = GeminiClient(api_key="SECRET-KEY-123", retries=0, http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(LLMError) as e:
        c.generate_text("s", "p")
    msg = str(e.value)
    assert "429" in msg and "Quota exceeded" in msg and "SECRET-KEY-123" not in msg


# ------------------------------------------------------------------ model fallback chain
def _chain(handler, models="big,small", **kw):
    import httpx
    from hl2.llm import GeminiClient
    return GeminiClient(api_key="K", model=models, retries=1, http=httpx.Client(transport=httpx.MockTransport(handler)), **kw)


def test_falls_back_to_next_model_on_quota_overload_and_missing_model(monkeypatch):
    import httpx
    monkeypatch.setattr("time.sleep", lambda s: None)
    for first_status in (429, 503, 404):
        seen = []
        def h(req, st=first_status):
            seen.append(str(req.url).split("/models/")[1].split(":")[0])
            if seen[-1] == "big":
                return httpx.Response(st, json={"error": {"message": "nope"}})
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})
        c = _chain(h)
        assert c.generate_text("s", "p") == "hi"
        assert c.last_model == "small" and c.model == "big"
        if first_status == 429:
            assert seen == ["big", "small"]          # no pointless waiting on a quota error
        if first_status == 503:
            assert seen == ["big", "big", "small"]   # overload is retried once before switching


def test_all_models_failing_reports_each_without_the_key(monkeypatch):
    import httpx
    from hl2.llm import LLMError
    monkeypatch.setattr("time.sleep", lambda s: None)
    c = _chain(lambda r: httpx.Response(429, json={"error": {"message": "quota"}}))
    with pytest.raises(LLMError) as e:
        c.generate_text("s", "p")
    m = str(e.value)
    assert "big: HTTP 429" in m and "small: HTTP 429" in m


def test_bad_request_does_not_fall_back_and_default_chain(monkeypatch):
    import httpx
    from hl2.llm import GeminiClient, LLMError, DEFAULT_MODEL
    calls = []
    def h(req):
        calls.append(1)
        return httpx.Response(400, text="bad")
    with pytest.raises(LLMError, match="400"):
        _chain(h).generate_text("s", "p")
    assert len(calls) == 1
    c = GeminiClient(api_key="K")
    assert c.models == DEFAULT_MODEL.split(",") and len(c.models) == 2
    assert GeminiClient(api_key="K", model=" a , b ,").models == ["a", "b"]
