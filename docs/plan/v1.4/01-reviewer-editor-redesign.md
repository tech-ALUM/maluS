# Step 1 — Reviewer Editor: A4 rendered view + comments panel + private notes

## Objective

Replace the reviewer's two-column raw editor with a single rendered **A4** view
where comments show in **red**, a right **comments panel** lists them (click →
scroll + highlight the marker for a few seconds), each comment carries a
**private per-reviewer note**, and comments are added by **selecting rendered
text**. The Markdown copy is reconstructed on submit; the server contract is
unchanged.

## Deliverables

### Private-notes store (backend, TDD)
- [x] `ReviewerNote(id, review_id, user_id, anchor_key: str, body: str)` with
      `UniqueConstraint(review_id, user_id, anchor_key)` in `db/models.py`.
- [x] An **Alembic migration** creating the table (consistent with the models).
- [x] Repo helpers: list a reviewer's notes for a review; upsert one by
      `anchor_key`; (empty body deletes it).
- [x] `GET /ui/reviews/{id}/my-notes` → `{anchor_key: body}` JSON for the current
      user; `PUT /ui/reviews/{id}/my-notes` (`anchor_key`, `body`) upserts one.
      Reviewer-only for that review; a user only ever sees/writes **their own**
      notes.
- [x] Tests: save + read back; scoping (another user cannot read/write them; a
      non-member is refused); empty body clears a note.

### Rendered A4 editor (frontend)
- [x] `edit_copy.html` rewritten: no textarea column; an **A4 sheet** (paper
      look, ~A4 width, centered, generous vertical space) holding the rendered
      document, plus a right **comments panel**; a hidden `content` field and the
      `Submit copy` button; the `data-baseline` is still provided.
- [x] `reviewer-editor.js` (new; `marked` vendored): on load, **parse** `content`
      into the baseline + a list of comments (kind, params, body, baseline
      offset); render the A4 by replacing each block with a **red marker span**
      before `marked` runs; build the panel.
- [x] **Select → comment**: selecting text in the sheet shows a floating
      "Comment" action → a small form (type/sev + body; for `{SUGG}` prefill
      `old` = selection, enter `new`). Anchor by text-match (selected string +
      occurrence index) with a containing-block fallback. Edit/delete a comment
      from its panel card or marker.
- [x] **Comments panel** (Word style): one card per comment (body + quoted
      anchor). Clicking a card scrolls the sheet to the marker and **highlights
      it ~2s**. Each card has an expandable **private note** field that loads
      from / saves to `/my-notes` (debounced), keyed by the comment's
      `anchor_key`.
- [x] **Submit**: reconstruct the Markdown (baseline + blocks at ascending
      offsets) into the hidden `content`, keep the client freeze pre-check, post
      to the existing `POST /ui/reviews/{id}/edit-copy`.
- [x] CSS for the A4 sheet, red comment markers/highlight, and the panel (ALUM
      palette).

## Key behaviors

- `anchor_key` is the comment's baseline character offset (stable; the baseline
  is frozen), so a private note survives edits to the comment body and other
  comments coming and going.
- Rendering avoids offset→DOM mapping by substituting marker spans into the
  source before `marked`; only the *add* path maps a selection to the source, by
  text match with a block-level fallback.
- Nothing about submission changes: the reconstructed Markdown still passes
  `validate_insertion_only` (only blocks inserted into the frozen baseline) and
  triggers the same server-side harvest.

## Definition of Done

A reviewer opens their copy as a single rendered A4 page; existing comments show
in red with a panel listing them; selecting text adds a comment; clicking a panel
card scrolls to and briefly highlights the marker; a private note typed on a card
persists for that reviewer only; submitting still validates the freeze rule and
harvests; server suite green; JS flows verified live.

## Out of scope

- Pagination of the A4 sheet (continuous single sheet; print/paged view later).
- Threaded discussion / replies on comments (owner disposition stays in the RTD).
- Rich-text editing of the document (freeze rule: insert-only).
- Sharing private notes or promoting a note into the RID.

## Deviations

Recorded in `memory/decisions/2026-07-12-v1.4-step-01-reviewer-editor.md`.

- **Two editors coexist**: the reviewer uses the new `reviewer-editor.js`; the
  owner's *implement* editor keeps `editor.js` + `.editor-grid`/`.preview`
  (unchanged). Only the reviewer surface was redesigned.
- **Rendering avoids offset→DOM mapping**: comment blocks are substituted into a
  copy of the baseline as red `<span class="cmt">` markers *before* `marked`
  runs (marked passes inline HTML through); the marker shows the COMM body or the
  SUGG `old→new` in red.
- **Add path**: `selectionOffset()` maps a DOM selection to a baseline offset by
  text-match (selected string + occurrence index counted in the rendered text
  before the selection); a no-match falls back to end-of-baseline.
- **`anchor_key` = the baseline offset (as a string)**; private-note cards
  debounce-save via `PUT /my-notes`. Notes routes live in `router.py` beside
  edit-copy (reviewer-gated), JSON on GET / 204 on PUT; new `ReviewerNoteRepo`.
- **Migration** `f1a2b3c4d5e6` creates `reviewer_notes`; `test_db_migration`
  asserts table-name parity with the models.
- **JS is required** for the editor: the hidden `#content-src` (name=`content`)
  carries the reconstructed Markdown; a no-JS submit would post baseline-only and
  be rejected safely. Server contract unchanged.
- **Live-verified** end-to-end in a browser: A4 render + red markers + panel,
  card→jump+flash, private-note persistence, select-to-comment anchoring
  (block inserted exactly after the selected phrase), submit→harvest (2 COMM
  RIDs). The screenshot tool timed out (renderer); DOM snapshots used as proof.

## Sources

- Design session with Alberto Boffi, 2026-07-12 (approved: rendered A4, red
  comments, Word-style panel, private notes, select-to-comment).
- Replaces the editor from `docs/plan/v1/06-gui-editor-reviewer.md`; block
  grammar + anchoring from `docs/spec/comment-syntax.md`; current implementation
  in `src/malus/web/templates/edit_copy.html` + `src/malus/web/static/editor.js`
  + `src/malus/web/router.py` (`edit_copy_page` / `submit_copy`).
