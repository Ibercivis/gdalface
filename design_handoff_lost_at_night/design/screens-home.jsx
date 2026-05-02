/* ──────────────────────────────────────────────────────────────
   Lost at Night — Home / Landing
   ────────────────────────────────────────────────────────────── */
function Home() {
  return (
    <div data-screen-label="03 Home" style={{
      width: "100%", height: "100%", position: "relative",
      background: "linear-gradient(180deg, oklch(0.12 0.04 285), oklch(0.18 0.05 290))",
      overflow: "hidden", display: "flex", flexDirection: "column",
    }}>
      {/* Stars */}
      <svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice"
           style={{ position: "absolute", inset: 0, opacity: 0.7 }}>
        {Array.from({ length: 80 }).map((_, i) => {
          const x = (i * 137) % 1440, y = (i * 211) % 900;
          const r = (i % 5 === 0) ? 1.4 : 0.6;
          return <circle key={i} cx={x} cy={y} r={r} fill="oklch(0.95 0.02 280)" opacity={0.3 + (i % 5) * 0.1} />;
        })}
      </svg>

      {/* Topbar */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "20px 48px", position: "relative", zIndex: 2,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--bg-3)", border: "1px solid var(--line)", display: "grid", placeItems: "center", color: "var(--accent)" }}>
            <Icon name="moon" size={16} />
          </div>
          <span style={{ fontWeight: 600, fontSize: 16, color: "var(--ink-0)" }}>Lost at Night</span>
        </div>
        <nav style={{ display: "flex", gap: 24, alignItems: "center", fontSize: 13 }}>
          {["Challenges", "Batches", "Statistics", "About"].map(l => (
            <a key={l} href="#" style={{ color: "var(--ink-2)", textDecoration: "none" }}>{l}</a>
          ))}
          <Btn kind="primary" size="sm">Sign in</Btn>
        </nav>
      </header>

      {/* Hero */}
      <main style={{
        flex: 1, display: "grid", gridTemplateColumns: "1.1fr 1fr",
        alignItems: "center", padding: "0 48px", gap: 48, position: "relative", zIndex: 2,
      }}>
        <div>
          <Pill tone="ghost" icon="spark">Citizen science · ESA-funded</Pill>
          <h1 style={{ fontSize: 56, lineHeight: 1.05, margin: "20px 0 18px", color: "var(--ink-0)", fontWeight: 700, letterSpacing: -1, textWrap: "balance" }}>
            Help us locate the night<br />from <span style={{ color: "var(--accent)" }}>orbit</span>.
          </h1>
          <p style={{ fontSize: 17, color: "var(--ink-2)", lineHeight: 1.5, maxWidth: 540, marginBottom: 28 }}>
            Match astronaut photographs of Earth at night with their real-world coordinates.
            Your taps train models that map light pollution worldwide.
          </p>
          <div style={{ display: "flex", gap: 12 }}>
            <Btn kind="primary" size="lg" iconRight="chevronRight">Start a challenge</Btn>
            <Btn kind="ghost" size="lg" icon="play">Watch how it works</Btn>
          </div>
          <div style={{ display: "flex", gap: 32, marginTop: 36 }}>
            {[
              ["Photos located", "284,612"],
              ["Active citizens", "12,408"],
              ["Cities mapped", "3,217"],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="mono" style={{ fontSize: 24, color: "var(--ink-0)", fontWeight: 600 }}>{v}</div>
                <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>{k}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Hero visual: Earth from orbit */}
        <div style={{ position: "relative", height: 480 }}>
          <div style={{
            position: "absolute", inset: 0,
            background: `radial-gradient(circle at 50% 55%, oklch(0.45 0.1 240) 0%, oklch(0.2 0.06 270) 35%, transparent 60%)`,
            filter: "blur(20px)",
          }} />
          <div style={{
            position: "absolute", left: "50%", top: "50%",
            width: 360, height: 360, transform: "translate(-50%, -50%)",
            borderRadius: "50%",
            background: "radial-gradient(circle at 35% 30%, oklch(0.3 0.08 250), oklch(0.08 0.03 270) 80%)",
            boxShadow: "0 0 80px oklch(0.6 0.15 230 / 0.3), inset -40px -40px 80px oklch(0 0 0 / 0.6)",
            overflow: "hidden",
          }}>
            {/* city lights */}
            {Array.from({ length: 60 }).map((_, i) => {
              const a = (i * 0.31) * Math.PI * 2;
              const r = 60 + (i * 17) % 110;
              const x = 180 + Math.cos(a) * r;
              const y = 180 + Math.sin(a) * r * 0.85;
              return <div key={i} style={{ position: "absolute", left: x, top: y, width: 2, height: 2, background: "oklch(0.92 0.16 90)", borderRadius: "50%", boxShadow: "0 0 4px oklch(0.92 0.16 90)" }} />;
            })}
          </div>
        </div>
      </main>

      <footer style={{ padding: "20px 48px", color: "var(--ink-3)", fontSize: 12, position: "relative", zIndex: 2, display: "flex", justifyContent: "space-between" }}>
        <span>© 2025 Lost at Night · Constructed by Ibercivis</span>
        <span className="mono">v 2.1.0</span>
      </footer>
    </div>
  );
}

window.Home = Home;
