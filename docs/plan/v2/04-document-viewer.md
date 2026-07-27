# Step 4 — Anchor offsets + unified document viewer

## Objective

One shared `/document` page for every role: the rendered baseline
(Obsidian-like — tables, fences, lists fully rendered) with **everyone's**
harvested comments as markers colored per reviewer, a Word-style right rail
of comment cards, and role-gated actions in place (reviewer: add/edit own
comments + save/submit; owner/admin: inline disposition; verify-capable:
verify/reopen). Replaces the reviewer edit-copy page.

## Part A — persist `anchor.offset`

`anchor_json` is already a JSON column serialized from `Anchor.to_dict()`
(`src/malus/db/rtd_io.py:101,151`) → adding an `offset` field to the
`Anchor` dataclass flows through DB and `rtd.yaml` with **no migration**.

**Files:** `src/malus/models.py` (Anchor: `offset: int | None = None`,
`to_dict`/`from_dict` additive — key omitted when None, lossless round-trip),
`src/malus/harvest.py` (`_anchor(baseline, offset)` sets it; it already
receives the base offset), `docs/spec/rid-schema.md` (normative note:
optional `anchor.offset`, baseline character offset, absent on pre-v2 RIDs).

- [ ] Failing tests: harvest produces RIDs whose `anchor.offset` equals the
      block's baseline offset; `rtd.yaml` round-trip with and without
      `offset`; DB export/import preserves it; existing RIDs (no key) load
      as `None`.
- [ ] Implement; suite green; commit
      `feat(harvest): persist anchor.offset for viewer anchoring (v2 step 4a)`.

## Part B — the viewer

**Files:**
- Create: `src/malus/web/templates/document.html`,
  `src/malus/web/static/document-viewer.js`,
  `src/malus/web/static/vendor/purify.min.js` (vendored DOMPurify, licence
  header kept; recorded in ADR 0003 at step 6).
- Modify: `src/malus/web/router.py` — new
  `GET /ui/reviews/{review_id}/document` (any member or admin; provides
  baseline, RID payload, capability flags, own-copy content for reviewers);
  `GET /ui/reviews/{review_id}/edit-copy` → 303 to `/document`
  (`POST /edit-copy` **stays** — unchanged save/submit contract).
- Modify: `review.html` (CTA + nav point to Document), `base.html`
  (sidebar link), `app.css` (viewer layout, marker styles per
  `--rev-1…--rev-8`, GFM document CSS: tables, fences, blockquotes,
  task lists).
- Delete: `src/malus/web/static/reviewer-editor.js`, `edit_copy.html`
  (superseded; POST handler renders `document.html` on 422).
- Test: `tests/test_document_viewer.py` (new).

**Interfaces (server → JS):** template embeds
`<script type="application/json" id="viewer-data">` with
`{reviewId, role, isAdmin, canDispose, baseline, myCopy|null, mySubmitted,
rids:[{rid, reviewer, kind, type, severity, status, disposition, comment,
reply, resolution, aiDrafted, offset|null, lineHint, canVerify}],
reviewers:[names in stable order]}`. No new JSON API endpoints.

**Rendering pipeline (C1):**
1. Compute marker positions: harvested RIDs at `offset` (fallback: first
   character of `lineHint`'s line); the reviewer's own **unsaved/local**
   comments come from the parsed copy (existing parse logic carried over
   from reviewer-editor.js) and shadow their matching harvested RID
   (identity match: kind+type+sev+comment) to stay editable.
2. Inject sentinels `U+E000 <key> U+E000` into the baseline string at the
   marker offsets (text tokens — cannot break tables/fences/lists).
3. `marked.parse(...)` → `DOMPurify.sanitize(html)` (keep the sentinel
   chars) → walk text nodes, split at sentinels, insert
   `<button class="marker" data-key style="--rev-color:...">` elements.
4. Right rail: one card per comment in document order — reviewer name +
   color dot, kind/type/sev, body, status/disposition pill; click ⇄ marker
   (scroll + flash, both directions).

**Role capabilities (UI mirrors, server enforces — nothing new to enforce):**
- Reviewer: selection popover to add COMM/SUGG (UX carried from v1.4),
  edit/delete own comments, private notes (existing `/my-notes` endpoints),
  Save draft / Submit via the existing `POST /edit-copy` (hidden
  reconstructed textarea, freeze pre-check kept). After own submit: own
  comments read-only banner (server already refuses via submitted copy —
  verify during implementation; if it does not, keep current behavior and
  note it).
- Owner/admin (human): each card embeds the disposition form (select +
  reply + resolution) posting to the existing
  `POST /rids/{rid}/dispose`; AI-proposal badge + Discard draft as on the
  finding page.
- Verify-capable (own reviewer / moderator / admin, never AI): Verify /
  Reopen(reason) in the card, posting to existing endpoints.
- Retract: own OPEN comment (reviewer) or any (admin) — existing endpoint.

## Deliverables (TDD, part B)

- [ ] Failing route tests: member roles + admin get 200 with correct
      capability flags and full RID payload; non-member 403; AI principal
      gets read-only flags (no dispose/verify capabilities in payload);
      `edit-copy` GET redirects 303 to `/document`; POST contract unchanged
      (a valid save still 303s, a freeze violation still 422s — now
      rendering `document.html`).
- [ ] Implement route + template + JS + CSS; wire links; delete superseded
      files.
- [ ] Browser verification (dev preview, one user per role): tables and
      fences render; markers colored per reviewer with legend; reviewer
      adds/edits/deletes own comment and saves fast; owner disposes inline;
      moderator verifies; AI-principal view is read-only.
- [ ] Suite green; commit
      `feat(web): unified document viewer — all comments, colors, inline disposition (v2 step 4)`.

## Definition of Done

`/document` serves every role from one component; `edit-copy` page gone
(URL redirects); tables/fences/lists render correctly with markers present
inside them; all viewer actions round-trip through the existing endpoints;
suite green; no migration.

## Out of scope

- Real-time multi-user refresh (reload/htmx refresh is enough for v2).
- Comment threads/discussions beyond the existing reply/resolution fields.
- Editing other reviewers' comments (never).

## Sources

- `00-design.md` §5–6 (approved A1 + C1 + DOMPurify); decision table §2.
- `src/malus/web/static/reviewer-editor.js` (parse/popover/notes logic
  carried over), `src/malus/db/rtd_io.py` (anchor_json), `_can_verify`
  in `src/malus/web/router.py:52`.
