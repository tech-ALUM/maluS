# maluS v2 — Overview & Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans
> (inline) or superpowers:subagent-driven-development to implement, one step
> file at a time, in order. Steps use checkbox (`- [ ]`) syntax for tracking.

Requested by Alberto Boffi, 2026-07-27 (this repo, Claude Code). Validated
design: [`00-design.md`](00-design.md). Six workstreams: visible/transferable
owner, fast Save/Submit, Obsidian-like Markdown rendering, unified per-role
document viewer with colored comments and inline disposition, always-dual-panel
finding view, ALUM app-shell redesign + logo prompt.

**Goal:** ship v2.0.0 of the maluS web app implementing the six validated
workstreams with no regression of the review invariants.

**Architecture:** unchanged v1 stack (FastAPI + SQLModel/SQLite + Jinja +
htmx + vanilla JS, no build step). New: linear freeze matcher in the harvest
core; `anchor.offset` persisted inside the existing `anchor_json` JSON column
(no migration); one `document-viewer.js` component replacing
`reviewer-editor.js`; app-shell (sidebar) skin on ALUM brand tokens; vendored
DOMPurify beside htmx/marked.

**Tech stack:** Python 3.12, FastAPI, SQLModel, Jinja2, htmx, marked v12,
DOMPurify (vendored), pytest.

## Global constraints

- Closure authority: reviewers + moderators + global admin, **never the
  owner, never an AI** (`is_ai` guard absolute) — unchanged.
- The GUI holds no authority the server does not enforce — unchanged.
- Freeze rule D1 (copies = baseline + inserted blocks only) — unchanged.
- No build step, no CDN at runtime; front-end libraries are vendored.
- No new third-party Python runtime deps.
- Conventional Commits; every step ends with `python -m pytest -q` green.
- Light theme only; ALUM brand palette/type per the alum-brand-identity skill.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-perf-linear-freeze.md` | linear `_align_ws` matcher replaces char-level difflib in freeze validation + offset mapping | — |
| 2 | `02-owner-transfer.md` | owner chip in lists/dashboard; `transfer_ownership` service + Members UI | — |
| 3 | `03-app-shell-redesign.md` | sidebar app shell, organic ALUM restyle of all existing pages | — |
| 4 | `04-document-viewer.md` | `anchor.offset` persisted; unified `/document` viewer (all comments, colors, inline disposition); replaces edit-copy | 1, 3 |
| 5 | `05-finding-focus.md` | finding page → viewer focus mode (`?focus=RID`), dual panel always | 4 |
| 6 | `06-release.md` | logo prompt file, spec/ADR/docs updates, CHANGELOG, v2.0.0 | 1–5 |

## Global Definition of Done

- `python -m pytest -q` green after every step; no schema migration in the
  whole release (offset lives in `anchor_json`).
- Save draft / Submit copy respond in sub-second server time on large
  documents (perf guard test in step 1).
- Every page renders inside the new app shell; the document viewer shows all
  reviewers' comments in distinct colors with role-gated actions; the finding
  view is always dual-panel.
- Browser verification (dev-server preview) performed for steps 2–5 before
  marking them done.

## Sources

- Design session with Alberto Boffi, 2026-07-27 (this repo, Claude Code) —
  decisions recorded in `00-design.md` §2.
- Code evidence: `src/malus/harvest.py`, `src/malus/web/router.py`,
  `src/malus/web/accounts.py`, `src/malus/api/authz.py`,
  `src/malus/db/{models.py,rtd_io.py}`, `src/malus/web/static/*`,
  `src/malus/web/templates/*`.
- History: Open Brain (openbrain-alum, tag maluS) #88, #92, #97, #103, #105,
  #108; ADR 0001/0002; `docs/spec/*.md`.
