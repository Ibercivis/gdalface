/* ──────────────────────────────────────────────────────────────
   Mock map — synthetic raster with "city light" hotspots,
   road grid and a river. Pure SVG, no tiles.
   ────────────────────────────────────────────────────────────── */

const MapMock = ({ mode = "osm", overlays = { viirs: 0.6, sdgsat: 0.85 }, brightness = 1, contrast = 1, saturation = 1 }) => {
  const filter = `brightness(${brightness}) contrast(${contrast}) saturate(${saturation})`;

  // Deterministic "cities" — fixed seeds so refresh keeps the look
  const hotspots = [
    { x: 520, y: 420, r: 130, i: 1.0 },     // main metro
    { x: 380, y: 340, r: 60,  i: 0.55 },
    { x: 660, y: 380, r: 55,  i: 0.5 },
    { x: 460, y: 540, r: 70,  i: 0.65 },
    { x: 720, y: 520, r: 45,  i: 0.4 },
    { x: 280, y: 480, r: 40,  i: 0.35 },
    { x: 600, y: 220, r: 38,  i: 0.32 },
    { x: 170, y: 280, r: 28,  i: 0.25 },
    { x: 820, y: 280, r: 30,  i: 0.28 },
    { x: 220, y: 620, r: 32,  i: 0.3 },
    { x: 760, y: 660, r: 30,  i: 0.28 },
  ];

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", filter, transition: "filter 150ms" }}>
      {/* Base map */}
      <svg viewBox="0 0 960 800" preserveAspectRatio="xMidYMid slice"
           style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        <defs>
          <pattern id="streetGrid" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M0 30 H60 M30 0 V60" stroke="oklch(0.45 0.05 290 / 0.18)" strokeWidth="0.6" fill="none" />
          </pattern>
          <pattern id="streetGridFine" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M0 10 H20 M10 0 V20" stroke="oklch(0.45 0.05 290 / 0.08)" strokeWidth="0.4" fill="none" />
          </pattern>
          <radialGradient id="cityLight" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="oklch(0.96 0.04 90)" stopOpacity="0.95" />
            <stop offset="35%" stopColor="oklch(0.86 0.12 80)" stopOpacity="0.55" />
            <stop offset="70%" stopColor="oklch(0.6 0.1 65)"  stopOpacity="0.18" />
            <stop offset="100%" stopColor="oklch(0.4 0.05 60)" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="riverG" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="oklch(0.42 0.07 240)" />
            <stop offset="1" stopColor="oklch(0.32 0.06 250)" />
          </linearGradient>
        </defs>

        {/* base */}
        {mode === "osm" ? (
          <>
            <rect width="960" height="800" fill="oklch(0.32 0.04 290)" />
            <rect width="960" height="800" fill="url(#streetGridFine)" />
            <rect width="960" height="800" fill="url(#streetGrid)" />
            {/* parks / blocks */}
            <g opacity="0.5">
              <rect x="120" y="180" width="180" height="120" rx="6" fill="oklch(0.36 0.06 160)" opacity="0.35" />
              <rect x="700" y="600" width="160" height="120" rx="6" fill="oklch(0.36 0.06 160)" opacity="0.3" />
              <rect x="420" y="120" width="120" height="80" rx="6" fill="oklch(0.36 0.06 160)" opacity="0.3" />
            </g>
            {/* highways */}
            <g stroke="oklch(0.6 0.14 30)" strokeWidth="2.2" fill="none" opacity="0.7">
              <path d="M0 380 C 200 360, 350 420, 520 420 S 820 460, 960 440" />
              <path d="M520 0 C 510 200, 540 320, 520 420 S 480 640, 500 800" />
              <path d="M120 800 C 240 700, 380 600, 520 540 S 740 480, 960 520" />
            </g>
            <g stroke="oklch(0.55 0.04 290)" strokeWidth="0.9" fill="none" opacity="0.45">
              <path d="M0 220 H960 M0 580 H960 M180 0 V800 M780 0 V800" />
            </g>
            {/* river */}
            <path d="M -20 60 C 200 200, 300 340, 380 420 C 460 500, 500 660, 580 820"
                  stroke="url(#riverG)" strokeWidth="22" fill="none" strokeLinecap="round" opacity="0.85" />
            <path d="M -20 60 C 200 200, 300 340, 380 420 C 460 500, 500 660, 580 820"
                  stroke="oklch(0.55 0.08 240)" strokeWidth="1" fill="none" opacity="0.55" />
          </>
        ) : (
          <>
            <rect width="960" height="800" fill="oklch(0.22 0.02 280)" />
            {/* satellite-like noise */}
            <g opacity="0.25">
              {Array.from({ length: 200 }).map((_, i) => {
                const x = (i * 137) % 960, y = (i * 211) % 800;
                return <rect key={i} x={x} y={y} width="14" height="10" fill={i % 3 ? "oklch(0.3 0.04 100)" : "oklch(0.28 0.04 200)"} />;
              })}
            </g>
            <path d="M -20 60 C 200 200, 300 340, 380 420 C 460 500, 500 660, 580 820"
                  stroke="oklch(0.35 0.06 240)" strokeWidth="22" fill="none" strokeLinecap="round" opacity="0.85" />
          </>
        )}

        {/* SDGSAT/VIIRS — city lights */}
        <g style={{ mixBlendMode: "screen" }}>
          {hotspots.map((h, i) => (
            <g key={i} opacity={h.i * (overlays.sdgsat ?? 0)}>
              <circle cx={h.x} cy={h.y} r={h.r * 1.5} fill="url(#cityLight)" />
              <circle cx={h.x} cy={h.y} r={h.r * 0.5} fill="oklch(0.98 0.05 95)" opacity="0.7" />
            </g>
          ))}
        </g>
        {/* faint VIIRS — wider, bluer */}
        <g style={{ mixBlendMode: "screen" }} opacity={overlays.viirs ?? 0}>
          {hotspots.map((h, i) => (
            <circle key={i} cx={h.x} cy={h.y} r={h.r * 2.4} fill="oklch(0.7 0.1 240)" opacity={h.i * 0.18} />
          ))}
        </g>
      </svg>

      {/* attribution */}
      <div style={{
        position: "absolute", bottom: 4, right: 6,
        fontSize: 10, color: "oklch(0.7 0.03 285 / 0.7)",
        background: "oklch(0.18 0.05 290 / 0.5)",
        padding: "2px 6px", borderRadius: 4,
        fontFamily: '"JetBrains Mono", monospace',
      }}>
        Leaflet · OSM · EOG · SDGSAT @ LostAtNight.org
      </div>
    </div>
  );
};

window.MapMock = MapMock;
