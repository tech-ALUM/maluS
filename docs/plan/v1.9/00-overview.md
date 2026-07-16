# maluS v1.9 — ALUM Brand Refresh (GUI)

Requested by Alberto Boffi, 2026-07-16 (this repo, Claude Code). A cohesive
visual refresh of the web GUI to the ALUM brand identity, **keeping every
function and flow** — this is a design-only pass (CSS + shared shell + markup
classes; no route, service, or HTMX behaviour changes).

## Scope decisions (agreed 2026-07-16)

- **Depth: cohesive refresh** — keep structure and functionality; elevate the
  design system (tokens, type, components, spacing, hierarchy) applying the exact
  ALUM brand tokens. Not a layout rework.
- **Fonts: vendor the real families** — Space Grotesk / Inter / JetBrains Mono
  served locally (`@font-face` woff2 under `static/fonts/`), honouring the
  no-runtime-CDN rule. Previously the GUI only *named* them and fell back to
  system fonts.

## What changes

- The three brand fonts are vendored (latin subset, ~264 KB total) and wired via
  `@font-face`; the app now renders in the real brand type.
- Colour tokens aligned to the locked brand hex (`references/brand.md`): `--paper`
  `#F7F8FA`, `--line` `#E2E7EC`, `--muted` `#5C6470`, plus new `--faint`,
  `--surface`, `--coral-soft`, `--teal-soft`, and `--radius` / `--shadow`.
- Components refreshed to the brand philosophy (coral deliberate, teal support,
  JetBrains Mono for ids/versions): topbar with a coral rule + the **ALUM mark**,
  refined buttons, tables (Space Grotesk headers + row hover), cards/metrics with
  a subtle shadow, callouts on the soft tints.
- Applied once in the shared `app.css` + `base.html`, so it lands on every page.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-alum-refresh.md` | Vendor fonts; align tokens; refresh components; ALUM mark; package-data | v1 (GUI), the `alum-brand-identity` skill |

## Global Definition of Done

- `python -m pytest -q` green; **no schema change / no migration**; no runtime
  CDN (fonts served locally); no logic/route change.
- The three brand fonts load from `static/fonts/*.woff2`; colour tokens match
  `references/brand.md`; the ALUM mark shows in the topbar.
- Fonts + logo ship in the package/image (`package-data` includes `static/fonts/*`).

## Sources

- Design session with Alberto Boffi, 2026-07-16 (this repo, Claude Code): scope =
  cohesive refresh + vendor real fonts.
- ALUM brand identity: the `alum-brand-identity` skill — `references/brand.md`
  (locked palette, type system, logo rules) and `assets/alum-mark.svg`.
