/* ──────────────────────────────────────────────────────────────
   Lost at Night — Participation screen (rebuild)
   ────────────────────────────────────────────────────────────── */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density": "comfortable",
  "showGamification": true,
  "issSize": 1,
  "highContrast": false,
  "showLayerLegend": true
}/*EDITMODE-END*/;

/* ----- Top bar ------------------------------------------------ */
function TopBar({ tweaks }) {
  const compact = tweaks.density === "compact";
  return (
    <header style={{
      gridArea: "top",
      display: "flex", alignItems: "center",
      gap: 14,
      padding: compact ? "0 14px" : "0 18px",
      borderBottom: "1px solid var(--line)",
      background: "linear-gradient(180deg, oklch(0.22 0.06 290), oklch(0.18 0.05 290))",
      height: "var(--topbar-h)",
    }}>
      {/* Mission status */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Pill tone="ghost" icon="moon">Test mission</Pill>
        <Pill tone="live" icon="spark">ACTIVE</Pill>
      </div>

      <div style={{ flex: 1 }} />

      {/* Gamification cluster — discreet */}
      {tweaks.showGamification && (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="trophy" size={14} stroke={1.6} />
            <span style={{ fontSize: 12, color: "var(--ink-2)" }}>Rank</span>
            <span className="mono" style={{ fontSize: 13, color: "var(--ink-0)", fontWeight: 600 }}>#1</span>
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>/ 1</span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 200 }}>
            <span style={{ fontSize: 12, color: "var(--ink-2)" }}>CP</span>
            <ProgressBar value={420} max={3000} height={5} />
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-1)", whiteSpace: "nowrap" }}>
              420 / 3,000
            </span>
          </div>

          <div style={{ width: 1, height: 22, background: "var(--line)" }} />

          <Pill tone="accent" icon="crown">Leading</Pill>
        </div>
      )}

      <Btn kind="ghost" size="sm" iconRight="chevronRight">Leaderboard</Btn>
      <Btn kind="ghost" size="sm" icon="help" />
    </header>
  );
}

/* ----- New Task modal --------------------------------------- */
function NewTaskModal({ open, onClose }) {
  if (!open) return null;

  const crew = [
    { name: "Shkaplerov", hue: 25 },
    { name: "Ivanishin",  hue: 200 },
    { name: "Burbank",    hue: 70 },
    { name: "Kononenko",  hue: 320 },
    { name: "Kuipers",    hue: 140 },
    { name: "Pettit",     hue: 280 },
  ];

  return (
    <div style={{
      position: "absolute", inset: 0, zIndex: 100,
      display: "grid", placeItems: "center",
      background: "oklch(0.05 0.02 280 / 0.55)",
      backdropFilter: "blur(4px)",
      WebkitBackdropFilter: "blur(4px)",
      animation: "fadeIn 200ms ease",
    }}
    onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 580, maxWidth: "calc(100vw - 40px)",
          background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))",
          border: "1px solid var(--line)",
          borderRadius: 14,
          boxShadow: "0 20px 60px oklch(0 0 0 / 0.5), 0 1px 0 oklch(1 0 0 / 0.04) inset",
          color: "var(--ink-1)",
          overflow: "hidden",
        }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 18px",
          borderBottom: "1px solid var(--line-soft)",
          background: "oklch(0.22 0.06 290)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <div style={{
              width: 26, height: 26, borderRadius: 7,
              background: "var(--accent)", color: "var(--accent-ink)",
              display: "grid", placeItems: "center", flexShrink: 0,
            }}>
              <Icon name="spark" size={14} stroke={2} />
            </div>
            <div style={{ minWidth: 0, lineHeight: 1.15 }}>
              <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: 1, color: "var(--ink-3)", textTransform: "uppercase", whiteSpace: "nowrap" }}>
                Briefing
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: "var(--ink-0)", marginTop: 3 }}>New task</div>
            </div>
          </div>
          <button onClick={onClose} title="Close"
            style={{ width: 30, height: 30, borderRadius: 7, color: "var(--ink-2)", display: "grid", placeItems: "center" }}
            onMouseEnter={(e) => e.currentTarget.style.background = "var(--bg-3)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M5 5l14 14M19 5L5 19" />
            </svg>
          </button>
        </div>

        {/* Two-column body */}
        <div style={{ padding: "18px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
          {/* Photo info */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: "var(--ink-3)", textTransform: "uppercase", marginBottom: 10 }}>
              Photo info
            </div>
            <dl style={{ margin: 0, display: "grid", gap: 6, fontSize: 12.5 }}>
              {[
                ["Image", "ISS038-E-13869", true],
                ["Date", "2014-02-14", true],
                ["Focal length", "58 mm"],
                ["Location", "Houston, United States"],
                ["Nadir point", "\u2014"],
                ["Photo center", "29.8\u00b0 N, \u201295.4\u00b0 W", true],
              ].map(([k, v, mono]) => (
                <div key={k} style={{ display: "grid", gridTemplateColumns: "110px 1fr", gap: 8 }}>
                  <dt style={{ color: "var(--ink-3)" }}>{k}</dt>
                  <dd className={mono ? "mono" : ""} style={{ margin: 0, color: "var(--ink-1)" }}>{v}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Crew */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: "var(--ink-3)", textTransform: "uppercase", marginBottom: 10 }}>
              ISS Expedition 38 crew
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
              {crew.map((c, i) => (
                <div key={c.name} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: "50%",
                    background: `radial-gradient(circle at 30% 30%, oklch(0.85 0.12 ${c.hue}), oklch(0.4 0.08 ${c.hue}))`,
                    border: "1.5px solid oklch(0.4 0.05 285)",
                    display: "grid", placeItems: "center",
                    color: "oklch(0.95 0.02 285)", fontWeight: 600, fontSize: 16,
                    boxShadow: "inset 0 -4px 8px oklch(0 0 0 / 0.3)",
                  }}>
                    {c.name[0]}
                  </div>
                  <span style={{ fontSize: 11, color: "var(--ink-2)" }}>{c.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Stats table */}
        <div style={{ padding: "0 18px 18px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: "var(--ink-3)", textTransform: "uppercase", marginBottom: 10 }}>
            Your stats
          </div>
          <div style={{
            border: "1px solid var(--line-soft)", borderRadius: 10,
            overflow: "hidden",
          }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead>
                <tr style={{ background: "oklch(0.26 0.06 290)" }}>
                  {["", "Total", "Rank", "To next", "To #1"].map((h, i) => (
                    <th key={i} style={{
                      textAlign: i === 0 ? "left" : "right",
                      padding: "8px 12px",
                      fontSize: 11, fontWeight: 600, color: "var(--ink-2)",
                      borderBottom: "1px solid var(--line-soft)",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ["Tasks",       "19",  "#11", "2",   "872"],
                  ["Control pts", "122", "#11", "2",   "3,645"],
                  ["Hours",       "4.8h","#6",  "0.5h","87.6h"],
                ].map(([k, ...vals], r) => (
                  <tr key={k} style={{
                    background: r % 2 ? "oklch(0.21 0.05 290)" : "transparent",
                  }}>
                    <td style={{ padding: "9px 12px", color: "var(--ink-1)", fontWeight: 500 }}>{k}</td>
                    {vals.map((v, i) => (
                      <td key={i} className="mono" style={{
                        padding: "9px 12px", textAlign: "right",
                        color: i === 0 ? "var(--ink-0)" : "var(--ink-2)",
                        fontWeight: i === 0 ? 600 : 400,
                      }}>{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: "14px 18px",
          background: "oklch(0.18 0.05 290)",
          borderTop: "1px solid var(--line)",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
        }}>
          <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
            Pick ≥3 control points that match in <span style={{ color: "var(--ink-1)" }}>both</span> the photo & map.
          </div>
          <Btn kind="primary" size="md" iconRight="chevronRight" onClick={onClose}>
            <span style={{ whiteSpace: "nowrap" }}>Let’s go</span>
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* fade-in keyframes */
if (typeof document !== "undefined" && !document.getElementById("laon-anim-css")) {
  const s = document.createElement("style");
  s.id = "laon-anim-css";
  s.textContent = `@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }`;
  document.head.appendChild(s);
}

/* ----- Numbered pin overlay --------------------------------- */
const Pin = ({ x, y, n, active, ghost, onClick }) => (
  <button
    onClick={onClick}
    style={{
      position: "absolute",
      left: `${x * 100}%`, top: `${y * 100}%`,
      transform: "translate(-50%, -100%)",
      width: 26, height: 30, padding: 0, background: "none", border: 0,
      cursor: "pointer", zIndex: 5,
      filter: active ? "drop-shadow(0 0 8px var(--accent))" : "drop-shadow(0 2px 4px oklch(0 0 0 / 0.6))",
      transition: "filter 150ms, transform 150ms",
    }}
    onMouseEnter={(e) => e.currentTarget.style.transform = "translate(-50%, -100%) scale(1.12)"}
    onMouseLeave={(e) => e.currentTarget.style.transform = "translate(-50%, -100%) scale(1)"}
  >
    <svg viewBox="0 0 26 30" width="26" height="30">
      <path
        d="M13 1c6 0 11 4.6 11 10.4 0 6.2-6.5 12.5-10 16.7a1.3 1.3 0 0 1-2 0C8.5 23.9 2 17.6 2 11.4 2 5.6 7 1 13 1z"
        fill={ghost ? "oklch(0.4 0.05 290)" : "var(--accent)"}
        stroke={active ? "white" : "oklch(0.25 0.05 100)"}
        strokeWidth={active ? "1.6" : "1"}
        opacity={ghost ? 0.6 : 1}
      />
    </svg>
    <span className="mono" style={{
      position: "absolute", inset: 0, paddingTop: 2,
      display: "grid", placeItems: "center",
      fontSize: 12, fontWeight: 700,
      color: ghost ? "oklch(0.85 0.02 280)" : "var(--accent-ink)",
    }}>{n}</span>
  </button>
);

/* ----- ISS panel (left) -------------------------------------- */
function ISSPanel({ tweaks, points, activeId, onActivate }) {
  const [adj, setAdj] = useState({ brightness: 0, contrast: 0, gamma: 1, saturation: 0 });
  const [showAdj, setShowAdj] = useState(true);
  const set = (k) => (v) => setAdj(s => ({ ...s, [k]: v }));
  const reset = () => setAdj({ brightness: 0, contrast: 0, gamma: 1, saturation: 0 });
  const dirty = adj.brightness || adj.contrast || adj.gamma !== 1 || adj.saturation;

  return (
    <section style={{
      gridArea: "iss",
      position: "relative",
      background: "var(--bg-0)",
      borderRight: "1px solid var(--line)",
      overflow: "hidden",
    }}>
      {/* Photo header */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, zIndex: 4,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px",
        background: "linear-gradient(180deg, oklch(0 0 0 / 0.55), transparent)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon name="camera" size={14} />
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-0)" }}>ISS photograph</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-2)", padding: "2px 6px", border: "1px solid var(--line-soft)", borderRadius: 5 }}>
            ISS038-E-13869
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <Btn kind="ghost" size="sm" icon="sliders" onClick={() => setShowAdj(s => !s)}
               title="Toggle image adjustments">
            {showAdj ? "Hide" : "Adjust"}
          </Btn>
          <Btn kind="ghost" size="sm" icon="expand" title="Fullscreen" />
        </div>
      </div>

      {/* The photo */}
      <div style={{
        position: "absolute", inset: 0,
        transform: `scale(${0.78 + 0.22 * tweaks.issSize})`,
        transformOrigin: "center center",
        transition: "transform 200ms ease",
      }}>
        <ISSMock {...adj} />
        {points.filter(p => p.photo).map(p => (
          <Pin key={p.id} x={p.photo.x} y={p.photo.y} n={p.n}
               active={p.id === activeId}
               onClick={() => onActivate(p.id)} />
        ))}
      </div>

      {/* Adjustment popover */}
      {showAdj && (
        <div style={{ position: "absolute", top: 56, left: 14, zIndex: 5, width: 280 }}>
          <FloatCard title="Image adjustments" icon="sliders" right={
            <button onClick={reset}
              style={{ fontSize: 11, color: dirty ? "var(--ink-1)" : "var(--ink-3)",
                       display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Icon name="reset" size={11} /> Reset
            </button>
          } padding="10px 12px 12px">
            <div style={{ display: "grid", gap: 7 }}>
              <Slider label="Brightness" value={adj.brightness} onChange={set("brightness")} />
              <Slider label="Contrast"   value={adj.contrast}   onChange={set("contrast")} />
              <Slider label="Gamma"      value={adj.gamma}      min={0.5} max={2} step={0.05} onChange={set("gamma")} />
              <Slider label="Saturation" value={adj.saturation} onChange={set("saturation")} />
            </div>
          </FloatCard>
        </div>
      )}

      {/* Footer caption */}
      <div style={{
        position: "absolute", bottom: 12, left: 14, right: 14, zIndex: 4,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        fontSize: 11, color: "oklch(0.78 0.02 285 / 0.85)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Pill tone="ghost" mono>14 Feb 2014 · 03:22 UTC</Pill>
          <Pill tone="ghost" mono>ƒ/1.4 · 1/4s · ISO 25600</Pill>
        </div>
        <span className="mono" style={{ color: "var(--ink-3)" }}>NASA/JSC · public domain</span>
      </div>
    </section>
  );
}

/* ----- Map panel (center) ------------------------------------ */
function MapPanel({ tweaks, points, activeId, onActivate }) {
  const [mode, setMode] = useState("osm");
  const [layers, setLayers] = useState({ viirs: true, sdgsat: true });
  const [adj, setAdj] = useState({ brightness: 1, contrast: 1, saturation: 1 });
  const set = (k) => (v) => setAdj(s => ({ ...s, [k]: v }));

  return (
    <section style={{
      gridArea: "map",
      position: "relative",
      background: "var(--bg-0)",
      overflow: "hidden",
    }}>
      <MapMock
        mode={mode}
        overlays={{
          viirs: layers.viirs ? 0.5 : 0,
          sdgsat: layers.sdgsat ? 0.85 : 0,
        }}
        brightness={adj.brightness}
        contrast={adj.contrast}
        saturation={adj.saturation}
      />
      {points.map(p => p.map ? (
        <Pin key={p.id} x={p.map.x} y={p.map.y} n={p.n}
             active={p.id === activeId}
             onClick={() => onActivate(p.id)} />
      ) : null)}

      {/* Floating zoom — bottom-left */}
      <div style={{ position: "absolute", left: 12, bottom: 36, zIndex: 4, display: "grid", gap: 6 }}>
        <FloatCard padding="0" style={{ minWidth: 0 }}>
          <button style={{ width: 34, height: 34, display: "grid", placeItems: "center", color: "var(--ink-1)" }}>
            <Icon name="plus" size={14} />
          </button>
          <div style={{ height: 1, background: "var(--line-soft)" }} />
          <button style={{ width: 34, height: 34, display: "grid", placeItems: "center", color: "var(--ink-1)" }}>
            <Icon name="minus" size={14} />
          </button>
        </FloatCard>
        <FloatCard padding="0" style={{ minWidth: 0 }}>
          <button style={{ width: 34, height: 34, display: "grid", placeItems: "center", color: "var(--ink-1)" }}
                  title="Recenter">
            <Icon name="target" size={14} />
          </button>
        </FloatCard>
      </div>

      {/* Top-left mode switch */}
      <div style={{ position: "absolute", left: 12, top: 12, zIndex: 4 }}>
        <Segmented
          options={[
            { value: "osm", label: "OSM", icon: "map" },
            { value: "sat", label: "Satellite", icon: "sat" },
          ]}
          value={mode}
          onChange={setMode}
          size="sm"
        />
      </div>

      {/* Top-right layer card */}
      <div style={{ position: "absolute", right: 12, top: 12, zIndex: 4, width: 268 }}>
        <FloatCard title="Layers & enhancement" icon="layers" padding="10px 12px 12px">
          <div style={{ display: "grid", gap: 8 }}>
            <LayerToggle
              label="VIIRS"
              sub="NOAA · 750m"
              checked={layers.viirs}
              onChange={(v) => setLayers(s => ({ ...s, viirs: v }))}
              swatch="oklch(0.7 0.1 240)"
            />
            <LayerToggle
              label="SDGSAT EU/UK"
              sub="High-res lights · 40m"
              checked={layers.sdgsat}
              onChange={(v) => setLayers(s => ({ ...s, sdgsat: v }))}
              swatch="oklch(0.92 0.18 95)"
            />
            <div style={{ height: 1, background: "var(--line-soft)", margin: "4px 0" }} />
            <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 600 }}>
              SDGSAT filters
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              <Slider label="Brightness" value={Math.round((adj.brightness - 1) * 100)}
                      onChange={(v) => set("brightness")(1 + v / 100)} />
              <Slider label="Contrast"   value={Math.round((adj.contrast - 1) * 100)}
                      onChange={(v) => set("contrast")(1 + v / 100)} />
              <Slider label="Saturation" value={Math.round((adj.saturation - 1) * 100)}
                      onChange={(v) => set("saturation")(1 + v / 100)} />
            </div>
          </div>
        </FloatCard>
      </div>

      {/* Compass / scale — bottom-right */}
      <div style={{
        position: "absolute", right: 12, bottom: 36, zIndex: 4,
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <div style={{
          fontSize: 10, color: "oklch(0.85 0.02 285 / 0.7)",
          background: "oklch(0.18 0.05 290 / 0.65)", padding: "4px 8px", borderRadius: 6,
          border: "1px solid var(--line-soft)",
          fontFamily: '"JetBrains Mono", monospace',
        }}>
          ⟵ 20 km ⟶
        </div>
      </div>
    </section>
  );
}

const LayerToggle = ({ label, sub, checked, onChange, swatch }) => (
  <button
    onClick={() => onChange(!checked)}
    style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "6px 8px", borderRadius: 7,
      background: checked ? "oklch(0.3 0.07 290 / 0.6)" : "transparent",
      border: `1px solid ${checked ? "var(--line)" : "transparent"}`,
      transition: "background 120ms",
      width: "100%", textAlign: "left",
    }}
  >
    <div style={{
      width: 14, height: 14, borderRadius: 4,
      background: checked ? swatch : "transparent",
      border: `1.5px solid ${checked ? swatch : "var(--ink-3)"}`,
      display: "grid", placeItems: "center",
      flexShrink: 0,
    }}>
      {checked && <Icon name="check" size={10} stroke={2.4} />}
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 12, color: "var(--ink-1)", fontWeight: 500 }}>{label}</div>
      <div className="mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>{sub}</div>
    </div>
  </button>
);

/* ----- Sidebar (right) — control points ---------------------- */
function Sidebar({ points, activeId, onActivate, onRename, onDelete, onAdd }) {
  const enoughPoints = points.length >= 3;

  return (
    <aside style={{
      gridArea: "side",
      display: "flex", flexDirection: "column",
      background: "linear-gradient(180deg, var(--bg-1), var(--bg-0))",
      borderLeft: "1px solid var(--line)",
    }}>
      {/* Brand block — moved here to match reference */}
      <div style={{
        padding: "14px 16px",
        borderBottom: "1px solid var(--line-soft)",
        display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "var(--bg-3)", border: "1px solid var(--line)",
            display: "grid", placeItems: "center", color: "var(--accent)",
          }}>
            <Icon name="moon" size={16} />
          </div>
          <div style={{ lineHeight: 1.05 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink-0)" }}>Lost at</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink-0)" }}>night</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <Btn kind="ghost" size="sm" icon="info" title="Mission info" />
          <Btn kind="ghost" size="sm" icon="help" title="Help" />
        </div>
      </div>

      {/* Image identity */}
      <div style={{
        padding: "12px 16px", borderBottom: "1px solid var(--line-soft)",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <Icon name="info" size={14} stroke={1.8} />
        <span className="mono" style={{ fontSize: 12.5, color: "var(--ink-1)", flex: 1 }}>ISS038-E-13869</span>
        <Pill tone="ghost" mono>1 / 12</Pill>
      </div>

      {/* Section header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 16px 8px",
      }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: "var(--ink-3)", textTransform: "uppercase" }}>
          Control points
        </div>
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          {points.length} / min 3
        </span>
      </div>

      {/* Points list */}
      <div style={{ padding: "0 12px", flex: 1, overflowY: "auto", display: "grid", gap: 6, alignContent: "start" }}>
        {points.map((p) => (
          <PointRow
            key={p.id}
            point={p}
            active={p.id === activeId}
            onActivate={() => onActivate(p.id)}
            onRename={(name) => onRename(p.id, name)}
            onDelete={() => onDelete(p.id)}
          />
        ))}

        {/* Add row — dashed call-to-action */}
        <button
          onClick={onAdd}
          style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "10px 12px", marginTop: 4,
            background: "transparent",
            border: "1.5px dashed var(--line)", borderRadius: 9,
            color: "var(--ink-2)", textAlign: "left",
            transition: "background 120ms, border-color 120ms, color 120ms",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "oklch(0.3 0.07 290 / 0.35)";
            e.currentTarget.style.color = "var(--ink-0)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--ink-2)";
          }}
        >
          <Icon name="plus" size={14} />
          <span style={{ fontSize: 12.5 }}>Add control point</span>
          <span style={{ flex: 1 }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>
            click photo + map
          </span>
        </button>

        {points.length === 0 && (
          <div style={{
            marginTop: 8, padding: "12px",
            fontSize: 11.5, color: "var(--ink-3)", lineHeight: 1.5,
            background: "oklch(0.22 0.05 290 / 0.5)", borderRadius: 8,
            border: "1px solid var(--line-soft)",
          }}>
            Pick the same landmark in <strong style={{ color: "var(--ink-1)" }}>both</strong> the ISS photo and the map.
            Repeat 3+ times to triangulate.
          </div>
        )}
      </div>

      {/* Hint footer */}
      {points.length > 0 && points.length < 3 && (
        <div style={{
          padding: "10px 16px",
          fontSize: 11.5, color: "var(--warn)",
          borderTop: "1px solid var(--line-soft)",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <Icon name="info" size={12} />
          Add {3 - points.length} more point{3 - points.length > 1 ? "s" : ""} to enable Submit.
        </div>
      )}

      {/* Action bar */}
      <div style={{
        padding: 14, borderTop: "1px solid var(--line)",
        background: "oklch(0.16 0.05 290)",
        display: "flex", gap: 8,
      }}>
        <Btn kind="secondary" size="md" title="Try with hints">Try</Btn>
        <Btn kind="primary" size="md" disabled={!enoughPoints} title="Submit your control points">
          Submit
        </Btn>
        <div style={{ flex: 1 }} />
        <Btn kind="ghost" size="md" title="Skip this image">Skip</Btn>
      </div>
    </aside>
  );
}

/* ----- Single control-point row ----------------------------- */
const PointRow = ({ point, active, onActivate, onRename, onDelete }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(point.name);
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const commit = () => {
    onRename(draft.trim() || point.name);
    setEditing(false);
  };

  return (
    <div
      onClick={onActivate}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "8px 10px",
        background: active ? "oklch(0.34 0.08 290 / 0.7)" : "oklch(0.24 0.06 290 / 0.55)",
        border: `1px solid ${active ? "var(--accent)" : "var(--line)"}`,
        borderRadius: 9,
        transition: "background 120ms, border-color 120ms",
        cursor: "pointer",
      }}
    >
      {/* Numbered pin */}
      <div style={{ position: "relative", width: 24, height: 28, flexShrink: 0 }}>
        <svg viewBox="0 0 24 28" width="24" height="28" style={{ position: "absolute", inset: 0 }}>
          <path
            d="M12 1c5.5 0 10 4.3 10 9.6 0 5.7-6 11.5-9.2 15.4a1 1 0 0 1-1.6 0C7.9 22.1 2 16.3 2 10.6 2 5.3 6.5 1 12 1z"
            fill="var(--accent)"
            stroke="oklch(0.3 0.06 100)"
            strokeWidth="1"
          />
        </svg>
        <span className="mono" style={{
          position: "absolute", inset: 0, paddingTop: 1,
          display: "grid", placeItems: "center",
          fontSize: 11, fontWeight: 700, color: "var(--accent-ink)",
        }}>
          {point.n}
        </span>
      </div>

      {/* Name (editable on dblclick) */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") { setDraft(point.name); setEditing(false); }
            }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%", background: "var(--bg-1)", color: "var(--ink-0)",
              border: "1px solid var(--accent)", borderRadius: 5,
              padding: "3px 6px", fontSize: 13, fontFamily: "inherit", outline: "none",
            }}
          />
        ) : (
          <div
            onDoubleClick={(e) => { e.stopPropagation(); setEditing(true); }}
            style={{
              fontSize: 13, color: "var(--ink-0)", fontWeight: 500,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}
            title="Double-click to rename"
          >
            {point.name}
          </div>
        )}
        <div className="mono" style={{ fontSize: 10, color: "var(--ink-3)", marginTop: 1 }}>
          {point.matched ? "matched · photo & map" : "photo only · click map to match"}
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 2 }} onClick={(e) => e.stopPropagation()}>
        <button
          title="Point info"
          style={{
            width: 26, height: 26, borderRadius: 6,
            color: "var(--ink-2)", display: "grid", placeItems: "center",
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = "var(--bg-3)"}
          onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
        >
          <Icon name="info" size={13} />
        </button>
        <button
          title="Delete point"
          onClick={onDelete}
          style={{
            width: 26, height: 26, borderRadius: 6,
            color: "var(--ink-2)", display: "grid", placeItems: "center",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(0.32 0.14 25 / 0.5)"; e.currentTarget.style.color = "oklch(0.92 0.08 25)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--ink-2)"; }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
          </svg>
        </button>
      </div>
    </div>
  );
};

/* ----- Tweaks panel removed ---------------------------------- */
function TweaksRemoved() { return null; }

/* ----- Root --------------------------------------------------- */
const tweaks = { density: "comfortable", showGamification: true, issSize: 1, highContrast: false };

function Participation({ withBriefing, frameId }) {
  const [showBriefing, setShowBriefing] = useState(withBriefing);

  const [points, setPoints] = useState([
    { id: "p1", n: 1, name: "City core",       photo: { x: 0.50, y: 0.56 }, map: { x: 0.55, y: 0.52 }, matched: true },
    { id: "p2", n: 2, name: "Northern outpost", photo: { x: 0.32, y: 0.30 }, map: { x: 0.40, y: 0.30 }, matched: true },
    { id: "p3", n: 3, name: "Coast cluster",    photo: { x: 0.66, y: 0.72 }, map: { x: 0.70, y: 0.70 }, matched: true },
    { id: "p4", n: 4, name: "Bright suburb",    photo: { x: 0.42, y: 0.74 }, map: null, matched: false },
  ]);
  const [activeId, setActiveId] = useState("p4");

  const addPoint = useCallback(() => {
    const n = points.length + 1;
    const id = "p" + Math.random().toString(36).slice(2, 7);
    setPoints((arr) => [...arr, { id, n, name: `Point ${n}`, photo: null, map: null, matched: false }]);
    setActiveId(id);
  }, [points.length]);
  const renamePoint = useCallback((id, name) => {
    setPoints((arr) => arr.map(p => p.id === id ? { ...p, name } : p));
  }, []);
  const deletePoint = useCallback((id) => {
    setPoints((arr) => arr.filter(p => p.id !== id).map((p, i) => ({ ...p, n: i + 1 })));
    setActiveId((cur) => cur === id ? null : cur);
  }, []);

  return (
    <div data-screen-label={withBriefing ? "01 With briefing" : "02 Participation"}
      style={{
        position: "relative",
        display: "grid",
        gridTemplateAreas: `"top  top  top"
                            "iss  map  side"`,
        gridTemplateRows: "var(--topbar-h) 1fr",
        gridTemplateColumns: `minmax(360px, 1fr) minmax(420px, 1.4fr) var(--rail-w)`,
        width: "100%", height: "100%",
      }}>
      <TopBar tweaks={tweaks} />
      <ISSPanel tweaks={tweaks} points={points} activeId={activeId} onActivate={setActiveId} />
      <MapPanel tweaks={tweaks} points={points} activeId={activeId} onActivate={setActiveId} />
      <Sidebar
        points={points}
        activeId={activeId}
        onActivate={setActiveId}
        onRename={renamePoint}
        onDelete={deletePoint}
        onAdd={addPoint}
      />
      <NewTaskModal open={showBriefing} onClose={() => setShowBriefing(false)} />
    </div>
  );
}

function ScreenFrame({ label, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        color: "var(--ink-2)", fontSize: 12, fontWeight: 500, padding: "0 4px",
      }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: 99, background: "var(--accent)" }} />
          {label}
        </span>
        <span className="mono" style={{ color: "var(--ink-3)", fontSize: 11 }}>1440 × 900</span>
      </div>
      <div style={{
        width: 1440, height: 900,
        borderRadius: 14, border: "1px solid var(--line)",
        boxShadow: "0 30px 80px oklch(0 0 0 / 0.5)",
        overflow: "hidden", background: "var(--bg-0)", position: "relative",
      }}>
        {children}
      </div>
    </div>
  );
}

function App() {
  return (
    <div style={{
      width: "100vw", minHeight: "100vh",
      background: "oklch(0.10 0.02 285)",
      padding: 40, display: "flex", flexDirection: "column", gap: 40,
    }}>
      <header style={{
        display: "flex", alignItems: "baseline", justifyContent: "space-between",
        color: "var(--ink-1)",
      }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 600, color: "var(--ink-0)" }}>Lost at Night — Full screen flow</div>
          <div style={{ fontSize: 13, color: "var(--ink-3)", marginTop: 4 }}>
            Eight key screens, side by side. 1440 × 900.
          </div>
        </div>
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>v3 · 8 frames</span>
      </header>
      <ScreenFrame label="01 — Participation · briefing">
        <Participation withBriefing={true} />
      </ScreenFrame>
      <ScreenFrame label="02 — Participation · active">
        <Participation withBriefing={false} />
      </ScreenFrame>
      <ScreenFrame label="03 — Home / Landing">
        <Home />
      </ScreenFrame>
      <ScreenFrame label="04 — Login">
        <Login />
      </ScreenFrame>
      <ScreenFrame label="05 — Challenges">
        <Challenges />
      </ScreenFrame>
      <ScreenFrame label="06 — Batches (photos in a campaign)">
        <Batches />
      </ScreenFrame>
      <ScreenFrame label="07 — Statistics">
        <Statistics />
      </ScreenFrame>
      <ScreenFrame label="08 — Result (post-submit)">
        <Result />
      </ScreenFrame>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
