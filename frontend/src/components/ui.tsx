import Link from "next/link";
import type { CSSProperties } from "react";

const PATHS: Record<string, string> = {
  drop: "M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z",
  gauge: "M4 17a8 8 0 1 1 16 0 M12 17l4-5",
  heart: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 20a8 8 0 0 1 16 0",
  file: "M7 3h7l5 5v13H7z M14 3v5h5 M10 13h6 M10 17h6",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M21 21l-5-5",
  trend: "M4 17l6-6 4 4 6-8 M15 7h5v5",
  chat: "M4 5h16v11H9l-5 4V5z",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z M9 12l2 2 4-4",
  upload: "M12 16V4 M7 9l5-5 5 5 M4 20h16",
  grid: "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 11v6 M12 7.5v.01",
  palette:
    "M12 3a9 9 0 1 0 0 18c1.4 0 2-1 1.5-2-.5-1 0-2.5 1.5-2.5H17a4 4 0 0 0 4-4c0-5-4-9.5-9-9.5z M7.5 11v.01 M10 7.5v.01 M14.5 7.5v.01",
  check: "M5 12l5 5 9-10",
  up: "M7 14l5-5 5 5",
};

export function Icon({
  name,
  size = 20,
  className,
}: {
  name: keyof typeof PATHS | string;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d={PATHS[name] ?? PATHS.spark} />
    </svg>
  );
}

export function Logo({ tagline = false }: { tagline?: boolean }) {
  return (
    <Link href="/" className="logo" aria-label="HealthLens home">
      <svg className="logo-mark" viewBox="0 0 40 40" aria-hidden="true">
        <circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" strokeWidth="3" />
        <circle cx="20" cy="20" r="8" fill="currentColor" />
        <circle cx="26.5" cy="13.5" r="2.6" fill="var(--bg)" />
      </svg>
      <span className="logo-text">
        <strong>HealthLens</strong>
        {tagline && <small>AI Health Companion</small>}
      </span>
    </Link>
  );
}

export function Gauge({
  value,
  caption,
  size = 280,
}: {
  value: number;
  caption: string;
  size?: number;
}) {
  const r = 84;
  const c = 2 * Math.PI * r;
  const arc = c * 0.75; // 270 degree sweep
  const len = (arc * Math.min(Math.max(value, 0), 100)) / 100;
  const vars = { "--c": `${c}` } as CSSProperties;

  return (
    <div className="gauge" style={{ width: size, maxWidth: "100%" }}>
      <svg viewBox="0 0 200 200" role="img" aria-label={`${caption}: ${value} percent`} style={vars}>
        <g transform="rotate(135 100 100)">
          <circle className="gauge-track" cx="100" cy="100" r={r} strokeDasharray={`${arc} ${c}`} />
          <circle className="gauge-fill" cx="100" cy="100" r={r} strokeDasharray={`${len} ${c}`} />
        </g>
      </svg>
      <div className="gauge-center">
        <strong>{value}%</strong>
        <span>{caption}</span>
      </div>
    </div>
  );
}