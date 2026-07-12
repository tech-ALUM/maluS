# maluS v1.4 — Reviewer Editor Redesign (A4 rendered + comments panel)

Requested by Alberto Boffi, 2026-07-12. The reviewer's editing surface changes
from a raw split (textarea + live preview) to a **single rendered A4 view** with
a **Word-style comments panel**. The document-review machinery underneath —
freeze rule, harvest, submission contract — is **unchanged**.

## What changes vs v1.3

| Concern | v1.3 | v1.4 |
|---|---|---|
| Reviewer editor | two-column: `<textarea>` + live preview | single **rendered A4 sheet**, no raw column |
| Comments in the doc | literal `{COMM}`/`{SUGG}` text | rendered as **red** inline markers at their anchor |
| Adding a comment | type a block in the textarea | **select rendered text → "Comment"** (Word/Docs style) |
| Reviewing my comments | scroll the raw text | a right **comments panel** (cards); click a card → scroll + highlight the marker ~2s |
| Personal notes | none | a **private per-reviewer note** on each comment (never harvested, never shared) |

## What is unchanged (non-negotiable)

- The reviewer copy is still baseline + inserted `{COMM}`/`{SUGG}` blocks; the
  editor **reconstructs that Markdown on submit** and posts it to the existing
  `POST /ui/reviews/{id}/edit-copy` — same freeze validation + auto-harvest.
- Freeze rule, closure invariant, RID/anchor model: untouched.
- No new runtime dependency (`marked` is already vendored).

## Anchoring model (the robust core)

A comment is anchored to a **character offset into the frozen baseline** (the
insertion point, at the end of the selected phrase). Because the baseline never
changes, this offset is stable across sessions and independent of other
comments. It is:

- how a private note stays attached (its `anchor_key`);
- how the round-trip works: parse `content` → blocks + their baseline offsets on
  load; re-insert blocks at their offsets (ascending) on submit.

Adding a comment maps the DOM selection to the baseline by **text match** (the
selected string + its occurrence index); if the selection spans Markdown
formatting and cannot be matched, it falls back to the end of the containing
block. Rendering does not need offset→DOM mapping: each block is replaced by a
red marker span *before* `marked` runs, so it renders inline where it sits.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-reviewer-editor-redesign.md` | Private-notes store (model + migration + endpoints); A4 rendered editor; select-to-comment; comments panel with jump-highlight + private notes; Markdown round-trip | v1 Step 6, v1.2 Step 2 |

## Global Definition of Done

- `python -m pytest -q` green; a new Alembic migration for the notes table,
  consistent with the models.
- Submit still validates the freeze rule server-side and harvests.
- No new runtime dependency; assets vendored (no CDN).
- JS behavior (select→comment, jump-highlight, note persistence) verified live in
  the browser (TestClient does not run JS).

## Sources

- Design session with Alberto Boffi, 2026-07-12 (this repo, Claude Code):
  rendered A4 only, comments in red, Word-style panel with private notes and
  click-to-jump-and-highlight; add-comment via text selection (approved).
- Builds on `docs/plan/v1/06-gui-editor-reviewer.md` (the editor being replaced)
  and `docs/spec/comment-syntax.md` (block grammar + anchoring).
