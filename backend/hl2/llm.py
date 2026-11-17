"""
Small LLM client for HealthLens (free tier: Google Gemini API, called over plain REST with httpx).

Settings (environment variables, never hard-code a key):
    GEMINI_API_KEY   your free key from Google AI Studio
    GEMINI_MODEL     one model name or a comma-separated list, tried in order. Default
                     "gemini-2.5-flash,gemini-3.5-flash-lite": the bigger model first, and the next one is used
                     when the first is out of quota (429), overloaded (503) or not found (404).
                     Models on the free tier change over time: if all are "not found", pick current ones in AI Studio.

PRIVACY: on the free tier Google may use what you send to improve its products. HealthLens therefore
only accepts SYNTHETIC sample reports. Do not send real patient data through this client.

Every caller must work when the LLM is unavailable (no key, quota used up, network error):
`LLMError` is raised and callers fall back to deterministic behaviour.
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

DEFAULT_MODEL = "gemini-2.5-flash,gemini-3.5-flash-lite"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class LLMError(RuntimeError):
    """The LLM could not give a usable answer (no key, quota, network, blocked, bad JSON ...)."""


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 timeout: float = 60.0, retries: int = 2, http: Optional[httpx.Client] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        raw = model or os.environ.get("GEMINI_MODEL", "") or DEFAULT_MODEL
        self.models = [m.strip() for m in raw.split(",") if m.strip()] or [DEFAULT_MODEL.split(",")[0]]
        self.model = self.models[0]          # first choice
        self.last_model = None               # model that actually answered the latest call
        self.timeout, self.retries = timeout, retries
        self._http = http or httpx.Client(timeout=timeout)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------ low level
    def _post(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available:
            raise LLMError("GEMINI_API_KEY is not set")
        failures: List[str] = []
        for mi, model in enumerate(self.models):
            has_next = mi < len(self.models) - 1
            url = f"{BASE_URL}/{model}:generateContent"
            last = None
            for attempt in range(self.retries + 1):
                try:
                    r = self._http.post(url, json=body, headers={"x-goog-api-key": self.api_key})
                except httpx.HTTPError as e:  # network / timeout
                    last = f"network error: {e.__class__.__name__}"
                else:
                    if r.status_code == 200:
                        self.last_model = model
                        return r.json()
                    last = f"HTTP {r.status_code}"
                    try:
                        detail = str(r.json().get("error", {}).get("message", ""))[:160]
                    except Exception:
                        detail = ""
                    if detail:
                        last += f": {detail}"
                    if r.status_code == 404 and has_next:
                        break                                  # this model name is not available: try the next one
                    if r.status_code not in (429, 500, 502, 503, 504):
                        raise LLMError(f"Gemini {last}: {r.text[:200]}")
                    if r.status_code == 429 and has_next:
                        break                                  # quota is per model: waiting does not help, switch
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
            failures.append(last or "unknown error")
            if has_next:
                failures[-1] = f"{model}: {failures[-1]}"
        if len(self.models) == 1:
            raise LLMError(f"Gemini failed after retries ({failures[-1]})")
        failures[-1] = f"{self.models[-1]}: {failures[-1]}"
        raise LLMError("Gemini failed on every model (" + "; ".join(failures) + ")")

    @staticmethod
    def _parts(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if data.get("promptFeedback", {}).get("blockReason"):
            raise LLMError("blocked by safety filter")
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError("no candidates returned")
        c = cands[0]
        if c.get("finishReason") in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
            raise LLMError(f"stopped: {c.get('finishReason')}")
        return (c.get("content") or {}).get("parts") or []

    # ------------------------------------------------------------------ public helpers
    def generate_text(self, system: str, prompt: str, temperature: float = 0.2, max_tokens: int = 700) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        text = "".join(p.get("text", "") for p in self._parts(self._post(body))).strip()
        if not text:
            raise LLMError("empty answer")
        return text

    def generate_json(self, system: str, prompt: str, schema: Dict[str, Any],
                      files: Tuple[Tuple[str, bytes], ...] = ()) -> Dict[str, Any]:
        parts: List[Dict[str, Any]] = [{"text": prompt}]
        for mime, data in files:
            parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}})
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": schema},
        }
        text = "".join(p.get("text", "") for p in self._parts(self._post(body))).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"model did not return valid JSON: {e}") from e

    def chat_with_tools(self, system: str, history: List[Dict[str, str]], user_message: str,
                        tool_declarations: List[Dict[str, Any]],
                        run_tool: Callable[[str, Dict[str, Any]], Dict[str, Any]],
                        max_steps: int = 3) -> str:
        """Function-calling loop. `history` is a list of {"role": "user"|"assistant", "text": ...}."""
        contents: List[Dict[str, Any]] = []
        for h in history[-8:]:
            contents.append({"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["text"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})
        for _ in range(max_steps + 1):
            body = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": contents,
                "tools": [{"functionDeclarations": tool_declarations}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
            }
            parts = self._parts(self._post(body))
            calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not calls:
                text = "".join(p.get("text", "") for p in parts).strip()
                if not text:
                    raise LLMError("empty answer")
                return text
            contents.append({"role": "model", "parts": parts})
            responses = []
            for c in calls:
                try:
                    out = run_tool(c["name"], c.get("args") or {})
                except Exception as e:  # tool errors go back to the model, not to the user
                    out = {"error": str(e)[:200]}
                responses.append({"functionResponse": {"name": c["name"], "response": out}})
            contents.append({"role": "user", "parts": responses})
        raise LLMError("too many tool steps")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b,openai/gpt-oss-20b"


class GroqClient:
    """Chat client for Groq (OpenAI-compatible API), used only by the chat assistant.
    Settings: GROQ_API_KEY, GROQ_MODEL (one name or a comma-separated list, tried in order)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 timeout: float = 30.0, http: Optional[httpx.Client] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        raw = model or os.environ.get("GROQ_MODEL", "") or GROQ_DEFAULT_MODEL
        self.models = [m.strip() for m in raw.split(",") if m.strip()] or [GROQ_DEFAULT_MODEL.split(",")[0]]
        self.model = self.models[0]
        self.last_model = None
        self._http = http or httpx.Client(timeout=timeout)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _post(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available:
            raise LLMError("GROQ_API_KEY is not set")
        failures: List[str] = []
        for model in self.models:
            try:
                r = self._http.post(GROQ_URL, json={**body, "model": model},
                                    headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.HTTPError as e:
                failures.append(f"{model}: network error: {e.__class__.__name__}")
                continue
            if r.status_code == 200:
                self.last_model = model
                return r.json()
            try:
                detail = str(r.json().get("error", {}).get("message", ""))[:160]
            except Exception:
                detail = ""
            failures.append(f"{model}: HTTP {r.status_code}" + (f": {detail}" if detail else ""))
            if r.status_code not in (404, 429, 500, 502, 503, 504):
                break                       # a bad request or bad key will fail on every model
        raise LLMError("Groq failed (" + "; ".join(failures) + ")")

    def chat_with_tools(self, system: str, history: List[Dict[str, str]], user_message: str,
                        tool_declarations: List[Dict[str, Any]],
                        run_tool: Callable[[str, Dict[str, Any]], Dict[str, Any]],
                        max_steps: int = 3) -> str:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for h in history[-8:]:
            messages.append({"role": "user" if h["role"] == "user" else "assistant", "content": h["text"]})
        messages.append({"role": "user", "content": user_message})
        tools = [{"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": t.get("parameters", {"type": "object", "properties": {}})}} for t in tool_declarations]
        for _ in range(max_steps + 1):
            body: Dict[str, Any] = {"messages": messages, "temperature": 0.2, "max_tokens": 800}
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            data = self._post(body)
            choices = data.get("choices") or []
            if not choices:
                raise LLMError("no choices returned")
            msg = choices[0].get("message") or {}
            calls = msg.get("tool_calls") or []
            if not calls:
                text = (msg.get("content") or "").strip()
                if not text:
                    raise LLMError("empty answer")
                return text
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for c in calls:
                fn = c.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                    out = run_tool(fn.get("name", ""), args if isinstance(args, dict) else {})
                except Exception as e:      # tool errors go back to the model, not to the user
                    out = {"error": str(e)[:200]}
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": json.dumps(out, default=str)})
        raise LLMError("too many tool steps")

class FakeClient:
    """Test double with the same public methods. Feed it scripted answers."""

    available = True
    model = "fake"

    def __init__(self, json_answer: Optional[Dict] = None, text_answer: Optional[str] = None,
                 tool_script: Optional[List[Tuple[str, Dict]]] = None, final_text: str = "ok", fail: bool = False):
        self.json_answer, self.text_answer = json_answer, text_answer
        self.tool_script, self.final_text, self.fail = tool_script or [], final_text, fail
        self.calls: List[Dict] = []

    def generate_text(self, system, prompt, **kw):
        self.calls.append({"system": system, "prompt": prompt})
        if self.fail:
            raise LLMError("fake failure")
        return self.text_answer or ""

    def generate_json(self, system, prompt, schema, files=()):
        self.calls.append({"system": system, "prompt": prompt, "files": [(m, len(d)) for m, d in files]})
        if self.fail:
            raise LLMError("fake failure")
        return self.json_answer or {}

    def chat_with_tools(self, system, history, user_message, tool_declarations, run_tool, max_steps=3):
        self.calls.append({"system": system, "user": user_message, "tools": [t["name"] for t in tool_declarations]})
        if self.fail:
            raise LLMError("fake failure")
        self.tool_results = [run_tool(name, args) for name, args in self.tool_script]
        return self.final_text
