# maluS v2.1 — Design (validated)

**Status:** approved by Alberto Boffi, 2026-07-28 (this session). Five UX
requests on top of v2.0.1. Invariants unchanged (closure authority, `is_ai`
guard, freeze rule).

## Decisions taken with Alberto (2026-07-28)

| Topic | Decision |
|---|---|
| Focus UX | Click a comment (marker or card) → focus it; click another → move focus; click elsewhere / ESC → exit. **No explicit enter/exit controls.** Text selection never exits focus. |
| History | **Append-only timeline per RID** rendered from the existing audit log (`target=rid:<id>`). Dispositions stay editable, but every change is a NEW tracked event — history is never rewritten. Saved values render as read-only record, not as a pre-filled form. |
| Card actions | One unified action row per card, **only the buttons the caller's role+status allow** (owner/admin: Dispose/Change disposition + AI Confirm/Discard; verify-capable: Verify/Reopen; reviewer: Delete own). One single editing form. |
| Colors | `users.color` (global default, **admin-only**, Users page) + `review_members.color` (per-review override, owner/admin, Members page). Resolution: member override → user default → deterministic palette. Comments/markers/legend/RTD chips all use the resolved color. |
| New review | Baseline arrives as an **uploaded `.md` file** (multipart), not pasted text. 2 MB limit, UTF-8, `.md/.markdown`. Filename (stem) pre-fills an empty title. JSON API `/reviews` unchanged. |

## Technical notes (evidence)

- Audit rows already exist per RID since v1: `answer`, `update_rid`,
  `discard_draft`, `implement`, `verify`, `reopen`, `retract_comment` log
  `target=f"rid:{rid}"` with actor + ts (`services/core.py`). The timeline
  needs one grouped query, no new table. `answer`/`update_rid` details are
  enriched (changed fields) so new events are self-describing; legacy rows
  render with action + actor + date only.
- Alembic is live (3 revisions) — the color columns are revision 4.
  Both columns nullable → additive, no backfill.
- `python-multipart` is already a dependency (FastAPI `Form(...)` in use).

## Steps

| # | File | Scope |
|---|---|---|
| 1 | `01-viewer-ux.md` | click-based focus, per-RID history timeline, unified role-filtered actions |
| 2 | `02-member-colors.md` | color columns + resolution + Users/Members pickers + consumption |
| 3 | `03-upload-baseline.md` | new review via .md upload |
| 4 | `04-release.md` | CHANGELOG, bump 2.1.0, tag, push |

## Sources

- Alberto's requests + the two recorded decisions, this session (2026-07-28).
- `src/malus/services/core.py` (audit calls), `alembic/versions/`,
  `src/malus/web/static/document-viewer.js`, `src/malus/db/models.py`.
