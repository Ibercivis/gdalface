/* ──────────────────────────────────────────────────────────────
   ISS night-shot mock — synthetic city as seen from orbit
   Yellow-orange core with arteries radiating, deep black bg.
   ────────────────────────────────────────────────────────────── */

const ISSMock = ({ brightness = 0, contrast = 0, gamma = 1, saturation = 0 }) => {
  // map slider conventions: brightness/contrast in [-100..100] → multipliers
  const b = 1 + brightness / 100;
  const c = 1 + contrast / 100;
  const s = 1 + saturation / 100;
  const filter = `brightness(${b}) contrast(${c}) saturate(${s})`;

  // points generated deterministically — clustered around a center
  const center = { x: 380, y: 340 };
  const lights = useMemo(() => {
    const arr = [];
    let rng = 1337;
    const next = () => (rng = (rng * 9301 + 49297) % 233280) / 233280;
    // dense core
    for (let i = 0; i < 380; i++) {
      const a = next() * Math.PI * 2;
      const r = Math.pow(next(), 1.6) * 130;
      arr.push({ x: center.x + Math.cos(a) * r, y: center.y + Math.sin(a) * r * 0.8, s: 0.5 + next() * 1.6, h: 60 + next() * 25, k: 1 });
    }
    // arteries (radiating)
    const arms = [0, 0.6, 1.2, 1.9, 2.6, 3.3, 4.1, 4.8, 5.4];
    arms.forEach((angle) => {
      const len = 130 + next() * 180;
      const wig = 0.3 + next() * 0.4;
      for (let t = 0; t < 70; t++) {
        const dist = (t / 70) * len + 60;
        const wob = Math.sin(t * 0.4) * 18 * wig;
        const x = center.x + Math.cos(angle) * dist + Math.cos(angle + Math.PI / 2) * wob;
        const y = center.y + Math.sin(angle) * dist * 0.85 + Math.sin(angle + Math.PI / 2) * wob;
        arr.push({ x, y, s: 0.4 + next() * 1.2, h: 55 + next() * 30, k: 0.8 });
      }
    });
    // sparse far points
    for (let i = 0; i < 120; i++) {
      arr.push({ x: next() * 760, y: next() * 600, s: 0.3 + next() * 0.7, h: 60 + next() * 30, k: 0.5 });
    }
    return arr;
  }, []);

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: "oklch(0.05 0.02 270)", filter, transition: "filter 150ms" }}>
      <svg viewBox="0 0 760 600" preserveAspectRatio="xMidYMid slice"
           style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        <defs>
          <radialGradient id="issGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="oklch(0.95 0.16 80)" stopOpacity="0.9" />
            <stop offset="0.5" stopColor="oklch(0.7 0.18 60)" stopOpacity="0.4" />
            <stop offset="1" stopColor="oklch(0.3 0.1 40)" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="issMoonglow" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="oklch(0.9 0.05 240)" stopOpacity="0.5" />
            <stop offset="1" stopColor="oklch(0.5 0.05 240)" stopOpacity="0" />
          </radialGradient>
          <filter id="issBlur">
            <feGaussianBlur stdDeviation="0.8" />
          </filter>
        </defs>

        {/* atmospheric glow over center */}
        <ellipse cx={center.x} cy={center.y} rx="220" ry="160" fill="url(#issGlow)" opacity="0.85" />
        {/* secondary cluster — distant city left */}
        <ellipse cx="120" cy="260" rx="70" ry="50" fill="url(#issMoonglow)" opacity="0.6" />

        {/* lights */}
        <g style={{ mixBlendMode: "screen" }} filter="url(#issBlur)">
          {lights.map((l, i) => (
            <circle key={i} cx={l.x} cy={l.y} r={l.s}
                    fill={`oklch(${0.85 + (l.k * 0.1)} 0.18 ${l.h})`}
                    opacity={l.k} />
          ))}
        </g>
        {/* hot core */}
        <circle cx={center.x} cy={center.y} r="12" fill="oklch(0.98 0.1 90)" opacity="0.95" filter="url(#issBlur)" />
        <circle cx={center.x} cy={center.y} r="3.5" fill="white" />

        {/* faint stars on the dark areas */}
        {Array.from({ length: 26 }).map((_, i) => {
          const x = (i * 71) % 760;
          const y = ((i * 113) % 600);
          return <circle key={i} cx={x} cy={y} r="0.6" fill="oklch(0.9 0.02 280)" opacity="0.35" />;
        })}
      </svg>

      {/* film grain */}
      <div style={{
        position: "absolute", inset: 0,
        background: "radial-gradient(ellipse at 50% 50%, transparent 60%, oklch(0 0 0 / 0.5) 100%)",
        pointerEvents: "none",
      }} />
    </div>
  );
};

window.ISSMock = ISSMock;
