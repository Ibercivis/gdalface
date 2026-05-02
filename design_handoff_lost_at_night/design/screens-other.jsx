/* ──────────────────────────────────────────────────────────────
   Lost at Night — Challenges, Batches, Statistics, Result
   ────────────────────────────────────────────────────────────── */

const NavTopbar = ({ active }) => (
  <header style={{
    display: "flex", alignItems: "center", gap: 28,
    padding: "0 32px", height: 56,
    borderBottom: "1px solid var(--line)",
    background: "linear-gradient(180deg, oklch(0.22 0.06 290), oklch(0.18 0.05 290))",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ width: 28, height: 28, borderRadius: 7, background: "var(--bg-3)", border: "1px solid var(--line)", display: "grid", placeItems: "center", color: "var(--accent)" }}>
        <Icon name="moon" size={14} />
      </div>
      <span style={{ fontWeight: 600, fontSize: 14, color: "var(--ink-0)" }}>Lost at Night</span>
    </div>
    <nav style={{ display: "flex", gap: 4, fontSize: 13 }}>
      {["Home", "Challenges", "Batches", "Statistics"].map(l => (
        <a key={l} href="#" style={{
          padding: "6px 12px", borderRadius: 7,
          color: l === active ? "var(--ink-0)" : "var(--ink-2)",
          background: l === active ? "var(--bg-3)" : "transparent",
          textDecoration: "none", fontWeight: 500,
        }}>{l}</a>
      ))}
    </nav>
    <div style={{ flex: 1 }} />
    <Pill tone="ghost" icon="trophy">Rank #11</Pill>
    <div style={{ width: 32, height: 32, borderRadius: "50%",
      background: "radial-gradient(circle at 30% 30%, oklch(0.85 0.12 200), oklch(0.4 0.08 200))",
      border: "1.5px solid var(--line)" }} />
  </header>
);

/* ----- Challenges -------------------------------------------- */
function Challenges() {
  const challenges = [
    { city: "Houston metropolitan area", batch: "ISS038-batch-04", photos: 124, done: 87, days: 12, status: "active", you: 12 },
    { city: "Madrid + Comunidad",        batch: "ISS070-batch-12", photos: 84,  done: 23, days: 28, status: "active", you: 0 },
    { city: "Tokyo Bay",                 batch: "ISS065-batch-09", photos: 210, done: 198, days: 3, status: "ending", you: 4 },
    { city: "Mexico City",               batch: "ISS062-batch-02", photos: 96,  done: 96, days: 0, status: "complete", you: 8 },
    { city: "Cairo / Nile delta",        batch: "ISS058-batch-07", photos: 142, done: 12, days: 45, status: "active", you: 0 },
  ];

  return (
    <div data-screen-label="05 Challenges" style={{
      width: "100%", height: "100%", display: "flex", flexDirection: "column",
      background: "var(--bg-0)", color: "var(--ink-1)",
    }}>
      <NavTopbar active="Challenges" />
      <div style={{ flex: 1, padding: 32, display: "grid", gridTemplateColumns: "1fr 320px", gap: 24, overflow: "auto" }}>
        <div>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 18 }}>
            <div>
              <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: "var(--ink-0)" }}>Active challenges</h1>
              <p style={{ margin: "4px 0 0", color: "var(--ink-3)", fontSize: 13 }}>Locate batches of ISS night photographs.</p>
            </div>
            <Segmented options={[
              { value: "all", label: "All" },
              { value: "joined", label: "Joined" },
              { value: "ending", label: "Ending soon" },
            ]} value="all" onChange={() => {}} />
          </div>

          <div style={{ display: "grid", gap: 10 }}>
            {challenges.map(c => <ChallengeRow key={c.batch} c={c} />)}
          </div>
        </div>

        {/* Right rail */}
        <aside style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: "var(--ink-3)", textTransform: "uppercase", marginBottom: 10 }}>Leaderboard · this week</div>
            <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 8 }}>
              {[
                ["1", "ana_cosmos", 1287, true],
                ["2", "j.silva", 1104],
                ["3", "nighthawk_42", 982],
                ["4", "you", 624, false, true],
                ["5", "stargazer", 612],
              ].map(([r, n, p, top, me]) => (
                <li key={n} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "6px 8px", borderRadius: 7,
                  background: me ? "oklch(0.3 0.07 290 / 0.5)" : top ? "oklch(0.32 0.12 100 / 0.2)" : "transparent",
                  border: me ? "1px solid var(--accent)" : "1px solid transparent",
                }}>
                  <span className="mono" style={{ width: 20, fontSize: 12, color: top ? "var(--accent)" : "var(--ink-3)", fontWeight: 600 }}>{r}</span>
                  <span style={{ flex: 1, fontSize: 13, color: me ? "var(--ink-0)" : "var(--ink-1)", fontWeight: me ? 600 : 400 }}>{n}</span>
                  <span className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>{p}</span>
                </li>
              ))}
            </ol>
          </div>

          <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: "var(--ink-3)", textTransform: "uppercase", marginBottom: 10 }}>Your week</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                ["Tasks", "24"],
                ["Pts", "624"],
                ["Streak", "5d"],
                ["Hours", "1.8h"],
              ].map(([k, v]) => (
                <div key={k} style={{ background: "var(--bg-2)", borderRadius: 8, padding: "10px 12px", border: "1px solid var(--line-soft)" }}>
                  <div className="mono" style={{ fontSize: 18, color: "var(--ink-0)", fontWeight: 600 }}>{v}</div>
                  <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{k}</div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

const ChallengeRow = ({ c }) => {
  const pct = (c.done / c.photos) * 100;
  const tone = c.status === "complete" ? "neutral" : c.status === "ending" ? "accent" : "live";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "auto 1fr auto auto", gap: 16, alignItems: "center",
      padding: "14px 16px",
      background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 10,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 8,
        background: "radial-gradient(circle at 50% 50%, oklch(0.7 0.15 80), oklch(0.25 0.06 290) 80%)",
        boxShadow: "inset 0 0 12px oklch(0 0 0 / 0.5)",
      }} />
      <div>
        <div style={{ fontSize: 14, color: "var(--ink-0)", fontWeight: 500 }}>{c.city}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>{c.batch} · {c.photos} photos</div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
          <div style={{ flex: 1, maxWidth: 280, height: 4, borderRadius: 4, background: "var(--bg-3)", overflow: "hidden" }}>
            <div style={{ width: `${pct}%`, height: "100%", background: c.status === "complete" ? "var(--good)" : "var(--accent)" }} />
          </div>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-2)" }}>{c.done}/{c.photos}</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
        <Pill tone={tone}>
          {c.status === "active" && `${c.days}d left`}
          {c.status === "ending" && `${c.days}d left`}
          {c.status === "complete" && "Complete"}
        </Pill>
        {c.you > 0 && <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>+{c.you} from you</span>}
      </div>
      <Btn kind={c.status === "complete" ? "ghost" : "primary"} size="sm" iconRight="chevronRight">
        {c.status === "complete" ? "Review" : c.you > 0 ? "Continue" : "Join"}
      </Btn>
    </div>
  );
};

/* ----- Batches ----------------------------------------------- */
function Batches() {
  const photos = Array.from({ length: 18 }).map((_, i) => ({
    id: `ISS038-E-${13800 + i * 23}`,
    done: i < 10,
    points: i < 10 ? Math.floor(3 + (i * 1.7) % 6) : 0,
    you: i < 7,
    hue: 60 + (i * 41) % 100,
  }));

  return (
    <div data-screen-label="06 Batches" style={{
      width: "100%", height: "100%", display: "flex", flexDirection: "column",
      background: "var(--bg-0)", color: "var(--ink-1)",
    }}>
      <NavTopbar active="Batches" />
      <div style={{ padding: "24px 32px 12px", borderBottom: "1px solid var(--line-soft)", display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--ink-3)", fontSize: 12 }}>
            Challenges <Icon name="chevronRight" size={11} /> Houston metropolitan area
          </div>
          <h1 style={{ margin: "6px 0 0", fontSize: 22, fontWeight: 600, color: "var(--ink-0)" }}>ISS038-batch-04</h1>
          <div style={{ marginTop: 4, fontSize: 12, color: "var(--ink-3)" }}>124 photographs · 12 days remaining · captured Feb 2014</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Segmented options={[{ value: "g", label: "Grid", icon: "layers" }, { value: "l", label: "List", icon: "sliders" }]} value="g" onChange={() => {}} size="sm" />
          <Btn kind="primary" size="sm" iconRight="play">Start unlocated</Btn>
        </div>
      </div>

      <div style={{ flex: 1, padding: 24, overflow: "auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 14 }}>
          {photos.map(p => <PhotoTile key={p.id} p={p} />)}
        </div>
      </div>
    </div>
  );
}

const PhotoTile = ({ p }) => (
  <div style={{
    aspectRatio: "1 / 1", borderRadius: 10,
    border: `1px solid ${p.you ? "var(--accent)" : "var(--line)"}`,
    overflow: "hidden", position: "relative", cursor: "pointer",
    background: "oklch(0.06 0.02 270)",
  }}>
    {/* synthetic city-from-orbit thumbnail */}
    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <defs>
        <radialGradient id={`g-${p.id}`} cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor={`oklch(0.92 0.16 ${p.hue})`} stopOpacity="0.85" />
          <stop offset="0.6" stopColor={`oklch(0.5 0.12 ${p.hue})`} stopOpacity="0.3" />
          <stop offset="1" stopColor="oklch(0.1 0.03 270)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="100" height="100" fill="oklch(0.08 0.02 270)" />
      <ellipse cx="50" cy="50" rx="35" ry="25" fill={`url(#g-${p.id})`} />
      {Array.from({ length: 16 }).map((_, j) => (
        <circle key={j} cx={20 + (j * 13) % 60} cy={20 + (j * 19) % 60} r="0.6" fill={`oklch(0.92 0.16 ${p.hue})`} opacity="0.7" />
      ))}
    </svg>
    {/* status overlay */}
    <div style={{
      position: "absolute", inset: 0,
      background: p.done ? "linear-gradient(180deg, transparent 50%, oklch(0 0 0 / 0.7))" : "linear-gradient(180deg, oklch(0 0 0 / 0.4), oklch(0 0 0 / 0.5))",
    }} />
    {/* badges */}
    <div style={{ position: "absolute", top: 8, left: 8, right: 8, display: "flex", justifyContent: "space-between" }}>
      {p.done ? (
        <span style={{ background: "var(--good)", color: "oklch(0.18 0.05 150)", borderRadius: 99, width: 18, height: 18, display: "grid", placeItems: "center" }}>
          <Icon name="check" size={11} stroke={2.6} />
        </span>
      ) : <span />}
      {p.you && <Pill tone="accent" mono>+{p.points}</Pill>}
    </div>
    <div className="mono" style={{ position: "absolute", bottom: 8, left: 8, right: 8, fontSize: 10, color: "var(--ink-1)" }}>
      {p.id}
    </div>
  </div>
);

/* ----- Statistics ------------------------------------------- */
function Statistics() {
  return (
    <div data-screen-label="07 Statistics" style={{
      width: "100%", height: "100%", display: "flex", flexDirection: "column",
      background: "var(--bg-0)", color: "var(--ink-1)",
    }}>
      <NavTopbar active="Statistics" />
      <div style={{ flex: 1, padding: 32, overflow: "auto" }}>
        <h1 style={{ margin: "0 0 20px", fontSize: 22, fontWeight: 600, color: "var(--ink-0)" }}>Your statistics</h1>

        {/* KPIs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
          {[
            { k: "Tasks completed", v: "187", d: "+12 this week", tone: "var(--good)" },
            { k: "Control points",  v: "1,124", d: "+148 this week", tone: "var(--good)" },
            { k: "Hours",           v: "32.4h", d: "Top 6%", tone: "var(--accent)" },
            { k: "Global rank",     v: "#11", d: "↑ 3 places", tone: "var(--good)" },
          ].map(s => (
            <div key={s.k} style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: 0.6 }}>{s.k}</div>
              <div className="mono" style={{ fontSize: 30, color: "var(--ink-0)", fontWeight: 600, marginTop: 6 }}>{s.v}</div>
              <div style={{ fontSize: 11, color: s.tone, marginTop: 4 }}>{s.d}</div>
            </div>
          ))}
        </div>

        {/* Activity chart + breakdown */}
        <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 14 }}>
          <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 12, padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 14 }}>
              <div>
                <div style={{ fontSize: 14, color: "var(--ink-0)", fontWeight: 500 }}>Activity over time</div>
                <div style={{ fontSize: 11, color: "var(--ink-3)" }}>Control points per week, last 12 weeks</div>
              </div>
              <Segmented options={[{value:"w",label:"12w"},{value:"q",label:"3m"},{value:"y",label:"1y"}]} value="w" onChange={()=>{}} size="sm" />
            </div>
            <ActivityChart />
          </div>

          <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 12, padding: 18 }}>
            <div style={{ fontSize: 14, color: "var(--ink-0)", fontWeight: 500, marginBottom: 14 }}>Regions you've located</div>
            <div style={{ display: "grid", gap: 10 }}>
              {[
                ["North America", 412, "var(--accent)"],
                ["Europe", 287, "oklch(0.78 0.13 230)"],
                ["Asia", 198, "oklch(0.78 0.16 150)"],
                ["South America", 142, "oklch(0.82 0.17 75)"],
                ["Africa", 85, "oklch(0.7 0.14 320)"],
              ].map(([n, v, c]) => (
                <div key={n}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                    <span style={{ color: "var(--ink-1)" }}>{n}</span>
                    <span className="mono" style={{ color: "var(--ink-2)" }}>{v}</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "var(--bg-3)", overflow: "hidden" }}>
                    <div style={{ width: `${(v/412)*100}%`, height: "100%", background: c }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const ActivityChart = () => {
  const data = [12, 18, 9, 22, 31, 28, 42, 55, 38, 47, 62, 58];
  const max = Math.max(...data);
  return (
    <svg viewBox="0 0 600 180" style={{ width: "100%", height: 180 }}>
      {/* gridlines */}
      {[0, 1, 2, 3].map(i => (
        <line key={i} x1="30" x2="600" y1={20 + i * 40} y2={20 + i * 40} stroke="var(--line-soft)" strokeWidth="0.5" />
      ))}
      {/* bars */}
      {data.map((v, i) => {
        const h = (v / max) * 130;
        return (
          <g key={i}>
            <rect x={40 + i * 47} y={170 - h} width="32" height={h}
              fill={i === data.length - 1 ? "var(--accent)" : "oklch(0.55 0.12 290)"}
              rx="3" />
            <text x={56 + i * 47} y={178} textAnchor="middle" fontSize="9" fill="var(--ink-3)" fontFamily='"JetBrains Mono"'>w{i+1}</text>
          </g>
        );
      })}
    </svg>
  );
};

/* ----- Result (post-submit) --------------------------------- */
function Result() {
  return (
    <div data-screen-label="08 Result" style={{
      width: "100%", height: "100%", position: "relative",
      background: "linear-gradient(180deg, oklch(0.16 0.05 290), oklch(0.12 0.04 290))",
      display: "grid", placeItems: "center", padding: 40,
    }}>
      <div style={{
        width: 720, background: "var(--bg-1)", border: "1px solid var(--line)",
        borderRadius: 16, overflow: "hidden", boxShadow: "0 30px 80px oklch(0 0 0 / 0.5)",
      }}>
        {/* Hero */}
        <div style={{
          padding: "32px 36px",
          background: "radial-gradient(ellipse at 50% 0%, oklch(0.45 0.15 100 / 0.4), transparent 60%)",
          borderBottom: "1px solid var(--line-soft)",
          textAlign: "center",
        }}>
          <Pill tone="accent" icon="check">Submitted</Pill>
          <h2 style={{ margin: "14px 0 6px", fontSize: 30, fontWeight: 600, color: "var(--ink-0)" }}>
            Great match!
          </h2>
          <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 14 }}>
            Your guess for <span className="mono" style={{ color: "var(--ink-1)" }}>ISS038-E-13869</span> was 8.4 km from the actual location.
          </p>
          <div className="mono" style={{ fontSize: 56, color: "var(--accent)", fontWeight: 700, marginTop: 16, lineHeight: 1 }}>
            +84 <span style={{ fontSize: 18, color: "var(--ink-2)", fontWeight: 500 }}>CP</span>
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", padding: 20, gap: 0 }}>
          {[
            ["Accuracy", "94.2%", "var(--good)"],
            ["Distance", "8.4 km", "var(--ink-0)"],
            ["Time taken", "2:14", "var(--ink-0)"],
          ].map(([k, v, c], i) => (
            <div key={k} style={{
              padding: 14, textAlign: "center",
              borderRight: i < 2 ? "1px solid var(--line-soft)" : "none",
            }}>
              <div className="mono" style={{ fontSize: 22, color: c, fontWeight: 600 }}>{v}</div>
              <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>{k}</div>
            </div>
          ))}
        </div>

        {/* Mini map of guess vs actual */}
        <div style={{ padding: "0 20px 20px" }}>
          <div style={{ height: 160, borderRadius: 10, overflow: "hidden", border: "1px solid var(--line-soft)", position: "relative", background: "var(--bg-3)" }}>
            <svg viewBox="0 0 600 160" preserveAspectRatio="xMidYMid slice" style={{ width: "100%", height: "100%" }}>
              <rect width="600" height="160" fill="oklch(0.22 0.04 280)" />
              <g stroke="var(--line-soft)" strokeWidth="0.5">
                {Array.from({ length: 12 }).map((_, i) => <line key={i} x1={i * 50} x2={i * 50} y1="0" y2="160" />)}
                {Array.from({ length: 4 }).map((_, i) => <line key={i} x1="0" x2="600" y1={i * 40} y2={i * 40} />)}
              </g>
              {/* actual */}
              <circle cx="320" cy="80" r="8" fill="var(--good)" opacity="0.4" />
              <circle cx="320" cy="80" r="3" fill="var(--good)" />
              {/* your guess */}
              <circle cx="285" cy="68" r="8" fill="var(--accent)" opacity="0.4" />
              <circle cx="285" cy="68" r="3" fill="var(--accent)" />
              <line x1="285" y1="68" x2="320" y2="80" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="3 3" />
            </svg>
            <div style={{ position: "absolute", left: 12, bottom: 10, display: "flex", gap: 14, fontSize: 11 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--ink-1)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 99, background: "var(--accent)" }} /> Your guess
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--ink-1)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 99, background: "var(--good)" }} /> Actual location
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div style={{ padding: 20, borderTop: "1px solid var(--line)", background: "oklch(0.16 0.05 290)", display: "flex", gap: 10 }}>
          <Btn kind="ghost" size="md">Share</Btn>
          <div style={{ flex: 1 }} />
          <Btn kind="secondary" size="md">Back to challenges</Btn>
          <Btn kind="primary" size="md" iconRight="chevronRight">Next photo</Btn>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Challenges, Batches, Statistics, Result });
