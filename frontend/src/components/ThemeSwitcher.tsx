"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui";

type ThemeId = "clinic" | "midnight" | "sunrise" | "meadow" | "dusk";

const THEME_STORAGE_KEY = "healthlens-theme";

const THEMES: { id: ThemeId; name: string; mode: "Light" | "Dark"; swatch: [string, string, string] }[] = [
  { id: "clinic", name: "Clinic", mode: "Light", swatch: ["#F3F7F8", "#0B7A75", "#3B5BDB"] },
  { id: "midnight", name: "Midnight", mode: "Dark", swatch: ["#0A1220", "#3DD6C6", "#7C8CFF"] },
  { id: "sunrise", name: "Sunrise", mode: "Light", swatch: ["#FFF3EA", "#C2255C", "#E67700"] },
  { id: "meadow", name: "Meadow", mode: "Light", swatch: ["#F0F5EA", "#2F7D3B", "#7A9A12"] },
  { id: "dusk", name: "Dusk", mode: "Dark", swatch: ["#150F26", "#B794F6", "#F687B3"] },
];

export default function ThemeSwitcher() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeId>("clinic");
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const current = document.documentElement.dataset.theme as ThemeId | undefined;
    if (current) setTheme(current);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function choose(id: ThemeId) {
    setTheme(id);
    document.documentElement.dataset.theme = id;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, id);
    } catch {}
    setOpen(false);
  }

  const active = THEMES.find((t) => t.id === theme) ?? THEMES[0];

  return (
    <div className="themer" ref={box}>
      <button
        type="button"
        className="themer-btn"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="palette" size={18} />
        <span className="themer-name">{active.name}</span>
      </button>

      {open && (
        <div className="themer-pop" role="group" aria-label="Choose a theme">
          {THEMES.map((t) => (
            <button
              key={t.id}
              type="button"
              className="themer-opt"
              aria-pressed={t.id === theme}
              onClick={() => choose(t.id)}
            >
              <span className="swatch" style={{ background: t.swatch[0] }}>
                <i style={{ background: t.swatch[1] }} />
                <i style={{ background: t.swatch[2] }} />
              </span>
              <span className="themer-label">
                {t.name}
                <small>{t.mode}</small>
              </span>
              {t.id === theme && <Icon name="check" size={16} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}