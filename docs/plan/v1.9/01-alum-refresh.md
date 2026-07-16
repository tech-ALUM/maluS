# Step 1 — ALUM brand refresh (fonts, tokens, components, mark)

## Objective

Apply the ALUM brand identity to the GUI as a design-only refresh: vendor the
real brand fonts, align tokens to the locked brand hex, refresh the shared
components, and add the ALUM mark — every function/route/flow unchanged.

## Deliverables

- [x] **Vendor fonts**: Space Grotesk (500/600/700), Inter (400/500/600),
      JetBrains Mono (400/500), latin subset woff2 under
      `src/malus/web/static/fonts/`; `@font-face` at the top of `app.css`
      (`font-display: swap`, local `/static/fonts/*` urls — no CDN).
- [x] **Tokens**: align `:root` to `references/brand.md` — `--paper #F7F8FA`,
      `--line #E2E7EC`, `--muted #5C6470`; add `--faint`, `--surface`,
      `--coral-soft`, `--teal-soft`, `--teal-dark`, `--radius`, `--shadow`.
- [x] **Components** (in `app.css`): topbar coral bottom rule + `.brand-mark`;
      Space Grotesk headings with tighter tracking; refined buttons/`.btn`
      (radius + transition); `.rtd` Space Grotesk headers + row hover; `.card` /
      `.metric` / `.subm-panel` subtle `--shadow`; callouts on the soft tints
      (`.cta-banner` coral-soft, `.ai-proposal` teal-soft); antialiased body.
- [x] **ALUM mark** (`base.html`): inline `<img class="brand-mark"
      src="/static/alum-mark.svg">` in the topbar brand link; `alum-mark.svg`
      copied into `static/`.
- [x] **Packaging**: `package-data` for `malus.web` includes `static/fonts/*`
      (so the woff2 ship in the Docker image, mirroring the `static/vendor/*` fix).
- [x] **Verify**: suite green; the fonts serve (`/static/fonts/inter-400.woff2`
      → 200 `font/woff2`) and the browser loads the real families; the mark
      serves + renders in the topbar; brand tokens present in the served CSS.

## Key behaviors

- Design-only: no template logic, route, service, or HTMX change; the refresh is
  shared (`app.css` + `base.html`) so it lands on every page uniformly.
- No runtime CDN: the fonts are vendored and served by the app; the stack falls
  back to `system-ui` if a face fails.

## Definition of Done

The GUI renders in the real ALUM fonts with brand-exact tokens and the ALUM mark
in the topbar; the fonts are served locally and ship in the image; every function
works exactly as before; suite green; no migration.

## Out of scope

- Layout rework / new navigation (this is a cohesive refresh, not a restructure).
- Changing the maluS favicon / product mark (kept as-is).
- Any behaviour, route, or data change.

## Deviations

Recorded in `memory/decisions/2026-07-16-v1.9-alum-refresh.md`.

- Fonts fetched from Google Fonts at build time and vendored (latin subset only,
  ~264 KB) — covers EN + Italian; no CDN at runtime.
- The `alum-brand-identity` skill's **guide template** (hero + TOC) was NOT
  applied — it targets doc pages, not a web app. Its **tokens, logo assets, and
  component philosophy** were applied to the existing `app.css` instead.
- Live check used the login page + static assets (the seeded dev server shares
  the preview port with the default config); the shared shell/CSS covers all
  pages. No schema change / no migration. Full suite green (255).

## Sources

- Design session with Alberto Boffi, 2026-07-16 (this repo, Claude Code).
- `alum-brand-identity` skill: `references/brand.md` (locked palette + type +
  logo rules), `assets/alum-mark.svg`. Fonts: Google Fonts (Space Grotesk, Inter,
  JetBrains Mono), vendored locally.
