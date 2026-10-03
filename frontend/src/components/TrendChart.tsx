"use client";

import { useId, useState } from "react";

type Series = Record<string, { label: string; unit: string; values: number[] }>;

const W = 640;
const H = 240;
const PAD = { l: 44, r: 20, t: 20, b: 32 };

function smoothPath(pts: { x: number; y: number }[]) {
  if (pts.length < 2) return "";
  let d = `M${pts[0].x},${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2.x},${p2.y}`;
  }
  return d;
}

export default function TrendChart({ months, series: all }: { months: string[]; series: Series }) {
  const keys = Object.keys(all);
  const [key, setKey] = useState<string>(keys[0]);
  const [active, setActive] = useState(months.length - 1);
  const gid = useId().replace(/:/g, "");
  const series = all[key];
  const vals = series.values;

  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const lo = min - span * 0.35;
  const hi = max + span * 0.35;

  const x = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / (vals.length - 1);
  const y = (v: number) => PAD.t + ((hi - v) / (hi - lo)) * (H - PAD.t - PAD.b);
  const pts = vals.map((v, i) => ({ x: x(i), y: y(v) }));
  const line = smoothPath(pts);
  const area = `${line} L${x(vals.length - 1)},${H - PAD.b} L${x(0)},${H - PAD.b} Z`;
  const ticks = [lo, (lo + hi) / 2, hi];
  const fmt = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));
  const tickFmt = (v: number) => (hi - lo >= 8 ? String(Math.round(v)) : v.toFixed(1));
  const current = vals[active];

  return (
    <div className="trend">
      <div className="trend-head">
        <div className="tabs" role="tablist" aria-label="Health measurement">
          {keys.map((k) => (
            <button
              key={k}
              role="tab"
              type="button"
              aria-selected={k === key}
              className="tab"
              onClick={() => setKey(k)}
            >
              {all[k].label}
            </button>
          ))}
        </div>
        <p className="trend-read" aria-live="polite">
          <strong>
            {fmt(current)}
            <small> {series.unit}</small>
          </strong>
          <span>{months[active]}</span>
        </p>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="trend-svg" role="group" aria-label={`${series.label}, last 6 months`}>
        <defs>
          <linearGradient id={`g${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="var(--accent)" stopOpacity="0.28" />
            <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} className="grid-line" />
            <text x={PAD.l - 10} y={y(t) + 4} textAnchor="end" className="axis">
              {tickFmt(t)}
            </text>
          </g>
        ))}

        <path d={area} fill={`url(#g${gid})`} />
        <path d={line} className="trend-line" />

        <line x1={x(active)} x2={x(active)} y1={PAD.t} y2={H - PAD.b} className="cursor-line" />

        {pts.map((p, i) => (
          <g
            key={i}
            tabIndex={0}
            role="button"
            aria-label={`${months[i]}: ${fmt(vals[i])} ${series.unit}`}
            onPointerEnter={() => setActive(i)}
            onFocus={() => setActive(i)}
            onClick={() => setActive(i)}
            className="trend-pt"
          >
            <rect x={p.x - 28} y={0} width={56} height={H} fill="transparent" />
            <circle cx={p.x} cy={p.y} r={i === active ? 7 : 4.5} className={i === active ? "dot dot-on" : "dot"} />
            <text x={p.x} y={H - 8} textAnchor="middle" className={i === active ? "axis axis-on" : "axis"}>
              {months[i]}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}