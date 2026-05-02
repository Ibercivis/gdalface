/* ──────────────────────────────────────────────────────────────
   Lost at Night — shared primitives
   ────────────────────────────────────────────────────────────── */

const { useState, useEffect, useRef, useCallback, useMemo } = React;

/* ----- Icons (small, hairline) -------------------------------- */
const Icon = ({ name, size = 16, stroke = 1.6 }) => {
  const p = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: stroke,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  };
  const paths = {
    moon: <><path d="M19 14.79A8 8 0 1 1 9.21 5a7 7 0 0 0 9.79 9.79z" {...p} /></>,
    crown: <><path d="M3 7l4 4 5-7 5 7 4-4-2 12H5z" {...p} /><path d="M5 19h14" {...p} /></>,
    trophy: <><path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4z" {...p} /><path d="M17 4h3v2a3 3 0 0 1-3 3M7 4H4v2a3 3 0 0 0 3 3" {...p} /></>,
    chevronRight: <><path d="M9 6l6 6-6 6" {...p} /></>,
    chevronLeft:  <><path d="M15 6l-6 6 6 6" {...p} /></>,
    chevronDown:  <><path d="M6 9l6 6 6-6" {...p} /></>,
    plus: <><path d="M12 5v14M5 12h14" {...p} /></>,
    minus: <><path d="M5 12h14" {...p} /></>,
    info: <><circle cx="12" cy="12" r="9" {...p} /><path d="M12 8h.01M11 12h1v5h1" {...p} /></>,
    help: <><circle cx="12" cy="12" r="9" {...p} /><path d="M9.5 9.5a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 3.5M12 17h.01" {...p} /></>,
    sliders: <><path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h14M18 18h2" {...p} /><circle cx="16" cy="6" r="2" {...p} /><circle cx="8" cy="12" r="2" {...p} /><circle cx="16" cy="18" r="2" {...p} /></>,
    layers: <><path d="M12 3l9 5-9 5-9-5 9-5z" {...p} /><path d="M3 13l9 5 9-5M3 18l9 5 9-5" {...p} /></>,
    reset: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" {...p} /><path d="M3 3v5h5" {...p} /></>,
    target: <><circle cx="12" cy="12" r="9" {...p} /><circle cx="12" cy="12" r="4" {...p} /><path d="M12 3v3M12 18v3M3 12h3M18 12h3" {...p} /></>,
    expand: <><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" {...p} /></>,
    skip: <><path d="M5 4l10 8-10 8V4zM19 5v14" {...p} /></>,
    check: <><path d="M5 12l5 5L20 7" {...p} /></>,
    play: <><path d="M6 4l14 8-14 8V4z" {...p} /></>,
    spark: <><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" {...p} /></>,
    camera: <><path d="M3 8a2 2 0 0 1 2-2h2l2-2h6l2 2h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8z" {...p} /><circle cx="12" cy="13" r="4" {...p} /></>,
    map: <><path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2z" {...p} /><path d="M9 4v16M15 6v16" {...p} /></>,
    sat: <><path d="M5 14l-2 2 4 4 2-2M16 5l-2 2 4 4 2-2" {...p} /><path d="M9 11l4 4M14 8l-4 4" {...p} /><circle cx="18" cy="18" r="2" {...p} /></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
};

/* ----- Pill / badge ------------------------------------------- */
const Pill = ({ tone = "neutral", icon, children, mono }) => {
  const tones = {
    neutral: { bg: "var(--bg-3)", fg: "var(--ink-1)", bd: "var(--line)" },
    accent:  { bg: "var(--accent)", fg: "var(--accent-ink)", bd: "transparent" },
    ghost:   { bg: "transparent",   fg: "var(--ink-2)", bd: "var(--line)" },
    live:    { bg: "oklch(0.32 0.12 150 / 0.35)", fg: "oklch(0.92 0.16 150)", bd: "oklch(0.5 0.16 150 / 0.5)" },
  };
  const t = tones[tone];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "4px 9px", height: 26,
      fontSize: 12, fontWeight: 500,
      borderRadius: 999, lineHeight: 1,
      background: t.bg, color: t.fg, border: `1px solid ${t.bd}`,
      fontFamily: mono ? '"JetBrains Mono", monospace' : undefined,
      whiteSpace: "nowrap",
    }}>
      {icon && <Icon name={icon} size={12} />}
      {children}
    </span>
  );
};

/* ----- Slider (re-usable, dark) ------------------------------- */
const Slider = ({ label, value, min = -100, max = 100, step = 1, onChange, unit = "" }) => {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <label style={{ display: "grid", gridTemplateColumns: "78px 1fr 36px", alignItems: "center", gap: 10, height: 22 }}>
      <span style={{ color: "var(--ink-2)", fontSize: 12 }}>{label}</span>
      <span style={{ position: "relative", height: 22, display: "flex", alignItems: "center" }}>
        <span style={{
          position: "absolute", left: 0, right: 0, top: "50%", transform: "translateY(-50%)",
          height: 3, borderRadius: 2,
          background: `linear-gradient(to right,
            var(--accent) 0%, var(--accent) ${pct}%,
            var(--bg-4) ${pct}%, var(--bg-4) 100%)`,
        }} />
        <input
          type="range"
          value={value} min={min} max={max} step={step}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          style={{
            position: "relative", width: "100%", height: 22, margin: 0,
            background: "transparent", appearance: "none", WebkitAppearance: "none",
          }}
          className="laon-slider"
        />
      </span>
      <span className="mono" style={{ color: "var(--ink-1)", fontSize: 12, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {value > 0 ? "+" : ""}{value}{unit}
      </span>
    </label>
  );
};

/* slider thumb styling — injected once */
if (typeof document !== "undefined" && !document.getElementById("laon-slider-css")) {
  const s = document.createElement("style");
  s.id = "laon-slider-css";
  s.textContent = `
    .laon-slider::-webkit-slider-thumb {
      -webkit-appearance: none; appearance: none;
      width: 14px; height: 14px; border-radius: 50%;
      background: var(--ink-0);
      border: 0;
      box-shadow: 0 0 0 1px oklch(0 0 0 / 0.3), 0 1px 3px oklch(0 0 0 / 0.4);
      cursor: pointer;
    }
    .laon-slider::-moz-range-thumb {
      width: 14px; height: 14px; border-radius: 50%;
      background: var(--ink-0); border: 0;
      box-shadow: 0 0 0 1px oklch(0 0 0 / 0.3), 0 1px 3px oklch(0 0 0 / 0.4);
      cursor: pointer;
    }
    .laon-slider { cursor: pointer; }
    .laon-slider:focus { outline: none; }
  `;
  document.head.appendChild(s);
}

/* ----- Segmented control -------------------------------------- */
const Segmented = ({ options, value, onChange, size = "md" }) => {
  const h = size === "sm" ? 26 : 30;
  return (
    <div style={{
      display: "inline-flex", padding: 2, gap: 2,
      background: "var(--bg-1)", border: "1px solid var(--line)",
      borderRadius: 8, height: h,
    }}>
      {options.map(opt => {
        const sel = opt.value === value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            style={{
              padding: "0 10px", height: h - 6,
              fontSize: size === "sm" ? 11 : 12, fontWeight: 500,
              color: sel ? "var(--ink-0)" : "var(--ink-2)",
              background: sel ? "var(--bg-3)" : "transparent",
              borderRadius: 6,
              transition: "background 120ms, color 120ms",
              display: "inline-flex", alignItems: "center", gap: 5,
            }}
          >
            {opt.icon && <Icon name={opt.icon} size={11} />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
};

/* ----- Floating card (panels over the canvas) ---------------- */
const FloatCard = ({ title, icon, right, children, style, padding = 12 }) => (
  <div style={{
    background: "oklch(0.18 0.05 290 / 0.86)",
    backdropFilter: "blur(14px) saturate(140%)",
    WebkitBackdropFilter: "blur(14px) saturate(140%)",
    border: "1px solid var(--line)",
    borderRadius: 12,
    boxShadow: "var(--shadow)",
    color: "var(--ink-1)",
    minWidth: 240,
    ...style,
  }}>
    {(title || right) && (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "9px 12px",
        borderBottom: "1px solid var(--line-soft)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--ink-1)", fontSize: 12, fontWeight: 600, letterSpacing: 0.2 }}>
          {icon && <Icon name={icon} size={13} />}
          {title}
        </div>
        {right}
      </div>
    )}
    <div style={{ padding }}>
      {children}
    </div>
  </div>
);

/* ----- Buttons ------------------------------------------------ */
const Btn = ({ kind = "ghost", size = "md", icon, iconRight, children, onClick, disabled, title }) => {
  const sizes = {
    sm: { h: 28, px: 10, fs: 12 },
    md: { h: 36, px: 14, fs: 13 },
    lg: { h: 44, px: 18, fs: 14 },
  }[size];
  const styles = {
    primary: {
      background: "var(--accent)", color: "var(--accent-ink)", border: "1px solid transparent",
      fontWeight: 600,
    },
    secondary: {
      background: "var(--bg-3)", color: "var(--ink-0)", border: "1px solid var(--line)",
      fontWeight: 500,
    },
    ghost: {
      background: "transparent", color: "var(--ink-1)", border: "1px solid var(--line)",
      fontWeight: 500,
    },
    danger: {
      background: "transparent", color: "var(--ink-2)", border: "1px solid var(--line)",
      fontWeight: 500,
    },
  }[kind];
  return (
    <button
      onClick={onClick} disabled={disabled} title={title}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 7,
        height: sizes.h, padding: `0 ${sizes.px}px`, fontSize: sizes.fs,
        borderRadius: 8, transition: "transform 80ms ease, filter 120ms",
        opacity: disabled ? 0.4 : 1, cursor: disabled ? "not-allowed" : "pointer",
        ...styles,
      }}
      onMouseDown={(e) => !disabled && (e.currentTarget.style.transform = "translateY(1px)")}
      onMouseUp={(e)   => (e.currentTarget.style.transform = "translateY(0)")}
      onMouseLeave={(e)=> (e.currentTarget.style.transform = "translateY(0)")}
    >
      {icon && <Icon name={icon} size={size === "lg" ? 16 : 14} />}
      {children}
      {iconRight && <Icon name={iconRight} size={size === "lg" ? 16 : 14} />}
    </button>
  );
};

/* ----- Progress / XP bar -------------------------------------- */
const ProgressBar = ({ value, max, height = 6, showLabel = false, label }) => {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 140 }}>
      {showLabel && (
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-2)", whiteSpace: "nowrap" }}>
          {label}
        </span>
      )}
      <div style={{
        flex: 1, height, borderRadius: height,
        background: "var(--bg-1)", border: "1px solid var(--line-soft)",
        overflow: "hidden", position: "relative",
      }}>
        <div style={{
          position: "absolute", inset: 0, right: `${100 - pct}%`,
          background: "linear-gradient(90deg, oklch(0.7 0.15 290), oklch(0.85 0.16 280))",
          borderRadius: height,
        }} />
      </div>
    </div>
  );
};

/* expose */
Object.assign(window, {
  Icon, Pill, Slider, Segmented, FloatCard, Btn, ProgressBar,
});
