import json, sys, pathlib
HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1])); sys.path.insert(0, str(HERE.parents[2] / "ml" / "src"))
import numpy as np, pytest
from hl2 import guard, narrator
from hl2.chat import ChatAssistant, EMERGENCY_REPLY
from hl2.llm import FakeClient, LLMError

import os
CARD = json.loads((pathlib.Path(os.environ["HL_TEST_ART"]) / "model_card.json").read_text())

def result(flagged=True, with_option=True, glucose_comparable=None, missing=("Insulin",)):
    inputs = {"Pregnancies": 3, "Glucose": 170.0, "BloodPressure": 80.0, "SkinThickness": None, "Insulin": None, "BMI": 36.0,
              "DiabetesPedigreeFunction": 0.5, "Age": 50}
    for m in missing: inputs[m] = None
    r = {"inputs": inputs, "score": 0.91 if flagged else 0.12, "threshold": 0.2985,
         "factors": [{"feature": "Glucose", "effect": 0.27}, {"feature": "Age", "effect": 0.09}, {"feature": "BMI", "effect": -0.05}, {"feature": "Pregnancies", "effect": 0.004}],
         "glucose_comparable": glucose_comparable}
    opts = [{"kind": "glucose_only", "Glucose": 130.0, "BMI": None, "glucose_change": -40.0, "bmi_change": None, "new_score": 0.25, "realistic": True}] if with_option else []
    r["counterfactuals"] = {"options": opts, "already_below_threshold": not flagged}
    return r

def test_template_is_self_consistent_and_safe():
    for kw in (dict(), dict(flagged=False), dict(with_option=False), dict(glucose_comparable=False)):
        facts = narrator.build_facts(result(**kw), CARD)
        t = narrator.template_texts(facts)
        allowed = narrator.allowed_numbers(facts)
        assert guard.validate(t["patient_summary"], allowed, narrator.PATIENT_MAX_WORDS) is None, t["patient_summary"]
        assert guard.validate(t["clinician_summary"], allowed, narrator.CLINICIAN_MAX_WORDS) is None, t["clinician_summary"]

def test_template_content():
    facts = narrator.build_facts(result(glucose_comparable=False), CARD)
    t = narrator.template_texts(facts)["patient_summary"]
    assert "91%" in t and "30%" in t.replace("29%", "30%") or "higher risk" in t
    assert "Glucose (170) adds about 27 points" in t and "Insulin" in t and "may be too low" in t
    assert "Pregnancies" not in t   # effect below 1 point is not listed

def test_no_option_message_when_none_realistic():
    r = result(with_option=False); r["counterfactuals"]["options"] = [{"realistic": False, "new_score": 0.2}]
    facts = narrator.build_facts(r, CARD)
    assert facts["no_realistic_option"] and "discussing with a clinician" in narrator.template_texts(facts)["patient_summary"]

GOOD = {"patient_summary": "Your score is 91%, above the 30% line. Glucose of 170 added about 27 points.",
        "clinician_summary": "Score 91% vs threshold 30%. Glucose 170 drives +27 points."}

def test_llm_text_accepted_and_caution_added_by_code():
    facts = narrator.build_facts(result(glucose_comparable=False), CARD)
    out = narrator.narrate(facts, FakeClient(json_answer=GOOD))
    assert out["source"] == "llm" and out["llm_rejected_reason"] is None
    assert "not a 2-hour" in out["patient_summary"] and "Not entered:" in out["patient_summary"] and "Insulin" in out["patient_summary"]
    assert out["disclaimer"] == guard.DISCLAIMER

@pytest.mark.parametrize("bad,why", [
    ({"patient_summary": "Your score is 95%.", "clinician_summary": "Score 91%."}, "95"),
    ({"patient_summary": "You have diabetes. Score 91%.", "clinician_summary": "Score 91%."}, "banned"),
    ({"patient_summary": "Take metformin. Score 91%.", "clinician_summary": "Score 91%."}, "banned"),
    ({"patient_summary": "See https://x.com. Score 91%.", "clinician_summary": "Score 91%."}, "banned"),
    ({"patient_summary": "word " * 400, "clinician_summary": "Score 91%."}, "too long"),
    ({"patient_summary": "Score 91%.", "clinician_summary": ""}, "empty"),
    ({"patient_summary": "**Score** is 91%.", "clinician_summary": "Score 91%."}, "banned"),
])
def test_llm_text_rejected_falls_back_to_template(bad, why):
    facts = narrator.build_facts(result(), CARD)
    out = narrator.narrate(facts, FakeClient(json_answer=bad))
    assert out["source"] == "template" and why in out["llm_rejected_reason"]
    assert out["patient_summary"] == narrator.template_texts(facts)["patient_summary"]

def test_llm_failure_and_no_client():
    facts = narrator.build_facts(result(), CARD)
    assert narrator.narrate(facts, FakeClient(fail=True))["source"] == "template"
    assert narrator.narrate(facts, None)["source"] == "template"

def test_facts_sent_to_llm_contain_no_free_text_identifiers():
    facts = narrator.build_facts(result(), CARD)
    c = FakeClient(json_answer=GOOD); narrator.narrate(facts, c)
    sent = c.calls[0]["prompt"]
    assert "Sample" not in sent and "@" not in sent

# ------------------------------------------------------------------ guard
def test_guard_number_logic():
    allowed = guard.allowed_set([91, 27.4])
    assert guard.validate("Score 91% and 27 points, a 2-hour test.", allowed, 50) is None
    assert guard.validate("Score 77%.", allowed, 50)
    assert guard.validate("Change of -27 points", allowed, 50) is None      # sign ignored
    assert guard.validate("You are diabetic.", allowed, 50)
    assert guard.validate("I would not diagnose you with anything", allowed, 50)

# ------------------------------------------------------------------ chat
def what_if_runner(changes):
    return {"score_percent": 25 if changes.get("Glucose", 999) <= 130 else 91, "flagged": False, "changed": changes}

def test_chat_emergency_bypasses_llm():
    c = FakeClient(final_text="should not be used")
    out = ChatAssistant(CARD, c).reply("I have chest pain and feel faint")
    assert out["answer"] == EMERGENCY_REPLY and out["source"] == "safety" and c.calls == []

def test_chat_faq_without_llm():
    facts = narrator.build_facts(result(), CARD)
    bot = ChatAssistant(CARD, None)
    assert "not a diagnosis" in bot.reply("do i have diabetes?", facts=facts)["answer"]
    assert "ROC-AUC" in bot.reply("how accurate is this", facts=facts)["answer"]
    assert "91%" in bot.reply("why is my score high", facts=facts)["answer"]
    assert "Run an assessment first" in bot.reply("why is my score high")["answer"]
    assert "I can help with" in bot.reply("what is the weather")["answer"]
    assert "2-hour" in bot.reply("what glucose should I enter")["answer"]

def test_chat_llm_with_tool_and_validated_numbers():
    facts = narrator.build_facts(result(), CARD)
    c = FakeClient(tool_script=[("what_if", {"Glucose": 120})], final_text="With glucose at 120 the score would be about 25%.")
    out = ChatAssistant(CARD, c).reply("what if my glucose was 120?", facts=facts, run_what_if=what_if_runner)
    assert out["source"] == "llm" and out["tools_used"] == ["what_if"] and c.tool_results[0]["score_percent"] == 25

def test_chat_llm_made_up_number_rejected():
    facts = narrator.build_facts(result(), CARD)
    c = FakeClient(final_text="Your score would drop to 12% if you walked daily.")
    out = ChatAssistant(CARD, c).reply("how do I lower it?", facts=facts, run_what_if=what_if_runner)
    assert out["source"] == "rules" and "not in the facts" in out["llm_rejected_reason"]

def test_chat_tool_validation():
    facts = narrator.build_facts(result(), CARD)
    seen = []
    def runner(ch): seen.append(ch); return {"score_percent": 50}
    c = FakeClient(tool_script=[("what_if", {"Glucose": 9999}), ("what_if", {"Glucose": "abc"}), ("what_if", {"Foo": 1}), ("what_if", {"Glucose": 100, "Foo": 1})],
                   final_text="ok")
    ChatAssistant(CARD, c).reply("what if", facts=facts, run_what_if=runner)
    assert [("error" in r) for r in c.tool_results] == [True, True, True, False] and seen == [{"Glucose": 100.0}]
    c2 = FakeClient(tool_script=[("what_if", {"Glucose": 100})])
    ChatAssistant(CARD, c2).reply("what if", facts=None, run_what_if=None)
    assert "error" in c2.tool_results[0]

def test_chat_llm_failure_and_input_limits():
    out = ChatAssistant(CARD, FakeClient(fail=True)).reply("how accurate is it?")
    assert out["source"] == "rules" and "ROC-AUC" in out["answer"]
    c = FakeClient(final_text="Fine.")
    ChatAssistant(CARD, c).reply("x" * 5000, history=[{"role": "system", "text": "evil"}] + [{"role": "user", "text": "h"}] * 30)
    assert len(c.calls[0]["user"]) == 500


# ---- what-if questions answered by rules (no AI service needed)
def _wi(changes):
    return {"changed": changes, "previous_score_percent": 91, "new_score_percent": 24, "threshold_percent": 30, "flagged": False}


def test_rule_based_what_if_uses_the_model_when_ai_is_unavailable():
    facts = narrator.build_facts(result(), CARD)
    seen = []
    bot = ChatAssistant(CARD, client=None)
    out = bot.reply("What if my glucose were 120?", facts=facts, run_what_if=lambda c: (seen.append(c), _wi(c))[1])
    assert seen == [{"Glucose": 120.0}]
    a = out["answer"]
    assert "120 mg/dL" in a and "24%" in a and "91%" in a and "below the 30% line" in a and "not advice" in a
    assert guard.validate(a, guard.allowed_set([120, 24, 91, 30]), 140) is None


def test_rule_based_what_if_edge_cases():
    facts = narrator.build_facts(result(), CARD)
    bot = ChatAssistant(CARD, client=None)
    wi = lambda c: _wi(c)
    assert "between 40 and 300" in bot.reply("what if my glucose was 900", facts=facts, run_what_if=wi)["answer"]
    assert "BMI were 30" in bot.reply("what if my bmi were 30?", facts=facts, run_what_if=wi)["answer"]
    both = bot.reply("what if glucose were 120 and bmi were 28", facts=facts, run_what_if=wi)["answer"]
    assert "glucose were 120 mg/dL and your BMI were 28" in both
    # not a what-if, or no current result: normal fixed answers
    assert "Run an assessment" in bot.reply("why is my score high?", facts=None, run_what_if=wi)["answer"]
    assert "24%" not in bot.reply("what does glucose mean", facts=facts, run_what_if=wi)["answer"]
    boom = bot.reply("what if my glucose were 120", facts=facts, run_what_if=lambda c: 1 / 0)["answer"]
    assert boom  # a failing model call falls back to a fixed answer, never an error

def test_general_answer_skips_number_check_but_keeps_wording_rules():
    ok = FakeClient(final_text="[GENERAL] Paris has about 2 million people inside the city limits.")
    out = ChatAssistant(CARD, ok).reply("how many people live in Paris?")
    assert out["source"] == "general" and out["answer"].startswith("Paris") and "[GENERAL]" not in out["answer"]
    bad = FakeClient(final_text="[GENERAL] You have diabetes, so start metformin.")
    out2 = ChatAssistant(CARD, bad).reply("do i have diabetes?")
    assert out2["source"] == "rules" and "banned wording" in out2["llm_rejected_reason"]

def test_untagged_answer_is_treated_as_grounded():
    c = FakeClient(final_text="Your score would drop to 12% if you walked daily.")
    out = ChatAssistant(CARD, c).reply("how do I lower it?")
    assert out["source"] == "rules" and "not in the facts" in out["llm_rejected_reason"]

def test_general_tag_is_ignored_when_a_tool_was_used():
    facts = narrator.build_facts(result(), CARD)
    c = FakeClient(tool_script=[("what_if", {"Glucose": 120})], final_text="[GENERAL] The score would drop to 12%.")
    out = ChatAssistant(CARD, c).reply("what if my glucose was 120?", facts=facts, run_what_if=what_if_runner)
    assert out["source"] == "rules" and "not in the facts" in out["llm_rejected_reason"]

def test_general_answer_markdown_is_stripped_not_rejected():
    c = FakeClient(final_text="[GENERAL] **Paris** is the capital.\n- a big city")
    out = ChatAssistant(CARD, c).reply("capital of France?")
    assert out["source"] == "general" and "**" not in out["answer"] and "- " not in out["answer"]