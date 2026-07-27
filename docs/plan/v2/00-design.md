# maluS v2 — Design (validated)

**Status:** Design approved by Alberto Boffi on 2026-07-27 (this document is
the validated design; the implementation plan lives in the sibling step
files). Invariants of record are unchanged — see §8.

## 1. Goals (as requested)

Six workstreams, requested by Alberto on 2026-07-27:

1. The review **owner** must be clearly visible in the dashboard and
   **transferable**.
2. Fix the bug where **Save draft / Submit copy** take very long to refresh
   the page.
3. The Markdown viewer must render **tables etc. properly (Obsidian-like)**.
4. Every reviewer and the owner see **everyone's comments, colored per
   reviewer**, and the owner can reply/dispose **directly in the viewer**.
5. Opening a comment (e.g. from the dashboard) always shows a **dual panel**
   with the rendered document beside it, scrolled to the anchor.
6. A **major redesign** — organic, beautiful UX/UI, ALUM brand — plus a
   ready-to-paste **logo prompt** for an image generator.

## 2. Decisions taken with Alberto (2026-07-27)

| Topic | Decision |
|---|---|
| Ownership transfer | Current owner **or** global admin may transfer. The transferrer chooses the ex-owner's fate: **removed from the review** or **demoted to reviewer**. Never auto-moderator. |
| Shared document viewer | **One single viewer for everybody**, capabilities gated per role. It replaces the reviewer `edit-copy` editor. |
| Redesign direction | **App-shell with sidebar navigation, organic look, light theme only**, ALUM brand palette/type locked (coral/teal/ink, Space Grotesk + Inter + JetBrains Mono). |
| Technical choices | A1 (persist anchor offsets), B1 (linear freeze matcher), C1 (placeholder post-parse marker injection), vendored DOMPurify — all approved. |

## 3. Root-cause analysis of the slow Save/Submit (workstream 2)

Measured against the code, not guessed:

- `harvest.validate_insertion_only` runs `difflib.SequenceMatcher` at
  **character level** over the whole document (`src/malus/harvest.py:73`).
- `harvest._build_r2b` runs a **second** char-level SequenceMatcher per copy
  (`src/malus/harvest.py:91`).
- `POST /ui/reviews/{id}/edit-copy` calls `validate_insertion_only` once as a
  pre-check, then `svc.harvest` → `build_rtd` re-validates **every** reviewer
  copy and re-builds `r2b` for each (`src/malus/web/router.py:468-485`,
  `src/malus/harvest.py:174-181`).

Net effect: one Save/Submit costs `1 + 2·N_copies` char-level O(n²)-ish
diffs of the full document — seconds-to-minutes on real documents.

**Fix (B1):** a new core helper `_align_ws(baseline, residue)` walks both
strings with two pointers, tolerating only whitespace differences — O(n) —
and produces in a single pass both the freeze verdict and the
residue→baseline offset map. `validate_insertion_only` and `_build_r2b`
delegate to it. Public signatures, server contract, and acceptance semantics
are unchanged.

Rejected alternatives: line-level difflib with local refinement (still
superlinear in pathological cases, more code); async background harvest
(hides latency instead of removing it, introduces job state).

## 4. Owner visibility & transfer (workstream 1)

**UI.**
- Review list (`reviews.html`): an `owner: <name>` chip per row.
- Review dashboard (`review.html`): owner displayed prominently in the
  header block, not as muted text.
- Members page: new "Transfer ownership" section (visible to owner/admin) —
  user picker (reuses the members search), a radio for the ex-owner's fate
  (`remove` | `reviewer`), and a confirm step.

**Service.** `svc.transfer_ownership(session, review, new_owner, old_owner_fate, by)`:
- Authorization: current owner or global admin (reuse `authz` helpers).
- Target must be an **active human** user (`is_ai` → 422; AI may co-own via
  the v1.7 seat but never holds primary ownership).
- Transfer to self → 422 no-op.
- Updates `Review.owner_id`; adds the target as owner-member if not a member;
  applies the fate choice to the ex-owner (remove membership, or switch the
  membership role to reviewer — from then on they may legitimately verify,
  since they are no longer the owner).
- Writes an `AuditLog` entry `transfer_ownership` recording actor, old and
  new owner, and the fate choice.

## 5. Anchor offsets (enabler for workstreams 4–5)

**A1 — persist the baseline character offset at harvest time.**
- New nullable column `rids.anchor_offset` (Alembic migration). `build_rtd`
  already computes `base_off` and discards it; it now persists through
  `sync_rtd_to_review`.
- `rtd.yaml` gains an **optional, additive** `anchor.offset` field
  (import/export lossless round-trip preserved; absent field imports as
  NULL). `docs/spec/rid-schema.md` gets a normative update.
- Existing RIDs stay NULL until the next harvest of their review; the viewer
  falls back to `line_hint` (marker at start of that line).

Rejected: recomputing offsets per page view (re-pays the diff cost the perf
fix removes); client-side recompute from all copies (leaks private copies).

## 6. Unified document viewer (workstream 4) — replaces edit-copy

**Route.** `GET /ui/reviews/{id}/document` (old `edit-copy` URL 303-redirects
to it; all links updated). One component `document-viewer.js` (evolution of
`reviewer-editor.js`), no build step, vendored libs only.

**Rendering (C1 + tables).** The baseline is parsed **clean** by marked
v12; markers are injected as invisible placeholder tokens (the RID id
wrapped in Unicode private-use sentinels, U+E000 rid U+E000) at their
character offsets *before* parsing, then replaced with marker elements in
the resulting HTML *after* parsing — a text-level token cannot break
tables, fences, or lists.
Output is sanitized with **vendored DOMPurify** (new ADR: third vendored
front-end lib after htmx and marked) before `innerHTML`. The document CSS
gains full GFM styling: tables, code fences, blockquotes, task lists —
the "Obsidian-like" reading experience.

**Capabilities per role (server-gated as always; the UI mirrors, never
grants).**
- *Everyone:* rendered document; markers for **all** harvested RIDs colored
  per reviewer (deterministic 8-hue accessible palette derived from the ALUM
  brand); a legend mapping colors to reviewer names; click marker ⇄ comment
  card in the right rail (Word-style margin panel, as today).
- *Reviewer:* adds comments from a text selection (existing popover UX);
  edits/deletes **own** comments. Own comments render from the local copy
  (editable, source of truth) and are reconciled with their harvested RIDs
  by the existing identity match to show RID id/status; other reviewers'
  comments are read-only RID cards. Save draft / Submit keep the existing
  `POST /ui/reviews/{id}/edit-copy` contract (freeze validation + harvest
  unchanged). Private notes stay.
- *Owner/admin:* the comment card embeds the **disposition form inline**
  (posting to the existing `dispose` endpoint); AI-proposal badge and
  Discard-draft exactly as the finding page has today.
- *Verify-capable* (RID's own reviewer, moderator, admin — never AI, never
  owner): verify/reopen actions in the card. `_can_verify` logic is reused,
  not forked.

**Data flow.** The route renders the template with: baseline content, a JSON
payload of RIDs (rid, reviewer, kind, type, severity, status, disposition,
ai_drafted, anchor_offset, line_hint), the caller's role/capability flags,
and — for reviewers — their own copy content. No new JSON API surface.

## 7. Finding focus mode (workstream 5)

The finding page becomes the same viewer in **focus mode**
(`/ui/reviews/{id}/document?focus=<RID>`): left panel auto-scrolls to the
anchor with the focused RID's marker highlighted (others dimmed), right
panel shows the full RID detail plus disposition/verify forms. Clicking a
RID in the dashboard RTD table lands here — the dual panel is always
present. The old `/rids/{rid}` URL redirects to focus mode.

## 8. Invariants (unchanged, restated for the record)

- Closure authority: only the RID's reviewer — or moderator/global admin on
  their behalf — verifies/reopens; **never the owner, never an AI** (the
  `is_ai` guard is absolute; admin superuser per v1.10).
- The GUI holds no authority the server does not enforce.
- Freeze rule D1: reviewer copies are baseline + inserted blocks only.
- No third-party **runtime** Python deps beyond PyYAML/Typer/(FastAPI stack
  per ADR 0002); front-end vendoring (htmx, marked, +DOMPurify) recorded.

## 9. Redesign (workstream 6)

Applied via the ALUM brand identity skill (single source for tokens,
components, logo variants). Light theme only.

- **App shell:** left sidebar navigation — global: Reviews (+ New review),
  admin: Users; within a review: Dashboard / Document / Members. Slim topbar
  with brand mark and account controls. Responsive: sidebar collapses on
  narrow viewports.
- **Organic look:** generous radii, soft layered shadows, coral/teal accents
  on ink/paper, micro-transitions (hover/focus/card-enter), curated empty
  states, progress-to-closure as an organic ring/bar.
- **RTD table redesign:** clickable rows, reviewer color chips consistent
  with the viewer palette, status pills, filters as a compact toolbar.
- **Implementation shape:** one rewritten `app.css` (design tokens extend
  the v1.9 set), Jinja templates migrated page by page to the shell. No
  build step, no CDN.

## 10. Logo prompt (workstream 6 deliverable)

Shipped as `docs/brand/logo-prompt.md`, ready to paste into ChatGPT (or any
image generator). Content (English, final):

> Design a modern, organic logo for "maluS", a document-review web app by
> the brand ALUM. Concept: a document page merging with a review checkmark
> or a soft magnifying lens, drawn as one continuous rounded shape. Style:
> flat vector, minimal, friendly-professional, generous rounded corners,
> no gradients, no 3D, no skeuomorphism. Colors, exactly these: coral
> #FF6F61 as the primary accent, deep teal #0E7C86 as the secondary, ink
> #15181D for dark strokes/text, on white. Typography for the wordmark:
> geometric grotesque similar to Space Grotesk, lowercase "malu" with a
> capital final "S" ("maluS"), the "S" in coral. Deliver: (1) icon-only
> mark, (2) horizontal lockup icon + wordmark; each on white and on ink
> #15181D backgrounds. Composition must stay legible at 24 px, suitable
> for conversion to a clean SVG favicon.

## 11. Error handling

- Freeze violation / parse error on Save-Submit → inline 422 error in the
  viewer (unchanged contract).
- Transfer: to self or to an AI principal → 422 with message; by a
  non-owner/non-admin → 403; unknown target → 404.
- Concurrent dispositions → last-write-wins (unchanged).
- Viewer with NULL offsets (pre-migration RIDs) → line-hint fallback, no
  error.

## 12. Testing

- **Perf fix:** existing suite green; equivalence tests of `_align_ws` vs
  the difflib implementation over generated corpora (tables, fences,
  unicode, ws-only diffs, true violations); a coarse performance guard
  (large doc validates within a bounded time).
- **Transfer:** authz matrix (owner ok, admin ok, reviewer/moderator 403,
  AI target 422, self 422), fate variants, audit row, membership effects.
- **Offsets:** harvest persists offsets; `rtd.yaml` round-trip with and
  without `anchor.offset`; NULL fallback.
- **Viewer/focus routes:** role gating, payload correctness, redirects from
  `edit-copy` and `/rids/{rid}`.
- **End-to-end:** browser verification of each step via the dev-server
  preview (tables render, colors per reviewer, inline disposition, focus
  scroll) before each step is declared done — per the repo DoD.

## 13. Step ordering for the implementation plan

1. Perf fix (core, zero UI risk) — v2 step 1.
2. Owner chip + transfer — step 2.
3. App-shell redesign & design system (so later UI lands on the new skin) — step 3.
4. Anchor offsets + unified viewer — step 4.
5. Finding focus mode (dual panel) — step 5.
6. Polish, logo prompt file, docs/spec updates, release v2.0.0 — step 6.

## 14. Provenance

- Alberto's requests and the four recorded decisions: this session,
  2026-07-27.
- Code evidence: `src/malus/harvest.py`, `src/malus/web/router.py`,
  `src/malus/web/static/reviewer-editor.js`, `src/malus/web/templates/*`,
  `src/malus/db/models.py`, `src/malus/web/static/app.css` (v1.9 tokens),
  vendored `marked` v12.0.2.
- History: Open Brain (openbrain-alum, tag maluS) thoughts #88 (RID schema &
  lifecycle), #92 (v1 architecture), #97 (v1.4 editor), #103/#105 (GUI
  decisions), #108 (v1.5 delete); ADR 0001/0002; `docs/spec/*.md`.
