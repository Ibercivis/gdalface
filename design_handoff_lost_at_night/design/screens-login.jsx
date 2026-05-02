/* ──────────────────────────────────────────────────────────────
   Lost at Night — Login
   ────────────────────────────────────────────────────────────── */
function Login() {
  return (
    <div data-screen-label="04 Login" style={{
      width: "100%", height: "100%", position: "relative",
      background: "linear-gradient(135deg, oklch(0.14 0.05 290), oklch(0.20 0.06 285))",
      display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden",
    }}>
      {/* Left — visual */}
      <div style={{
        position: "relative", padding: 48,
        background: "radial-gradient(ellipse at 30% 60%, oklch(0.3 0.12 290 / 0.6), transparent 70%)",
        display: "flex", flexDirection: "column", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--bg-3)", border: "1px solid var(--line)", display: "grid", placeItems: "center", color: "var(--accent)" }}>
            <Icon name="moon" size={16} />
          </div>
          <span style={{ fontWeight: 600, fontSize: 15, color: "var(--ink-0)" }}>Lost at Night</span>
        </div>
        <div>
          <blockquote style={{
            margin: 0, fontSize: 22, lineHeight: 1.4, color: "var(--ink-1)",
            borderLeft: "3px solid var(--accent)", paddingLeft: 18, fontWeight: 400, maxWidth: 440,
          }}>
            “Every match you submit helps measure light pollution where satellites cannot reach.”
          </blockquote>
          <div style={{ marginTop: 14, fontSize: 12, color: "var(--ink-3)" }}>— Dr. Alejandro Sánchez de Miguel · ESA</div>
        </div>
        <div style={{ display: "flex", gap: 32, fontSize: 11, color: "var(--ink-3)" }}>
          <span>Privacy</span><span>Terms</span><span>Support</span>
        </div>
      </div>

      {/* Right — form */}
      <div style={{ display: "grid", placeItems: "center", padding: 48 }}>
        <div style={{ width: 360 }}>
          <h2 style={{ margin: "0 0 6px", fontSize: 28, fontWeight: 600, color: "var(--ink-0)" }}>Welcome back</h2>
          <p style={{ margin: "0 0 28px", color: "var(--ink-2)", fontSize: 14 }}>Sign in to continue locating the night.</p>

          <div style={{ display: "grid", gap: 14 }}>
            <Field label="Email" placeholder="you@stars.org" />
            <Field label="Password" placeholder="••••••••••" type="password" right={<a style={{ fontSize: 11, color: "var(--ink-3)" }}>Forgot?</a>} />
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--ink-2)" }}>
              <span style={{ width: 14, height: 14, borderRadius: 4, background: "var(--accent)", display: "grid", placeItems: "center", color: "var(--accent-ink)" }}>
                <Icon name="check" size={10} stroke={2.6} />
              </span>
              Keep me signed in
            </div>
            <Btn kind="primary" size="lg" iconRight="chevronRight">Sign in</Btn>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 12, margin: "22px 0", color: "var(--ink-3)", fontSize: 11 }}>
            <span style={{ height: 1, background: "var(--line-soft)" }} />
            <span>or continue with</span>
            <span style={{ height: 1, background: "var(--line-soft)" }} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <Btn kind="secondary" size="md">Google</Btn>
            <Btn kind="secondary" size="md">ORCID</Btn>
          </div>

          <div style={{ marginTop: 22, fontSize: 12, color: "var(--ink-3)", textAlign: "center" }}>
            New here? <a style={{ color: "var(--accent)", textDecoration: "none" }}>Create an account</a>
          </div>
        </div>
      </div>
    </div>
  );
}

const Field = ({ label, placeholder, type = "text", right }) => (
  <label style={{ display: "grid", gap: 6 }}>
    <span style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--ink-2)" }}>
      {label}{right}
    </span>
    <input type={type} placeholder={placeholder}
      style={{
        height: 40, padding: "0 12px",
        background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 8,
        color: "var(--ink-0)", fontSize: 14, fontFamily: "inherit", outline: "none",
      }} />
  </label>
);

window.Login = Login;
