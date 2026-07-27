# ADR 0003 — Vendored front-end libraries (no CDN, no build step)

**Status:** Accepted (v2, 2026-07-27). Extends ADR 0002.

## Context

The maluS GUI is server-rendered Jinja plus vanilla JS with **no build step
and no CDN at runtime** (repo rule since v1; the GUI must work on an
air-gapped LAN). Front-end functionality beyond vanilla JS is obtained by
vendoring minified libraries under `src/malus/web/static/vendor/`.

The v2 unified document viewer renders reviewer-authored Markdown (and the
baseline itself, authored by any owner) straight into the DOM. Rendering
untrusted-ish member input via `innerHTML` calls for sanitization.

## Decision

Three libraries are vendored, pinned, and served locally:

| Library | Version | Role |
|---|---|---|
| htmx | 2.x (v1 Step 5) | progressive enhancement (`hx-boost`, typeaheads) |
| marked | 12.0.2 (v1 Step 6) | GFM Markdown → HTML in the document viewer |
| DOMPurify | 3.2.7 (v2 step 4) | sanitize the rendered HTML before `innerHTML` |

Rules:

- Keep each file's license header intact (DOMPurify: Apache-2.0/MPL-2.0,
  marked: MIT, htmx: BSD-2).
- Pin exact versions; update by replacing the file and recording the bump in
  the CHANGELOG. Source of truth for downloads: the project's official dist
  (jsDelivr npm mirror acceptable).
- No other third-party front-end code without amending this ADR.
- Python runtime dependencies remain governed by ADR 0002 (PyYAML, Typer,
  FastAPI stack only).

## Consequences

- The GUI stays functional offline / air-gapped; page loads make no external
  requests (fonts are vendored too, v1.9).
- Sanitization is client-side by design (the server stores raw Markdown —
  the canonical data — and never renders it); DOMPurify guards every
  `innerHTML` sink in the viewer.
- Version bumps are manual and deliberate.
