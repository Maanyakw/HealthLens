"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import "./hl2.css";
import { chat, type ChatTurn, type PatientInput, type PredictResponse } from "@/lib/api";

const CHIPS = ["Why is my score this high?", "What if my glucose were 120?", "How accurate is this?", "What does the glucose value mean here?"];

export default function AskHealthLens({
  input,
  result,
  glucoseComparable = null,
}: {
  input?: PatientInput;
  result?: PredictResponse | null;
  glucoseComparable?: boolean | null;
}) {
  const hasResult = !!result?.ai_payload;
  const [log, setLog] = useState<(ChatTurn & { source?: string })[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [disclaimer, setDisclaimer] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [log, busy]);

  async function send(message: string) {
    const m = message.trim();
    if (!m || busy) return;
    setError(null); setText(""); setBusy(true);
    const history = log.map(({ role, text }) => ({ role, text }));
    setLog((l) => [...l, { role: "user", text: m }]);
    try {
      const r = await chat(m, history, input, result, glucoseComparable);
      setLog((l) => [...l, { role: "assistant", text: r.answer, source: r.source }]);
      setDisclaimer(r.disclaimer);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally { setBusy(false); }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void send(text); };

  return (
    <section className="hl2-card" aria-labelledby="hl2-chat-h">
      <h3 id="hl2-chat-h">Ask HealthLens</h3>
      <p className="hl2-muted">Ask about your result, how HealthLens works, or anything else. HealthLens answers are checked against the model; general answers are not. This is not medical advice.</p>
      <div className="hl2-row" aria-label="Suggested questions">
        {CHIPS.map((c) => <button key={c} type="button" className="hl2-btn" disabled={busy || (!hasResult && c.includes("my"))} onClick={() => send(c)}>{c}</button>)}
      </div>
      <div className="hl2-chat-log" role="log" aria-live="polite">
        {log.map((m, i) => <div key={i} className={`hl2-msg ${m.role}`}>{m.text}{m.source === "llm" && <div className="hl2-muted">AI-written, numbers checked</div>}{m.source === "general" && <div className="hl2-muted">General AI answer, not checked by HealthLens</div>}</div>)}
        {busy && <div className="hl2-msg assistant" role="status">Thinking…</div>}
        <div ref={end} />
      </div>
      {error && <div className="hl2-error" role="alert">{error}</div>}
      <form className="hl2-row" onSubmit={submit}>
        <input className="hl2-input" value={text} maxLength={500} onChange={(e) => setText(e.target.value)} placeholder="Ask about your result or anything else…" />
        <button type="submit" className="hl2-btn primary" disabled={busy || !text.trim()}>Send</button>
      </form>
      {disclaimer && <p className="hl2-muted">{disclaimer}</p>}
    </section>
  );
}
