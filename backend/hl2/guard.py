"""
Guardrails for text written by an LLM.

Rule: the LLM may only REPHRASE facts we computed. So
  * every number in its text must be one of the numbers we gave it, and
  * it must not diagnose, prescribe, or give medication advice, and
  * it must stay short and plain (no links, no markdown).
Anything that fails is thrown away and the deterministic template is shown instead.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

DISCLAIMER = ("HealthLens is a screening aid, not a diagnosis. Please talk to a doctor or other clinician "
              "about your result and any symptoms.")

_NUM_RE = re.compile(r"(?<![\w.])[-+−]?\d+(?:\.\d+)?")
_BANNED = [
    r"\byou (?:have|has|got|don'?t have|do not have|definitely have|probably have)\s+(?:type\s*[12]\s+)?diabetes\b",
    r"\byou (?:are|were) diabetic\b",
    r"\bdiagnos(?:e|ed|es|ing)\s+(?:you|with)\b",
    r"\b(?:start|stop|skip|increase|decrease|change)\s+(?:taking|your)\s+(?:medication|medicine|insulin|metformin|pills?)\b",
    r"\b(?:dose|dosage|prescri(?:be|bed|ption)|metformin)\b",
    r"\b(?:cure|guarantee[sd]?)\b",
    r"https?://|www\.",
    r"[*#`_]{2,}|^\s*[-*]\s",           # markdown
]
_BANNED_RE = [re.compile(p, re.I | re.M) for p in _BANNED]


def numbers_in(text: str) -> List[float]:
    out = []
    for m in _NUM_RE.findall(text):
        try:
            out.append(float(m.replace("−", "-")))
        except ValueError:
            pass
    return out


def allowed_set(values: Iterable[Optional[float]]) -> Set[float]:
    s: Set[float] = set()
    for v in values:
        if v is None:
            continue
        s.add(float(v))
        s.add(float(round(v)))
        s.add(round(float(v), 1))
        s.add(abs(float(round(v))))
        s.add(abs(round(float(v), 1)))
    return s


def validate(text: str, allowed: Set[float], max_words: int, tolerance: float = 0.51, check_numbers: bool = True) -> Optional[str]:
    """Return None if the text is fine, otherwise a short reason."""
    if not text or not text.strip():
        return "empty"
    if len(text.split()) > max_words:
        return f"too long (> {max_words} words)"
    for rx in _BANNED_RE:
        if rx.search(text):
            return f"banned wording: {rx.pattern[:40]}"
    if not check_numbers:
        return None
    for n in numbers_in(text):
        if abs(n) <= 3 and float(n).is_integer():      # "2-hour", "1 in 3", list counts
            continue
        if not any(abs(abs(n) - abs(a)) <= tolerance for a in allowed):
            return f"number {n:g} is not in the facts"
    return None