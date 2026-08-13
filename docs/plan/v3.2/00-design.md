# maluS v3.2 — Design (validated)

**Status:** approved by Alberto Boffi, 2026-08-13 (this session), after his
field-test of the v3.1 closeout viewer. Sixteen feedback points, seven steps.

**Wave numbering vs release numbering.** Folders under `docs/plan/` number
*feedback waves*, not releases — `v3` and `v3.1` both ship inside **3.0.0**.
This wave is different: Alberto decided that **3.0.0 is cut first**, from
`main` as it stands (`docs/plan/v3/06-release.md`), and this wave then ships as
**3.1.0**. So: folder `v3.2` → release **3.1.0**. Do not bump any version
inside steps 01–07; the bump belongs to the release step alone.

## Problem

v3.1 put closeout inside the unified document viewer. Using the result end to
end, sixteen defects and gaps surfaced, in four families:

1. **Chrome** — clicking a comment highlights its marker but does not carry the
   reader to it; the left sidebar cannot be collapsed; the `Save draft` button
   can end up under the sidebar; the reviewer banner on the RTD table is a wall
   of text where a button would do; saving a draft raises the browser's
   "leave site?" dialog.
2. **The comment card** — four different destructive controls (delete /
   withdraw / withdraw-admin / purge) where one bin icon should adapt; a saved
   disposition stays editable in place instead of locking behind an explicit
   `Edit disposition`; `Changes` and `History` are open by default in closeout;
   the reason a reviewer requested changes is buried in the reply string.
3. **Implementation** — the owner edits freely and ticks RID checkboxes
   afterwards, so nothing ties a specific edit to a specific finding; no diff
   is visible while editing; the reviewer's full diff cannot say which comment
   each change came from.
4. **The end of the review** — reopening a verified finding drops it out of the
   closeout queue entirely; reopening a terminated review is an admin-only
   instant action with no way for a member to ask for it; the download row
   shares a line with `Full diff` and degrades to a browser print view.

## Decisions

| Topic | Decision |
|---|---|
| Release order | **3.0.0 first** (`docs/plan/v3/06-release.md`, executed against current `main`), then this wave as **3.1.0**. Alberto's choice: two releases rather than one. Digital signing (`docs/plan/v3/05-signing.md`, [SHOULD], never implemented) is **not** in 3.0.0 — the CHANGELOG text prescribed by `06-release.md` Task 2 must drop its signing sentence and the `docs/how-to/signing-ca.md` link. Recorded as a deviation in that step file. |
| Brand assets | `docs/brand/` holds the **sources** (`alum-logo.png`, 1254², RGBA — the new ALUM lockup; `malus-icon.*` — the app icon from ChatGPT); `src/malus/web/static/` holds the **generated** runtime files. Conversion runs with Pillow (present in the dev venv, 12.3.0) and its output is committed — no build step at serve time, no new runtime dependency. The mark for the 26 px sidebar is the mark-only crop of the lockup. |
| App icon | `icon.svg` (a dark tile with a coral "S") is replaced by an icon derived from the new brand. Wiring stays as today (`base.html:7-9` + `manifest.json`), extended with the PNG sizes a favicon, an apple-touch icon and a maskable PWA icon actually need. Every asset URL keeps `?v={{ asset_v }}` (the v2.0.1 rule). |
| Comment → document | `setFocus` keeps the smooth scroll to the marker and stops calling `scrollIntoView` on the card: the card is brought into view by setting `scrollTop` on `.comments-panel` alone. Today the card's instant `scrollIntoView` cancels the marker's in-flight smooth scroll, which is why clicking a comment highlights the dot without travelling to it. |
| Sidebar | Collapsible on desktop: a toggle sets `.shell.nav-collapsed`, `232px → 56px` (icons only), state persisted in `localStorage`. The `≤900px` branch (`position:fixed; z-index:80`) is untouched. |
| Save draft overlap | `.rev-actions` gets a stacking context above the mobile sidebar branch. Verified at 375 / 768 / 900 / 1280 px. |
| Reviewer CTA | The `.cta-banner` prose in `review.html:12-17` goes; the existing link survives as the single button **`Go to document editor`**, left-aligned where the banner was. |
| Leave-site dialog | Reproduced first, then removed as a *symptom of the dirty flag*: `dirty = false` on every submit of `#rev-form`, not only when the client freeze pre-check passes. The guard against closing the tab with unsaved comments stays — it must simply never fire on maluS's own navigation. |
| One bin | Exactly **one** 🗑 control per comment, in the card and in the RTD row. What it does is decided by role and RID state; nothing else appears in the UI. Its confirm dialog is where a **human global admin** additionally chooses `Delete permanently` (purge) instead of `Withdraw`. Authority is unchanged: the services keep their own guards, the dialog only routes to one of them. |
| Disposition lock | After `Save disposition` the card shows the reply and the disposition as **read-only text** plus an `Edit disposition` button; the fields cannot be edited until it is pressed, and pressing it restores exactly the first-time form. Server rules unchanged (`update_rid` accepts `open\|answered` only, `core.py:562-565`). |
| Card sections | `Changes` becomes a `<details>`; `Changes` and `History` are both **closed by default** in closeout, and focusing a card no longer forces `History` open (`document-viewer.js:689-690`). |
| Rework reason | Promoted from a substring of `reply` to first-class columns on `rids` (`rework_reason`, `rework_by_id`, `rework_at`), with an idempotent Alembic revision that backfills them from the existing `[changes requested by …]` text. The closeout bucket logic reads the column instead of sniffing the string (`router.py:797`). The card renders it as a **callout at the top of the body** for the owner, and it stays in the history timeline. |
| Implementation flow | The closeout editor is **locked** by default. An accepted RID's card carries `Implement comment` — a button of the same weight and position as the card's other actions, replacing the small `Mark implemented` control. Pressing it unlocks the editor **bound to that RID**; the button becomes `Close and associate change`; closing offers a checklist of **duplicate RIDs** to link to the same change, then saves one `DocumentVersion` + one `RidChange` per selected RID. `save_closeout_version(…, rid_ids=[…])` already has this shape — no schema change. |
| One at a time | One implementation session may be open at a time; starting another asks to close the current one first. The session is client state: a reload discards the unsaved text, with a warning. The server stays the authority (a save still requires ≥1 accepted RID and real changed text). |
| Editor diff views | The toolbar becomes **`Render \| Edit \| Changes`**. `Changes` shows, with the existing `.diff-ins` / `.diff-del` colours (`app.css:426-429`), the changes already implemented (baseline ↔ latest version) and, while a session is open, the **live** diff of the not-yet-saved text. Switching between the three states **preserves caret position and scroll** — an explicit requirement, verified manually in the DoD. |
| Live diff engine | **Server-side**: a debounced (~400 ms) POST returns rendered diff HTML from `diffing.py`. One diff algorithm in the project, no new vendored front-end library (ADR 0003). The cost is a local round-trip. |
| Attributed full diff | Because every version now comes from a single implementation session, provenance is knowable: line provenance is carried through the version chain (`equal` propagates it, `insert`/`replace` overwrites it with the current session's RIDs), so the baseline → final diff can badge **each hunk with the RID(s) it came from**. `final.md` and the PDF are unaffected — attribution exists only in the diff views and in `download/diff.html`. |
| Reopen a verified RID | In `closeout`, reopening a `verified` RID moves it to **`implemented`** (*Awaiting verification*), not to `open`. Today `reopen_rid` always targets `open` (`lifecycle.py:144`) and `open` has **no bucket** in the closeout queue (`router.py:797-804`), so the finding vanishes from the workspace. Reopen during `in_review` is unchanged. |
| Reopen a terminated review | New **request** flow: columns `reopen_requested_at`, `reopen_requested_by_id`, `reopen_reason` on `reviews` (the convention `ReviewerCopy.reopen_requested_at` already established, `db/models.py:156`). **Any member** may request, with the same UI and double confirm as `Terminate review`. **Owner or human global admin** approves or rejects. While a request is pending **every member sees it** — dashboard, reviews list and document. `svc.reopen_finalized` (the v3.1 instant admin path) is kept. |
| Downloads | All five routes already send `Content-Disposition: attachment` (`router.py:1169-1252`); the anchors gain `download` and a test asserts the header end to end. The **Downloads row moves to its own line**, below `Full diff` (`review.html:103-120`). |
| PDF | **`Print view` is removed.** When a review was terminated without `malus[pdf]` installed, the PDF is generated and archived **on first download**. Operator prerequisite: `malus[pdf]` (WeasyPrint + Pango) installed in the ALUM server venv — without it, on-demand generation cannot work either, and the button must say so rather than 404. |
| Dependencies | None added at runtime. Pillow is used to generate committed image files, in the dev environment only. ADR 0003 (three vendored JS libs) and ADR 0004 (optional extras) unchanged. |
| Migrations | Two idempotent revisions: rework columns on `rids` (step 03) and reopen-request columns on `reviews` (step 06). Both inspect before altering, per the convention of `b9e4d5f6a701`. |

## What does **not** change

- **Closure authority**: `accept disposition`, `verify` and `request changes`
  belong to the RID's reviewer — or a moderator / human global admin on their
  behalf — never the owner, never an AI (`is_ai` absolute). The bin's confirm
  dialog and the reopen-request approval are routing, not new authority.
- **Traceability by construction**: a closeout save still requires ≥1 accepted
  RID and genuinely changed text; `Mark implemented` still requires ≥1 linked
  `RidChange`. Step 04 makes the link *stronger* (one session, one change), not
  optional.
- The phase state machine `draft → in_review → closeout → finalized`, and every
  RID transition except the reopen target changed in step 06.
- The freeze rule on reviewer copies.

## Testing

Server-side assertions are the rule; the repo has **no JavaScript test
harness** and this wave does not add one — JS-only behaviour carries a manual
verification block instead (the v3.1 convention).

- **Brand**: the generated icon files exist with the expected sizes and the
  `<head>` references resolve.
- **Chrome**: `review.html` contains the button and no longer the banner prose.
- **Card**: exactly one destructive control renders per card and per RTD row
  for each (role, state) pair; a saved disposition renders read-only.
- **Rework**: the migration backfills the columns from legacy reply text; the
  bucket logic uses the column; the callout renders for the owner.
- **Implementation**: a save carries exactly the session's RIDs; duplicates
  linked at close time produce one `RidChange` each.
- **Diff**: live-diff endpoint authz (owner/admin only, closeout only) and
  rendering; provenance attribution over a three-version chain; `final.md` and
  the PDF contain no attribution markup.
- **Lifecycle**: `verified → implemented` on reopen in closeout, and the RID
  lands in `Awaiting verification`; reopen-request authz matrix (member 303,
  non-member 403, owner/admin approve, AI barred), pending banner visible to
  every member.
- **Downloads**: `Content-Disposition` on all five routes; no `print` link
  anywhere; on-demand PDF generation when the artifact is missing.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 0 | `docs/plan/v3/06-release.md` | **Release 3.0.0** from current `main` — E2E, CHANGELOG (no signing), bump, tag | — |
| 1 | `01-brand.md` | new ALUM mark, maluS app icon, favicon and manifest set | 0 |
| 2 | `02-viewer-chrome.md` | scroll to marker, collapsible sidebar, Save-draft overlap, CTA button, leave-site dialog (items 2,3,4,5,6) | 0 |
| 3 | `03-comment-card.md` | one bin, disposition lock, collapsed sections, rework callout + migration (items 7,8,9,10) | 0 |
| 4 | `04-implementation-flow.md` | Implement comment → unlock → Close and associate change, duplicates, one session (item 13) | 3 |
| 5 | `05-diff-views.md` | `Render\|Edit\|Changes`, live diff endpoint, attributed full diff (items 11,12) | 4 |
| 6 | `06-lifecycle.md` | reopen target, reopen request on a terminated review + migration (items 14,15) | 3 |
| 7 | `07-downloads-pdf.md` | attachment audit, download row, print view removed, on-demand PDF (item 16) | 0 |

Implemented in order, one at a time, per `CLAUDE.md`. Steps 1, 2, 3 and 7 are
independent of each other; 4 needs the card work of 3; 5 needs the session
model of 4; 6 needs 3's migration to be in before adding a second one.

**Step files are written just-in-time**, each one immediately before its own
implementation, rather than all seven up front. This design document is the
contract for the wave; a step file is the contract for a step, and writing it
against the tree as it actually stands at that moment keeps its file
references true — v3.1 already had to warn twice that quoted line numbers
drift between steps.

**Cross-step coordination — read before starting any step out of order:**

- Steps **02 and 03 both edit `document-viewer.js`**; 02 touches `setFocus`
  (scroll), 03 touches the card renderer and `setFocus`'s `history.open` line.
  Whichever lands second locates its target **by content, not by line number**.
- Steps **03 and 06 each add an Alembic revision**. The second one to land must
  branch from the first — check `alembic heads` before writing
  `down_revision`, never copy the id quoted in the step file.
- Steps **04 and 05 both rewrite the closeout toolbar** of `document.html`. 04
  introduces the lock, 05 adds the third state; 05 assumes 04's session object
  exists in the JS.
- Step **07 touches `review.html`'s action block**, which step 02 also edits
  (the CTA banner sits directly above it). Same rule: locate by content.

## Sources

- Alberto Boffi's 16 feedback points and 8 design answers, this session
  (2026-08-13): duplicates attachable at close time; caret and scroll preserved
  across editor views; any member may request a reopen; the purge choice lives
  inside the bin's confirm dialog, not in the UI; the CTA button replaces the
  RTD-table banner in place; the ALUM mark is replaced from a transparent PNG;
  PDF guaranteed and `Print view` removed; 3.0.0 cut first, this wave as 3.1.0.
- Current code, read this session:
  `src/malus/web/static/document-viewer.js` (`setFocus` 677-708, dispose form
  574-604, destructive controls 338-506, `cp-implement` 525-536, `beforeunload`
  816-829), `src/malus/web/static/app.css` (shell 69-76, mobile 105-114,
  workbench 250, comments panel 357, diff classes 425-430),
  `src/malus/web/templates/document.html` (role banners 7-57, toolbar 72-75,
  editor 90, actions 99-104),
  `src/malus/web/templates/review.html` (CTA banner 12-17, actions and
  downloads 103-120), `src/malus/web/router.py` (`_document_context` buckets
  791-805, downloads 1169-1252, print 1255-1272),
  `src/malus/services/core.py` (`answer` 511, `update_rid` 540-586,
  `implement` 615, `verify` 638, `accept_disposition` 682,
  `save_closeout_version` 796-831, `reopen_finalized` 900-924,
  `finalize` 961-1006), `src/malus/lifecycle.py` (`reopen_rid` 115-147),
  `src/malus/constants.py` (statuses and transitions 37-78),
  `src/malus/db/models.py` (`ReviewerCopy.reopen_requested_at` 156,
  `RidChange` 231-245, `AuditLog` 265-277).
- Previous waves: `docs/plan/v3/00-design.md` (phases, RID lifecycle, closeout,
  finalize/export), `docs/plan/v3.1/00-design.md` (closeout inside the viewer,
  terminate/reopen, diff views, downloads), ADR 0003, ADR 0004.
- Open Brain `openbrain-alum`, tag `maluS`: #196 (v3 semantics and UX
  decisions), #198 (v3.1 step 01 as implemented), #199 (open steps and
  environment notes: use `.venv/bin/python`, full suite 4–7 min, never pipe
  pytest).
- Brand source: `docs/brand/alum-logo.png` supplied by Alberto on 2026-08-13
  (1254×1254 RGBA, alpha bounding box 198,220–1052,964);
  `docs/brand/logo-prompt.md`; ALUM tokens coral `#FF6F61`, teal `#0E7C86`,
  ink `#15181D`, paper `#F7F8FA`.
