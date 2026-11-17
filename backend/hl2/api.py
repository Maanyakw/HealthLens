"""
HealthLens API v2 (FastAPI).

Endpoints
    GET  /health              liveness + whether the model/LLM are ready
    GET  /model-info          model card (same field names as before, plus comparison and timings)
    GET  /global-importance   feature importance from the model card
    POST /predict             same fields as before + `ai_payload` (echoed to /narrate and /chat)
    POST /what-if             {patient, changes: Glucose/BMI only} -> before/after (for sliders)
    POST /narrate             written summaries (LLM if available and safe, otherwise template)
    POST /chat                Ask HealthLens
    POST /report/read         upload a SYNTHETIC lab report (PDF/PNG/JPEG) -> values to pre-fill the form

Environment variables
    ALLOWED_ORIGINS          extra comma-separated CORS origins
    ARTIFACT_DIR             default "artifacts"
    GEMINI_API_KEY / GEMINI_MODEL   free Google AI Studio key (optional; without it templates/rules are used)
    HEALTHLENS_USE_LLM       "0" switches the LLM off completely
    LLM_PER_MINUTE           per-IP limit for LLM endpoints (default 8)
    LLM_DAILY_CAP            global daily LLM calls before falling back to templates (default 150)
    TABPFN_TOKEN             needed at start-up to download the TabPFN weights
"""
from __future__ import annotations
from .llm import GeminiClient, GroqClient, LLMError

import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from . import legacy, narrator, report_reader
from .chat import ChatAssistant
from .llm import GeminiClient, LLMError
from .model_service import FEATURES, OPTIONAL, ModelService

FeatureName = Literal["Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"]


# ----------------------------------------------------------------------------- schemas
class PatientIn(BaseModel):
    # Same limits as the previous API version, so the existing form keeps working. 0 / null = not measured.
    Pregnancies: int = Field(ge=0, le=20)
    Glucose: Optional[float] = Field(default=None, ge=0, le=300)
    BloodPressure: Optional[float] = Field(default=None, ge=0, le=200)
    SkinThickness: Optional[float] = Field(default=None, ge=0, le=100)
    Insulin: Optional[float] = Field(default=None, ge=0, le=900)
    BMI: Optional[float] = Field(default=None, ge=0, le=70)
    DiabetesPedigreeFunction: float = Field(ge=0, le=2.5)
    Age: int = Field(ge=18, le=100)

    @field_validator(*OPTIONAL, mode="before")
    @classmethod
    def zero_means_not_measured(cls, v):
        return None if v in (0, 0.0, "", "0") else v

    def as_inputs(self) -> Dict[str, Optional[float]]:
        return {f: getattr(self, f) for f in FEATURES}


class WhatIfIn(BaseModel):
    patient: PatientIn
    changes: Dict[str, float]


class FactorIn(BaseModel):
    feature: FeatureName
    effect: float = Field(ge=-1, le=1)


class OptionIn(BaseModel):
    kind: Optional[str] = Field(default=None, max_length=40)
    Glucose: Optional[float] = None
    BMI: Optional[float] = None
    glucose_change: Optional[float] = None
    bmi_change: Optional[float] = None
    new_score: float = Field(ge=0, le=1)
    realistic: bool = False


class CounterfactualsIn(BaseModel):
    options: List[OptionIn] = Field(default_factory=list, max_length=5)
    already_below_threshold: bool = False


class ResultIn(BaseModel):
    """What /predict returned, echoed back so /narrate and /chat do not need to re-run the model."""
    inputs: PatientIn
    score: float = Field(ge=0, le=1)
    factors: List[FactorIn] = Field(max_length=8)
    counterfactuals: Optional[CounterfactualsIn] = None
    glucose_comparable: Optional[bool] = None


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=1500)


class ChatIn(BaseModel):
    message: str = Field(max_length=500)
    history: List[ChatTurn] = Field(default_factory=list, max_length=8)
    result: Optional[ResultIn] = None


# ----------------------------------------------------------------------------- limits
class Limiter:
    """Tiny in-memory limiter: N calls per minute per client, plus a global daily cap for the LLM."""

    def __init__(self, per_minute: int, daily_cap: int):
        self.per_minute, self.daily_cap = per_minute, daily_cap
        self.hits: Dict[str, deque] = defaultdict(deque)
        self.day, self.day_count = time.strftime("%Y-%m-%d"), 0

    def allow(self, who: str) -> bool:
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day, self.day_count = today, 0
        q = self.hits[who]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute or self.day_count >= self.daily_cap:
            return False
        q.append(now)
        self.day_count += 1
        return True


def _client_id(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else "?"))


# ----------------------------------------------------------------------------- app
def create_app(service: Optional[ModelService] = None, llm: Optional[Any] = None, limiter: Optional[Limiter] = None,
chat_llm: Optional[Any] = None) -> FastAPI:
    state: Dict[str, Any] = {"service": service}
    use_llm = os.environ.get("HEALTHLENS_USE_LLM", "1") != "0"
    client = llm if llm is not None else (GeminiClient() if use_llm else None)

    chat_client = chat_llm if chat_llm is not None else (GroqClient() if (use_llm and llm is None) else None)

    lim = limiter or Limiter(int(os.environ.get("LLM_PER_MINUTE", 8)), int(os.environ.get("LLM_DAILY_CAP", 150)))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["service"] is None:
            state["service"] = ModelService.load()
        yield

    app = FastAPI(title="HealthLens API", version="2.0", lifespan=lifespan)
    origins = ["https://health-lens-theta.vercel.app", "http://localhost:3000"] + [
        o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=r"https://health-lens[a-z0-9-]*\.vercel\.app",
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    def svc() -> ModelService:
        if state["service"] is None:
            raise HTTPException(503, "The model is still loading. Try again in a moment.")
        return state["service"]

    def llm_for(req: Request):
        """The LLM client if it is available AND this caller is within limits; otherwise None (templates are used)."""
        if client is None or not getattr(client, "available", False):
            return None
        return client if lim.allow(_client_id(req)) else None
    def chat_llm_for(req: Request):
        """Groq for the chat if configured, otherwise the main client; None means rule-based answers."""
        c = chat_client if (chat_client is not None and getattr(chat_client, "available", False)) else client
        if c is None or not getattr(c, "available", False):
            return None
        return c if lim.allow(_client_id(req)) else None


    def facts_for(r: ResultIn):
        s = svc()
        cf = r.counterfactuals.model_dump() if r.counterfactuals else None
        if cf:
            for o in cf["options"]:
                o["new_score"] = float(o["new_score"])
        result = {"inputs": r.inputs.as_inputs(), "score": r.score, "threshold": s.threshold,
                  "factors": [f.model_dump() for f in r.factors], "counterfactuals": cf, "glucose_comparable": r.glucose_comparable}
        return narrator.build_facts(result, s.card)

    # ------------------------------------------------------------------ routes
    @app.get("/health")
    def health():
        return {"status": "ok", "model_loaded": state["service"] is not None,
                "llm_available": bool(client is not None and getattr(client, "available", False)),
                "chat_llm_available": bool(chat_client is not None and getattr(chat_client, "available", False))}

    @app.get("/model-info")
    def model_info():
        return legacy.model_info(svc().card)

    @app.get("/global-importance")
    def global_importance():
        return legacy.global_importance(svc().card)

    @app.post("/predict")
    def predict(p: PatientIn, top: int = Query(6, ge=1, le=8), counterfactuals: bool = Query(True)):
        s = svc()
        inputs = p.as_inputs()
        return legacy.predict_response(s.assess(inputs), inputs, s.medians, top, counterfactuals)

    @app.post("/what-if")
    def what_if(w: WhatIfIn):
        bad = [k for k in w.changes if k not in ("Glucose", "BMI")]
        if bad:
            raise HTTPException(422, f"Only Glucose and BMI can be changed, got: {bad}")
        s = svc()
        base = w.patient.as_inputs()
        try:
            checked = PatientIn(**{**{k: (v if v is not None else 0) for k, v in base.items()}, **w.changes})
        except Exception as e:
            raise HTTPException(422, f"Invalid change: {e}")
        before, after = s.score(base), s.score(checked.as_inputs())
        return {"changes": dict(w.changes), "before": before, "after": after, "threshold": s.threshold,
                "flagged_before": before >= s.threshold, "flagged_after": after >= s.threshold}

    @app.post("/narrate")
    def narrate(r: ResultIn, request: Request):
        return narrator.narrate(facts_for(r), llm_for(request))

    @app.post("/chat")
    def chat(c: ChatIn, request: Request):
        s = svc()
        facts = facts_for(c.result) if c.result else None

        def run_what_if(changes: Dict[str, float]) -> Dict[str, Any]:
            base = c.result.inputs.as_inputs()
            new = PatientIn(**{**{k: (v if v is not None else 0) for k, v in base.items()}, **changes}).as_inputs()
            before, after = s.score(base), s.score(new)
            return {"changed": changes, "previous_score_percent": round(before * 100), "new_score_percent": round(after * 100),
                    "threshold_percent": round(s.threshold * 100), "flagged": after >= s.threshold}

        bot = ChatAssistant(s.card, chat_llm_for(request))  
        return bot.reply(c.message, [h.model_dump() for h in c.history], facts, run_what_if if c.result else None)

    @app.post("/report/read")
    async def read_report(request: Request, file: UploadFile = File(...)):
        data = await file.read(report_reader.MAX_UPLOAD_BYTES + 1)
        try:
            report_reader.check_upload(data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        c = llm_for(request)
        if c is None:
            raise HTTPException(503, "Reading reports needs the AI service, which is not available right now (or the limit was reached). Please enter the values by hand.")
        try:
            return report_reader.read_report(c, data)
        except LLMError:
            raise HTTPException(502, "The report could not be read. Please enter the values by hand.")

    return app
