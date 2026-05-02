# Handoff: Lost at Night — Web Redesign

## Overview

Lost at Night is a citizen-science project where users help locate the geographic origin of night-time photographs of Earth taken from the International Space Station. They compare an ISS photo against a map and place control points to match light patterns between the two.

This handoff covers a full visual + UX redesign of the public web product, in **8 screens** that together describe the end-to-end participation flow plus supporting pages (home, login, browsing, statistics, results).

## About the design files

The files in `design/` are **design references created in HTML/JSX**. They are React prototypes loaded inline through Babel-standalone — meant to convey look, layout, components, copy, and intended interactions. They are **not** production code to lift directly.

Your task is to **recreate these designs in the target codebase's environment**, using its established stack and conventions:
- If the project already uses React/Vue/Svelte/etc., use those patterns and the existing component library/design system.
- If there is no codebase yet, **React + TypeScript + Tailwind** (or CSS Modules) is a good default for this kind of dashboard-style product. The current Lost at Night site uses plain server-rendered HTML — ask the team whether the redesign should stay there or move to a SPA.

Reuse the design **values** (colors, typography, spacing, component anatomy, copy) — but rebuild components in idiomatic code for the target stack.

## Fidelity

**High-fidelity.** Final colors, typography, spacing, layout, copy, iconography (custom SVG glyphs in `components.jsx`), and interaction model. Recreate pixel-close.

The map and ISS image previews are stylized SVG mocks — in production they should be replaced with:
- Real Leaflet/MapLibre tiles (the current site already uses Leaflet)
- Real ISS night photographs from the project's batch/photo pipeline

---

## Design system

### Color tokens (CSS custom properties — see `design/Participation.html` `:root` block)

All colors are expressed in `oklch()` for perceptual consistency. Hex equivalents below for convenience.

**Backgrounds (deep night palette)**

| Token | oklch | Approx hex | Use |
|---|---|---|---|
| `--bg-0` | `oklch(0.16 0.045 290)` | `#1d1830` | App background |
| `--bg-1` | `oklch(0.20 0.055 290)` | `#26203c` | Surfaces / cards |
| `--bg-2` | `oklch(0.245 0.06 288)` | `#2f2848` | Inset surfaces |
| `--bg-3` | `oklch(0.295 0.065 286)` | `#3a3155` | Elevated / chips |
| `--bg-4` | `oklch(0.36 0.07 284)` | `#493e68` | Hover |

**Lines**
- `--line: oklch(0.36 0.05 286 / 0.55)` — primary borders
- `--line-soft: oklch(0.5 0.04 286 / 0.22)` — dividers

**Ink (text)**
- `--ink-0: oklch(0.98 0.01 280)` — primary
- `--ink-1: oklch(0.88 0.02 285)` — secondary
- `--ink-2: oklch(0.72 0.03 285)` — tertiary
- `--ink-3: oklch(0.58 0.04 285)` — labels / hints

**Accent + semantic**
- `--accent: oklch(0.92 0.18 105)` — lime/yellow ≈ `#e5e64a`. The signature color — used for primary CTAs, the active control point, leaderboard "you" highlight, and submit/result states.
- `--accent-ink: oklch(0.22 0.05 100)` — text on accent surfaces
- `--info: oklch(0.78 0.13 230)` — blue, used for info pills
- `--good: oklch(0.78 0.16 150)` — green, completed states
- `--warn: oklch(0.82 0.17 75)` — amber, warnings

### Typography

- **UI:** *Inter Tight* — weights 400, 500, 600, 700
- **Numerics / IDs:** *JetBrains Mono* — weights 400, 500, 600 — applied via the `.mono` class. Always use mono for: photo IDs (`ISS038-E-13869`), control-point counters, ranks, point counts, timers, coordinates.
- Base size: 14 px / 1.4 line-height
- Tabular numerals enabled (`font-feature-settings: "tnum" 1`)
- Headings: 56 px (hero), 30 px (page titles), 22–24 px (section), 14 px (card titles)

### Spacing & shape

- Radius: `--radius: 10px` for buttons/inputs/chips, `--radius-lg: 14px` for cards & modals, full pill (`999px`) for status badges.
- Shadow (cards/modals): `0 1px 0 oklch(1 0 0 / 0.04) inset, 0 8px 24px oklch(0 0 0 / 0.35)`
- Topbar height: 52–56 px
- Right rail width: 320 px
- Standard gap: 12 px; section gap 24–32 px; page padding 32–48 px

### Iconography

Custom thin-stroke SVG icons defined in `design/components.jsx` → `Icon` component. Stroke width 1.6 by default. Set: `moon`, `play`, `pause`, `crosshair`, `pin`, `plus`, `chevronRight`, `chevronLeft`, `chevronDown`, `check`, `x`, `sliders`, `layers`, `eye`, `info`, `spark`, `trophy`, `more`. **Reuse exactly** — don't substitute Lucide/Feather; the visual weight is tuned.

### Shared components (in `design/components.jsx`)

- **`Btn`** — `kind: "primary" | "secondary" | "ghost"`, `size: "sm" | "md" | "lg"`, optional `icon` / `iconRight`. Primary uses accent lime with dark ink.
- **`Pill`** — small status badge. `tone: "live" | "ghost" | "accent" | "neutral" | "good" | "warn"`. Optional `icon`. Optional `mono` for numeric pills.
- **`Slider`** — labeled range with min/max marks and current numeric readout.
- **`Segmented`** — compact segmented control (used for filter tabs, layer toggles).
- **`FloatCard`** — surface used for the floating overlays on the map.
- **`ProgressBar`** — used in challenge rows and onboarding modal.

---

## Screens

> All screens are 1440 × 900 design viewport.

### 01 — Participation · briefing modal
**Purpose:** First-time / new-task welcome. The participation screen renders behind a centered modal that explains the task in three steps before the user can interact.

**Layout:**
- Full participation screen behind a backdrop (`oklch(0.05 0.02 280 / 0.55)` + `backdrop-filter: blur(4px)`)
- Modal: 560 px wide, `--bg-1`, `--radius-lg`, drop shadow. Centered.
- Modal body: hero illustration (ISS + Earth), title, 3-step explainer, primary CTA "Start locating", secondary "Skip tour".

### 02 — Participation · active
**Purpose:** Core task. Match an ISS night photograph to the same area on a map by placing 4+ control points.

**Layout:** CSS grid, two rows × three columns.
```
"top  top  top"      52px
"iss  map  side"     1fr
1fr  1.4fr  320px
```

- **Topbar (row 1, all columns):** Logo + task title (`ISS038-E-13869`), centered: 4 step indicators (Briefing → Locate → Match → Submit). Right cluster: discreet gamification — Rank #11, +84 CP this session, "Leaderboard" link. Density and gamification visibility are constants in `app.jsx` (originally Tweaks-controlled; keep static unless product wants them user-toggleable).

- **Left panel — `ISSPanel`:** ISS photograph viewport. Top toolbar: zoom %, fit, rotate, reset. Bottom-left floating card: image-adjustment sliders (Brightness, Contrast, Gamma, Saturation) — collapsible. Control points are draggable circles with the point number + name label. Active point uses `--accent`; matched points use `--good`; unplaced uses outlined-only.

- **Center panel — `MapPanel`:** Leaflet/MapLibre map. Top toolbar: basemap toggle (OSM / Satellite), layer toggles (VIIRS night lights, SDGSAT), search. Bottom-left: layer legend (toggleable). Bottom-right: coordinate readout (mono). Same control-point markers as ISS panel — clicking a point in either panel activates it in the other.

- **Right rail — `Sidebar`:** Control-points list. Each row: number badge, editable name, status icon (matched / unplaced), drag handle, delete button. "+ Add point" button at bottom. Below the list: a "Confidence" radius slider and the action stack — Skip · Save draft · **Submit match** (primary, accent).

**Interactions:**
- Click a point in ISS panel → map pans to its map location, point becomes active.
- Drag in ISS panel → updates `photo: {x, y}` (0..1 normalized to ISS canvas).
- Click on map (when point active) → sets `map: {x, y}` for that point.
- Click point name → inline rename.
- Submit disabled until ≥3 points are matched (matched = both photo and map set).

### 03 — Home / Landing
**Purpose:** Public-facing entry. Sells the project, surfaces social proof, drives sign-in / start.

**Layout:**
- Top nav: logo, links (Challenges, Batches, Statistics, About), Sign-in CTA.
- Hero: 60/40 split. Left: pill ("Citizen science · ESA-funded"), 56px headline ("Help us locate the night from orbit."), 17px lede, two CTAs ("Start a challenge" primary, "Watch how it works" ghost), three KPI tiles (Photos located / Active citizens / Cities mapped).
- Right: stylized Earth-from-orbit visual — radial gradient sphere with scattered "city light" dots.
- Background: 80 SVG stars at low opacity, gradient from `bg-0` to `bg-1`.
- Footer: copyright + version.

### 04 — Login
**Purpose:** Sign-in. Also entry for ORCID (researcher community).

**Layout:** 50/50 split.
- Left: brand panel with logo, pull-quote (Dr. Alejandro Sánchez de Miguel · ESA), legal links.
- Right: 360px form column — Email, Password (with "Forgot?" inline), persistent-session checkbox styled as filled accent square with check icon, primary "Sign in" button, divider "or continue with", two secondary buttons (Google, ORCID), "Create an account" link.

### 05 — Challenges
**Purpose:** Browse/join active campaigns.

**Layout:**
- Topbar: app nav + Rank #11 pill + avatar circle (radial-gradient placeholder).
- Two-column body: main list + 320px right rail.
- **Main:** page title + segmented filter (All / Joined / Ending soon). Stack of `ChallengeRow`s — thumbnail (radial-gradient orbital city), city name, batch ID + photo count (mono), inline progress bar `done / total`, status pill (`{n}d left` live; `Ending` accent if ≤3d; `Complete` neutral), "+N from you" hint, action button (Continue / Join / Review).
- **Rail:** "Leaderboard · this week" — top 5 with rank, handle, points (mono). The "you" row gets accent border + subtle highlight. Below: "Your week" — 4-up stats grid (Tasks / Pts / Streak / Hours).

### 06 — Batches (photos in a campaign)
**Purpose:** Drill into a campaign and pick a photo to work on.

**Layout:**
- Topbar (same as Challenges, with "Batches" active).
- Sub-header strip: breadcrumb (Challenges › Houston metropolitan area), batch ID title, meta (124 photos · 12 days remaining · captured Feb 2014). Right: Grid/List segmented toggle, primary "Start unlocated" CTA.
- Body: 6-column responsive grid of `PhotoTile`s. Each tile:
  - Aspect 1:1, 10px radius, accent border if user contributed.
  - Synthetic city-from-orbit thumbnail (radial gradient + scattered dots).
  - Top-left: green check badge if completed.
  - Top-right: `+N` accent pill if user earned points on it.
  - Bottom: photo ID in mono, white, on dark gradient overlay.

### 07 — Statistics
**Purpose:** Personal dashboard / motivation.

**Layout:**
- Topbar (same).
- Page title.
- 4-up KPI grid: Tasks completed (187, +12 this week), Control points (1,124, +148 this week), Hours (32.4h, top 6%), Global rank (#11, ↑3 places). Each card: small uppercase label, large mono value, delta line in `--good` or `--accent`.
- Two-column body:
  - Wide card: "Activity over time" — segmented `12w / 3m / 1y`, bar chart (12 bars, last bar highlighted in accent). SVG implementation included; OK to swap for a real chart lib (Recharts / visx / d3).
  - Narrow card: "Regions you've located" — 5 horizontal stacked progress bars, one per continent, each in its own hue.

### 08 — Result (post-submit)
**Purpose:** Reward and motivate the next action immediately after submitting a match.

**Layout:** 720px centered card on the gradient app background.
- Top section: radial accent glow, "Submitted" check pill, large headline ("Great match!"), photo ID in mono, distance summary, **massive accent +84 CP** (mono, 56px, lime).
- Stats strip: 3-column equal split — Accuracy (94.2%, green), Distance (8.4 km), Time taken (2:14). Vertical dividers between columns.
- Mini-map: 160px tall SVG showing your guess (accent dot + halo) vs actual (green dot + halo) with dashed connecting line. Legend bottom-left.
- Action bar: Share (ghost) · Back to challenges (secondary) · **Next photo** (primary, iconRight).

---

## Interactions & state

### Per-screen state

| Screen | State | Notes |
|---|---|---|
| Participation | `points: ControlPoint[]`, `activeId: string \| null`, `showBriefing: boolean` | See `app.jsx` for current shape. Persist drafts to backend on Save. |
| Challenges | filter tab, joined-by-user set | Server-driven list. |
| Batches | view mode (grid/list), selected photo | URL query for batch ID. |
| Statistics | range selector | Fetch aggregated metrics by user. |
| Result | none, render-only | Pass scoring payload via route state / query. |

### Control-point shape

```ts
type ControlPoint = {
  id: string;
  n: number;                                 // 1-indexed display order
  name: string;
  photo: { x: number; y: number } | null;    // 0..1 normalized to ISS image
  map:   { x: number; y: number } | null;    // 0..1 normalized to map viewport — replace with {lat,lng} in production
  matched: boolean;                          // photo && map both set
};
```

In production, `map` should be `{ lat: number, lng: number }` driven by the Leaflet map's coordinate system, not normalized values.

### Animations & transitions

- Modal fade-in: 200ms ease (`fadeIn` keyframe in CSS).
- Hover state on buttons/rows: `--bg-3` → `--bg-4`, 120ms.
- ISS photo size scales with the `tweaks.issSize` value (currently a constant `1`); leave at 1 for production unless product wants the zoom slider.
- Active control-point: subtle pulse on the accent halo (optional polish).

### Accessibility

- All buttons need accessible labels (icons-only buttons in toolbars must have `aria-label`).
- Color is **never the only signal** — status pills always pair color with text or an icon.
- Keyboard: arrow keys to nudge an active control point by 1px in its panel; Enter to confirm; Esc to deselect.
- Modal traps focus while open.
- Maintain ≥4.5:1 contrast for body text. The lime accent on dark backgrounds passes; on light surfaces it does not — never put accent text on a light background.

### Responsive behavior

The mocks are desktop-only (1440 × 900). For mobile, the **participation screen** needs special handling — recommended approach:
- Stack: Topbar → ISS photo → Map → Sidebar as bottom sheet.
- Tabs to switch between "Photo" and "Map" views, with control-points list as a draggable bottom sheet.
- Touch targets ≥44px.
The marketing/login/dashboard screens reflow to a single column naturally.

---

## Files in `design/`

| File | What it is |
|---|---|
| `Participation.html` | Entry page. Loads React + Babel + all JSX files. Defines all CSS custom properties in `:root`. |
| `app.jsx` | App shell — currently stacks all 8 screens vertically inside `ScreenFrame` cards for review. The `Participation` component (active task screen) lives here. |
| `components.jsx` | Shared design-system components: `Icon`, `Pill`, `Btn`, `Slider`, `Segmented`, `FloatCard`, `ProgressBar`. **Lift these first** when starting the rebuild. |
| `iss-mock.jsx` | ISS photograph panel — image canvas, control-point markers, image-adjustment sliders. |
| `map-mock.jsx` | Map panel — basemap toggle, layer controls, coordinate readout. Stylized; replace with Leaflet/MapLibre in production. |
| `screens-home.jsx` | Home / Landing screen. |
| `screens-login.jsx` | Login screen. |
| `screens-other.jsx` | Challenges, Batches, Statistics, Result screens + the shared `NavTopbar`. |
| `tweaks-panel.jsx` | Dev-only knob panel — **not part of the product**. Safe to ignore. |

## Implementation order (suggested)

1. **Tokens + global CSS** — copy the `:root` block from `Participation.html` into the codebase's theme layer.
2. **`components.jsx` primitives** — `Btn`, `Pill`, `Icon`, `Segmented`, `Slider`. Without these the screens can't be built faithfully.
3. **`NavTopbar`** (in `screens-other.jsx`) — used by 4 screens.
4. **Static screens first:** Home → Login → Result. Lowest risk, build confidence in the system.
5. **Dashboard screens:** Challenges → Batches → Statistics. Integrate real data.
6. **Participation screen** — the most complex. Build in this order: (a) layout shell + Topbar, (b) Sidebar with control-point list state, (c) ISSPanel with draggable points, (d) MapPanel wired up to a real Leaflet map, (e) coordinate sync between panels, (f) submit flow → Result.
7. **Briefing modal** + onboarding gating.

## Screenshots

Reference renders of all 8 screens live in `screenshots/`:

- `01-participation-briefing.png`
- `02-participation-active.png`
- `03-home.png`
- `04-login.png`
- `05-challenges.png`
- `06-batches.png`
- `07-statistics.png`
- `08-result.png`

Use them as the source of truth when the prototype HTML disagrees with the README.

## Out of scope of this handoff

- Backend / API contracts
- Authentication implementation
- Real ISS photo pipeline + tile servers
- Mobile-specific designs (described in §Responsive but not mocked)
- Admin / campaign-creation tooling
