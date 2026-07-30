# maluS v3.1 — Design (validated)

**Status:** approved by Alberto Boffi, 2026-07-30 (this session), after his
field-test feedback on the v3 closeout cycle. Additive UX refactor on top of
v3 steps 01–04 (`main` = 2df818c) — no change to the RID state machine, the
phase state machine, or the closure-authority invariant.

"v3.1" names this **feedback wave**, not a release: the last tag is `v2.3.0`
and 3.0.0 was never cut, so these four steps land before v3's `06-release.md`
and ship inside the single **3.0.0** bump.

## Problem

v3 shipped closeout as a **separate page** (`/ui/reviews/{id}/closeout`) with
its own two-column editor and its own findings list. Using it, four defects
surfaced:

1. The owner works in two places at once — the closeout page to edit, the
   document viewer to read comments — and the closeout page splits the width
   between textarea and preview, so neither shows enough document.
2. The end of the review is unreachable in practice: **Finalize** exists but
   nothing can undo it, so nobody dares press it.
3. The dashboard renders the **Full diff** button twice, and the only diff
   available is the compact one (±3 lines) — there is no way to read the
   changed document as a whole.
4. A terminated review yields `final.md`, `report.md` and the PDF, only from
   the review dashboard — not the original baseline, not a readable diff
   artifact, and not from the reviews list where a member starts.

## Decisions

| Topic | Decision |
|---|---|
| Closeout home | The closeout workspace **moves into the unified document viewer** (`/ui/reviews/{id}/document`). `closeout.html` and `static/editor.js` are deleted; `GET /ui/reviews/{id}/closeout` becomes a 303 redirect to the document (same treatment `GET /implement` got in v3). `POST /ui/reviews/{id}/closeout` keeps its URL and its service call — only its caller changes. |
| Centre column | In phase `closeout` the sheet renders the **latest `DocumentVersion`**, not the baseline, and carries a two-state toolbar **`Render \| Edit`**. `Edit` swaps the sheet for a full-width textarea and is offered only to a principal that may write (`canDispose`-style: owner or global admin, `is_ai` barred). No inline comment markers in closeout: comment anchors are baseline offsets and the latest version has moved past them — the per-comment `Changes` diff in the card is the anchor now. |
| Render safety | The closeout render goes through `marked` **and DOMPurify**, like the review-phase sheet. This closes the known v3 minor (the old `editor.js` preview called `marked` unsanitized — self-XSS on the owner). |
| Side panel | Stays on the **right** (`.workbench` = doc `1fr` + panel `340px`, unchanged). Alberto's feedback said "left"; moving it was considered and rejected, because `.workbench` is shared by every role and every phase — flipping the columns would restyle the review phase too, for no gain in closeout. The decision is "the side column", and it is already on the right. In phase `closeout` its content switches from the flat comment list to the **work queue** — the four groups the workspace already had (`Rework requested`, `To implement`, `Awaiting verification`, `Verified`) — for **every** role, not just the owner, plus a collapsed `<details>` group **`Closed — no change`** holding the rejected and deferred findings so nothing silently disappears. Withdrawn findings stay out of the viewer payload exactly as today (`_document_context` skips them unless focused). |
| Queue items | The queue items are the existing `cp-card` component rendered **collapsed**: head = reviewer chip + RID + status pill + truncated comment; expanding reveals body, owner reply, resolution, history, the `Changes` diff section and the role's action buttons (Verify / Request changes / Mark implemented). `?focus=RID` expands its card as today. |
| Edit↔RID picker | Fused into the queue: cards in `To implement` and `Rework requested` carry a `name="rids"` checkbox. The panel already lives inside `#rev-form`, so in closeout that form posts `content` + `rids[]` to `POST /closeout`; the submit reads **`Save version & link (N)`** and is disabled while `N = 0` or the text is unchanged (the service rejects both cases anyway — the UI just stops the round-trip). |
| Mark implemented | HTML forbids nested forms, so the per-RID form of `closeout.html` becomes a `resolution` text input + button inside the card, submitted through the viewer's existing detached-form `post()` helper (the mechanism Verify / Accept / Reopen already use). Redirect target becomes `/document?focus={rid}`. |
| Comment popover | Gated on `phase == 'in_review'`. Today a reviewer whose copy is not submitted can still open the selection popover in closeout; the server refuses the save, but the affordance should not exist. |
| Terminate | The owner's button is relabelled **`Terminate review`** and also appears in the document's closeout toolbar once the gate holds. Domain vocabulary is unchanged: the phase stays `finalized`, the service stays `svc.finalize`, ADR/spec/CHANGELOG wording stays — only the button label and its confirm text change. The gate itself is already exactly the required one (`svc.finalize_gate`: every accepted RID `verified`, rejected/deferred `closed`, withdrawn ignored). |
| Reopen a terminated review | New service `svc.reopen_finalized`: `finalized → closeout`, `_require_phase(FINALIZED)`, **human global admin only** (`is_admin and not is_ai`, enforced in the service as well as the route), audit-logged, double confirm, in the dashboard `⋯` menu. The superseded `is_final` version stays in history; re-terminating adds a new final version and a new PDF artifact — `ArtifactRepo.get` already orders `created desc`, so the newest wins. |
| Diff views | `html_diff` gains `context: int \| None = 3` (`None` → whole document via `get_opcodes()` instead of `get_grouped_opcodes()`) and `line_numbers: bool = False` (two gutter `<span>`s per row, old and new). Signature stays backward-compatible, so the per-RID `Changes` section and its tests are untouched. `/ui/reviews/{id}/diff` gains a `Compact \| Full` toggle via `?view=` — server-side links, zero JS, shareable URL, consistent with the v2.2 filter chips. |
| Duplicate button | The owner-block `Full diff` link (`review.html:34`) is deleted. The all-members block (`review.html:98`, `phase in ('closeout','finalized')`) already covers owner, reviewer and moderator. |
| Downloads | Two new member-only, finalized-only routes: `download/baseline.md` (the frozen original) and `download/diff.html` (self-contained: inline CSS, header with review id + version ordinals, `html_diff(context=None, line_numbers=True)`, rendered from a Jinja template so no markup lives in Python). Full set becomes **`baseline.md · final.md · diff.html · report.md · PDF`** (or `Print view` when `malus[pdf]` was absent at finalize). |
| Downloads entry points | The dashboard download row is extended, and finalized rows in `/ui/reviews` gain a `⋯` menu with the same five links (`reviews_page` grows `status` + `has_pdf` per row). |
| Dependencies | None added. No new vendored JS (ADR 0003 untouched); the PDF extra rule (ADR 0004) unchanged. |
| Migration | None. No schema change, no data backfill. |

## What does **not** change

- The RID state machine and the phase state machine of v3 §RID lifecycle.
- **Closure authority**: `accept disposition`, `verify`, `request changes`
  belong to the reviewer — or moderator / human global admin on their behalf —
  never the owner, never an AI (`is_ai` absolute). The new `reopen_finalized`
  is an admin phase action, not a closure verdict, and carries the same
  `is_ai` bar.
- Traceability by construction: a closeout save still requires ≥1 accepted RID
  and a real text change; `Mark implemented` still requires ≥1 linked change.

## Testing

Web: closeout save posted from the document page (happy path + both rejections
re-render with the unsaved text); `GET /closeout` redirects 303; mark-implemented
from a card; a reviewer cannot open the comment popover in closeout; queue
grouping per role. Authz: `reopen_finalized` — admin 303, owner 403, AI admin
403, wrong phase 409. Regression: the dashboard contains exactly one link to
`/diff`. Diff: `context=None` keeps every line, line numbers rendered and
escaped, compact mode byte-identical to v3 for the same input. Downloads: five
routes 200 with the right `Content-Disposition`, 409 before finalize, 403 for
a non-member.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-closeout-in-document.md` | viewer closeout mode: Render/Edit toolbar, queue panel, collapsed cards + RID checkboxes, save + mark-implemented wiring, delete `closeout.html`/`editor.js`, popover gate | v3 01–03 |
| 2 | `02-terminate-reopen.md` | `Terminate review` label + document toolbar placement, `svc.reopen_finalized`, admin route + `⋯` entry | v3 04 |
| 3 | `03-diff-views.md` | `html_diff(context=None, line_numbers=…)`, `?view=` toggle, delete the duplicate dashboard button | v3 03 |
| 4 | `04-downloads.md` | `baseline.md` + `diff.html` routes, dashboard row, `⋯` menu in the reviews list | 3 (diff renderer) |
| 5 | `05-one-schema-authority.md` | Alembic becomes the single schema authority: serving path stops creating schema, backfills move into revisions, models↔migrations parity guard. Added 2026-07-30 after the production incident of that day; not part of the original UX wave. | — |

Steps 2–4 are independent of each other and of step 1; step 1 is the large one.
Implemented in order, one at a time, per `CLAUDE.md`.

**Cross-step coordination — read before starting any step out of order:**

- Steps **02 and 03 both edit the owner-actions block of
  `src/malus/web/templates/review.html`** (02 relabels the Finalize button
  around line 36; 03 deletes the duplicate `Full diff` link at line 34).
  Whichever lands second must locate its target **by content, not by the line
  numbers quoted in its own file** — they will have shifted.
- Step **02's last task depends on step 01** (it puts the Terminate button in
  the closeout toolbar that step 01 builds). That task is deliberately last and
  carries its own fallback; the rest of step 02 stands alone.
- Step **04 consumes the `html_diff` signature step 03 produces**
  (`context: int | None = 3, line_numbers: bool = False`) and the gutter class
  `.diff-ln` it emits. Do not start 04 before 03.
- Step **05 touches the boot path of a running production service** and is
  independent of the four UI steps. It can be scheduled whenever, but never
  interleaved task-by-task with them.

**Step 5 was added on 2026-07-30**, after the production incident described in
its own file: the server went down because `create_all` and Alembic each
believed they owned the schema. Commit `a5a0125` stopped the bleeding by making
revision `b9e4d5f6a701` skip objects that already exist; step 5 removes the
double authority that made the collision possible. It is independent of steps
1–4 and touches no UI.

## Sources

- Alberto Boffi's v3.1 feedback (4 points) and 7 design answers, this session
  (2026-07-30): closeout merged into the document view with a Render/Edit
  toggle; side panel stays right; queue and RID picker fused; two-state centre
  column; `Terminate review` + admin reopen; unified inline diff with line
  numbers; download set and `⋯` menu in the reviews list.
- Current code: `src/malus/web/templates/closeout.html`,
  `src/malus/web/templates/document.html`,
  `src/malus/web/templates/review.html:34,98`,
  `src/malus/web/static/document-viewer.js` (`cardEl`, `renderSheet`, `post`),
  `src/malus/web/router.py` (`_document_context` 678, `diff_page` 820,
  `_closeout_context` 973, downloads 1109–1152),
  `src/malus/services/core.py` (`implement` 615, `reopen_review` 889,
  `finalize_gate` 911, `finalize` 935), `src/malus/diffing.py`,
  `src/malus/repo/repositories.py:321` (`ArtifactRepo`).
- v3 baseline: `docs/plan/v3/00-design.md` (phases, lifecycle, closeout
  workspace, finalize/export), ADR 0003 (vendored front-end libs), ADR 0004
  (optional extras).
- Open Brain `openbrain-alum` thought #196 (2026-07-30) — v3 status, UX
  decisions from Alberto's field tests, known minors (unsanitized closeout
  preview, `asset_v` still 2.3.0).
