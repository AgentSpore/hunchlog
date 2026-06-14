# HunchLog

Log your hunches. Learn how right you really are.

A no-account web app to record predictions you make about the future — "Will X happen? I'm 70% sure" — then come back when they resolve and discover your true track record: a personal **calibration chart** and **Brier score** that show whether your confidence matches reality.

## Problem

On r/somebodymakethis and r/lightbulb people ask for "a program that tracks predictions" and "a way to check how open-minded someone really is." Everyone *feels* they called it ("I knew that would happen!") — but memory is rewritten by hindsight bias. There's no simple, private tool for a normal person to log a prediction with a confidence level and later see, objectively, how calibrated they are. Metaculus is a heavy community-forecasting platform; PunditTracker is dead; nothing owns the *private personal-calibration* niche.

## Proposed Solution

A fast, single-page tool. Make a prediction (a claim + a probability 0–100% + a resolve-by date). When the date comes, the app nudges you to resolve it (happened / didn't). Over time it computes your **Brier score** (lower = better) and draws a **calibration curve** — your stated probability buckets vs. how often things in each bucket actually came true. Perfect calibration is the diagonal. No account, no social feed, just you vs. reality.

## Architecture

- **Backend** — FastAPI, layered: `api/` routers, `services/` (prediction store, scoring/calibration engine), `core/` config + db, `schemas/` Pydantic v2. Storage aiosqlite. Stdlib + aiosqlite only, no external paid APIs.
- **Frontend** — BUILDLESS (deploy sandbox has no node/npm; never run a build step). `frontend/index.html` + `frontend/app.js` + `frontend/styles.css`. Tailwind via CDN play script with an inline `tailwind.config` for the tokens below; fonts via Google Fonts; **Chart.js via CDN** (`https://cdn.jsdelivr.net/npm/chart.js`) for the calibration chart; vanilla JS `fetch()` to the API. FastAPI mounts the frontend dir as `StaticFiles(directory=..., html=True)` at `/`.
  - CRITICAL (learned the hard way): the script/style tags in index.html must reference assets at ROOT (`/app.js`, `/styles.css`), NOT `/frontend/app.js` — StaticFiles serves the frontend dir contents AT `/`, so `/frontend/...` 404s and the page dies silently.
  - Apply background + font on `<body>` via Tailwind CLASSES (`class="bg-bg font-sans text-ink"`), never a `<style>` block with class-name values. Validate every tag is well-formed.

## Scoring (get this exactly right)

- A resolved prediction has stated probability `p` (0..1) and outcome `o` (1 if it happened, 0 if not).
- **Brier score** = mean over resolved predictions of `(p − o)²`. Range 0 (perfect) … 1 (worst). Show it as a number + a friendly label (≤0.1 "sharp", ≤0.2 "well-calibrated", ≤0.35 "decent", >0.35 "overconfident or noisy").
- **Calibration curve**: bucket resolved predictions by stated probability into deciles [0–10%, 10–20%, …, 90–100%]. For each non-empty bucket, x = mean stated probability in the bucket, y = actual hit rate (fraction that happened), n = count. Plot points against the y=x diagonal (perfect calibration). Points above the line = under-confident, below = over-confident.
- Edge cases: zero resolved → no Brier/curve, show an encouraging empty state. Always compute server-side in `services/`, expose via `GET /api/v1/stats`.

## Data model (sqlite)

`predictions(id, claim TEXT, probability REAL (0..1), resolve_by DATE, category TEXT, status TEXT['open'|'resolved'], outcome INTEGER NULL (1|0), created_at, resolved_at NULL)`

## API (all under /api/v1, no auth, CORS open, NO trailing-slash routes — paths must be exactly `/predictions` to match the frontend fetches)

- `POST /api/v1/predictions` — body `{claim, probability (0..1 or 0..100 — accept percent and normalize), resolve_by, category?}` → created row.
- `GET /api/v1/predictions?status=&category=` — list, newest first; include a derived `due` flag (status open AND resolve_by ≤ today).
- `GET /api/v1/predictions/{id}` — one row.
- `PATCH /api/v1/predictions/{id}/resolve` — body `{outcome: true|false}` → sets status=resolved, outcome, resolved_at.
- `DELETE /api/v1/predictions/{id}` — delete (so users can remove mistakes; the UI needs this).
- `GET /api/v1/stats` — `{brier: float|null, label: str|null, count_resolved, count_open, count_due, calibration: [{bucket, mean_prob, hit_rate, n}], by_category?}`.
- `GET /api/v1/health` → `{status:"ok"}`.

## UX / UI spec (THIS is the bar — a great, distinctive interface, not a generic CRUD form)

**Design language:** calm, intelligent, "quantified-self meets science notebook" — confident and precise without being intimidating or cold. Lots of whitespace, crisp typography, one decisive accent, tasteful data-viz. It should feel like a beautifully-made instrument.

**Design tokens** (put colors in the inline `tailwind.config` theme.extend.colors):
- `bg` `#0B1120` is too dark — use a refined LIGHT theme: `bg` `#F7F8FB`, `surface` `#FFFFFF`, `ink` `#0F172A`, `muted` `#64748B`, `border` `#E6E9F0`.
- Brand `brand` `#0F766E` (deep teal) with `brand-soft` `#CCFBF1`. Outcome colors: `hit` `#16A34A`, `miss` `#E11D48`, `pending` `#D97706`. Use these consistently for resolved-correct / resolved-wrong / open-due.
- Typography (Google Fonts `<link>`): display/headings **"Sora"** (600/700), body **"Inter"** (400/500), numbers/dates/probabilities **"JetBrains Mono"**. Hero 40/48, h2 24/32, body 15/24, mono-stat 32/36.
- Radius 16px cards, 10px controls. Soft shadow `0 8px 30px rgba(15,23,42,.06)`. 8-pt spacing.

**Screens / states**
1. **Dashboard (home)** — top: a calm hero "How calibrated are you?" with a one-line subhead. A **stats row**: big mono **Brier score** + its label, count resolved, count open, and a "X due to resolve" pill (amber, pulses subtly if >0). Center-stage: the **calibration chart** (Chart.js scatter/line: your bucket points + a dashed y=x diagonal; axis labels "Your confidence" / "Reality"; tooltip shows bucket, hit-rate, n). A prominent **"+ New prediction"** button. If there are **due** predictions, a "Resolve now" section lists them with quick Yes/No buttons inline (the satisfying core loop). Empty state (no data): warm invitation + an example, the chart area shows a friendly placeholder explaining what it'll become.
2. **New prediction** — a focused modal/card: the claim (textarea, placeholder "Bitcoin will close above \$100k by Dec 31"), a **big, satisfying probability slider** 0–100% with a live large mono readout and a verbal hint that updates ("coin-flip", "fairly likely", "near-certain"), a resolve-by date picker (defaults to +30 days), optional category chips. Submit with one confident button. Inline validation, optimistic insert, no page reload.
3. **Resolve** — for a due prediction: show the claim + the probability you gave, two big buttons "It happened" (hit-green) / "It didn't" (miss-rose). On resolve, the calibration chart + Brier animate to their new value (small celebratory micro-interaction). 
4. **History / all predictions** — a clean list/table: claim, your probability (mono), resolve-by, status badge (open-amber / correct-green / wrong-rose, each with icon+text, never color alone), category chip. Filter tabs (All / Open / Due / Correct / Wrong). Click a row → detail with delete.
5. **Loading** — skeleton shimmer on cards + chart; never a bare spinner. **Errors** — inline, human ("Couldn't save — try again").

**Interaction quality**
- The probability slider is the signature delight: large, smooth, with the live readout + changing verbal label + the track tinted brand. Buttons have clear focus rings in brand teal. Smooth 150–200ms transitions; the chart animates on data change; the "due" pill pulses. Fully responsive 360→1280 (chart resizes, slider thumb is thumb-friendly on mobile, stats row wraps to a 2×2 grid). Respect `prefers-reduced-motion`. Every status uses icon + text + color (a11y). Lighthouse a11y ≥ 95. Keyboard: `n` opens new-prediction, `/` focuses nothing destructive.

## Seed (so the deployed app isn't empty and the chart has shape)

On startup, if the table is empty, seed ~14 realistic resolved predictions spread across probability buckets (some hits, some misses, deliberately a little over-confident so the calibration curve has a visible, teachable shape) + 2–3 open ones (one already **due**, so the resolve loop is demoable on first visit). Idempotent.

## Success Criteria

- Create a prediction (accepts 70 or 0.7), it appears in the list; resolve a due one, stats + chart update.
- `GET /api/v1/stats` returns a correct Brier score and a non-trivial calibration curve from the seed.
- The frontend is a genuinely polished single page implementing the UX spec — the calibration chart renders real data, the probability slider feels great, due-predictions resolve inline, responsive + accessible — NOT a raw form or JSON page. Assets load from `/` (no `/frontend/...` 404), JS actually runs (event listeners attach), `GET /api/v1/health` → 200.
- No account, no external paid API, no build step; single `uvicorn` process serves API + static frontend.
