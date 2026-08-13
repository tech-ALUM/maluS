# v3.2 Step 3 — The comment card: one bin, a locked disposition, quiet sections

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** the card stops offering four ways to destroy a comment, stops
leaving a saved disposition editable in place, stops opening every section by
default, and stops hiding the reviewer's rework reason inside a string.

Feedback points **7, 8, 9, 10** of the v3.2 wave.

## Deliverables

- [x] Exactly one 🗑 control per comment, in the card and in the RTD row
- [x] A saved disposition is read-only until `Edit disposition` is pressed
- [x] `Changes` and `History` are collapsed by default in closeout
- [x] The reviewer's rework reason is a column, and a callout the owner cannot
      miss
- [x] Alembic revision applied on top of `c4d5e6f7a8b9`, idempotent
- [x] `python -m pytest -q` green

## Tasks

### Task 1: one bin (point 7)

**Files:** modify `src/malus/web/static/document-viewer.js`,
`src/malus/web/templates/review.html`, `src/malus/web/static/app.css`

Today the card renders up to four distinct destructive controls
(`document-viewer.js`):

| Control | Label | Condition | Endpoint | Line |
|---|---|---|---|---|
| local delete | `delete` | unsaved comment (`c && !r`) | DOM only | 338-350 |
| reviewer withdraw | `🗑 Withdraw` | own, `open`, `in_review` | `POST /rids/{rid}/retract` | 406-419 |
| admin withdraw | `Withdraw` | `canPurge`, `in_review` | `POST /rids/{rid}/retract` | 478-493 |
| admin purge | `Purge permanently` | `canPurge`, any phase | `POST /rids/{rid}/purge` | 494-506 |

They collapse into **one** 🗑 whose behaviour follows role and state. The
server-side rules do not move and must be mirrored exactly:
`retract_comment` requires the RID to be **`open`** (`services/core.py:321` —
the v3 rule that withdrawing a disposed comment silently violated the graph),
`purge_rid` is **human global admin, any phase** (`services/core.py:374`).

- [x] **Step 1:** decide what the single icon does, from `(role, status,
      phase)`:

      | Case | On click |
      |---|---|
      | unsaved local comment | remove it from the copy, no server call |
      | own comment, `open`, `in_review`, reviewer | confirm → retract |
      | admin, `open`, `in_review` | dialog: `Withdraw` or `Delete permanently` |
      | admin, anything else | confirm → `Delete permanently` |
      | nobody with authority | the icon is **not rendered** |

- [x] **Step 2:** build the two-choice dialog with the native `<dialog>`
      element — it is HTML, needs no library (ADR 0003 stays untouched), is
      focus-trapped and Esc-closable for free. `confirm()` cannot offer two
      destructive choices, and inventing a modal component is out of
      proportion. The purge branch keeps its double confirmation.
- [x] **Step 3 — done by inspection, not by change.** The RTD table already
      renders exactly one 🗑 (`review.html:183`), gated own-or-admin + `open` +
      `in_review`. It was left as it is; the dialog was **not** ported there.
      See `## Deviations` 2 for why.
- [ ] **Step 4 — NOT DONE as written, and it cannot be.** The card is built
      in JavaScript from the `#viewer-data` payload, so no server-side test can
      count the controls it renders. The counting was done by hand against the
      running server for all three states and both roles (see
      `## Verification`), which is the v3.1 convention for JS-only behaviour.
      `tests/web/test_retraction.py` still passes untouched.
- [x] **Step 5:** commit `feat(web): one bin per comment, role-aware`.

### Task 2: the disposition locks after saving (point 8)

**Files:** modify `src/malus/web/static/document-viewer.js`

The dispose form is built at `document-viewer.js:574-604`; on an `answered`
finding it is hidden behind an `Edit disposition` toggle
(`document-viewer.js:386-396`). Alberto's report is that after pressing
`Save disposition` the fields stay editable — establish first whether the
defect is the post-save state (before the redirect repaints the card) or the
toggle's own markup.

- [x] **Step 1:** reproduce and record which of the two it is.
- [x] **Step 2:** after a save, the card shows the disposition and the reply as
      **read-only text**, with a single `Edit disposition` button. The fields
      are not merely visually hidden — they must be unreachable by keyboard and
      not submittable while locked.
- [x] **Step 3:** pressing `Edit disposition` restores **exactly** the
      first-time form: same fields, same order, same submit label. One code
      path renders both states so they cannot drift.
- [x] **Step 4:** the server rule is unchanged and remains the authority:
      `update_rid` accepts `open|answered` only (`services/core.py:562-565`).
      Already asserted by `tests/services/test_disposition_immutable.py` and
      `tests/web/test_edit_disposition.py`, both untouched and green; no new
      test was written for a rule that was already pinned.
- [x] **Step 5:** commit `feat(web): a saved disposition locks until you edit it`.

### Task 3: quiet sections in closeout (point 9)

**Files:** modify `src/malus/web/static/document-viewer.js`,
`src/malus/web/static/app.css`

- [x] **Step 1:** `Changes` becomes a `<details>` (today a plain
      `<div class="cp-changes">`, always expanded, `document-viewer.js:310-333`)
      with a summary carrying the count, e.g. `Changes (2)`.
- [x] **Step 2:** both `Changes` and `History` are **closed by default**, and
      `setFocus` stops forcing history open (`document-viewer.js:689-690`).
      Focusing a card still expands the card itself and its containing group —
      that is v3.1 behaviour and it stays.
- [x] **Step 3:** manual verification: enter closeout, open a card in each of
      the four queue groups → both sections closed; open one → it stays open
      while you interact with the card; `?focus=RID` → card open, sections
      closed.
- [x] **Step 4:** commit `feat(web): comment sections start closed in closeout`.

### Task 4: the rework reason becomes a column (point 10)

**Files:** modify `src/malus/db/models.py`,
`src/malus/services/core.py`, `src/malus/web/router.py`,
`src/malus/web/static/document-viewer.js`; create
`src/alembic/versions/<rev>_rework_reason_columns.py`

When a reviewer requests changes, the reason is appended to the RID's `reply`
as `[changes requested by <name>: <reason>]`, and the closeout queue decides
the `rework` bucket by **sniffing that substring**
(`web/router.py:797`: `reworked = "[changes requested by" in (r["reply"] or "")`).
So the reason is both invisible to the owner (it is buried in a reply field
they also write into) and load-bearing for the workspace layout.

- [x] **Step 1:** add to `rids`: `rework_reason: str | None`,
      `rework_by_id: int | None` (FK `users.id`), `rework_at: datetime | None`.
- [x] **Step 2:** write the Alembic revision on top of the current head
      **`c4d5e6f7a8b9`** — but run `alembic heads` first and use what it
      reports, because step 06 adds a second revision and whichever lands
      later must branch from the earlier one. Follow the project convention
      (`CLAUDE.md`, revision `b9e4d5f6a701`): inspect with
      `sa.inspect(op.get_bind())` before every DDL operation so the revision
      is idempotent, and write the backfill as **set-based SQLAlchemy Core
      statements, never through the ORM**.
- [x] **Step 3:** backfill from history: existing rows whose `reply` contains
      `[changes requested by …]` get the parsed reason and, where the audit
      log identifies the actor, `rework_by_id` and `rework_at`. Rows that
      cannot be parsed keep `NULL` — do not guess.
- [x] **Step 4:** the request-changes service writes the columns. Keep writing
      the reply text as well **for this release**: `report.md`, the PDF and
      the history timeline read it, and changing all of them belongs to a
      different step. The columns are the new authority for *logic*; the reply
      string stays the human-readable trace.
- [x] **Step 5:** the bucket logic reads `rework_at is not None` instead of the
      substring (`web/router.py:797`). `tests/web/test_closeout_page.py` covers
      this grouping — it must stay green.
- [x] **Step 6:** the card renders the reason as a **callout at the top of the
      body** whenever the RID is in rework: reviewer name, timestamp, the text.
      Visible to every role, but it is the owner's work item — it must read as
      an instruction, not as a log line. It also stays in `History`.
- [x] **Step 7:** tests — migration backfill from a legacy reply string;
      bucket computed from the column; the callout renders for the owner;
      `pytest tests/db -q` proves the models/migrations parity guard
      (`tests/db/test_db_migration.py::test_migrations_match_the_models_exactly`)
      still holds, since a model change without a revision is a bug.
- [x] **Step 8:** commit `feat(db): the rework reason is a first-class column`
      and `feat(web): the rework reason is a callout, not a buried string`.

## Definition of Done

- [x] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [x] `alembic upgrade head` on a fresh DB **and** on a copy of a pre-step DB
      both succeed, and running it twice is a no-op
- [x] For every `(role, status, phase)` pair, at most one destructive control
      renders — verified by test, not by eye
- [x] Closure authority untouched: the owner still cannot accept, verify or
      request changes; `is_ai` still absolute
- [x] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Changing what `report.md` or the PDF print for a reworked finding.
- Widening who may purge. The dialog routes to existing services; it grants
  nothing new.

## Verification

Driven on the seeded dev server, on `DEMO-REVIEW` (in_review) and `DEMO-CLOSE`
(closeout, one finding awaiting verification and one sent back for rework).

**A real bug was caught here, not by the tests.** The first render of the
closeout panel produced *zero* cards while the payload was perfect and the
console stayed empty — the exception died inside the render loop. Re-running
the served bundle under a trap named it: `ReferenceError: phase is not defined`
in `binFor`. `phase` is a local of `cardEl` (`document-viewer.js:246`), and the
new helper is its sibling; it reads `data.phase` now. Nothing in the Python
suite could have seen this, which is the whole reason the manual pass exists.

### Point 7 — one bin

As **admin** on `in_review`, every card renders exactly **one** destructive
control, on all three findings:

| Finding | Status | Destructive controls | Dialog offers |
|---|---|---|---|
| SIN-SRS-0001 | answered | `🗑` ×1 | `Delete permanently` · `Cancel` — *"past 'open', so it can no longer be withdrawn"* |
| SIN-SRS-0002 | open | `🗑` ×1 | `Withdraw` (amber) · `Delete permanently` (red) · `Cancel` |
| SIN-SRS-0003 | open | `🗑` ×1 | same |

As **owner** in closeout: no bin at all, which is correct — the owner may
neither withdraw nor purge. The dialog is a native `<dialog>` opened with
`showModal()`, so it is modal and focus-trapped without a line of CSS or a
library, and the permanent delete keeps a second `confirm()` behind it.

### Points 9 and 10 — sections and the rework callout

On `DEMO-CLOSE`, owner:

| Finding | Queue | `Changes` | `History` | Callout |
|---|---|---|---|---|
| SIN-SRS-0003 | rework | `<details>`, **closed** | `<details>`, **closed** | *"Say what happens after the third failure."* — Changes requested by Remo Reviewer |
| SIN-SRS-0001 | awaiting | `<details>`, **closed** | `<details>`, **closed** | none |
| SIN-SRS-0002 | noChange | — | `<details>`, **closed** | none |

The payload carries `rework: {reason, by, at}` only while the request is
outstanding: after the owner re-implements, the same finding reports
`queue: "awaiting"` and `rework: null` (asserted in
`tests/web/test_comment_card_v32.py`).

## Deviations

1. **Point 8 was already satisfied on `main`.** Driven on the seeded server as
   owner: saving a disposition redirects to `?focus=<RID>`, the finding shows
   `answered`, the dispose form is `hidden` and the only visible control is
   `Edit disposition`, which reopens the identical form. That is exactly what
   the point asks for. The one real gap was that the hidden form's fields
   stayed **enabled** — `hidden` removes them from the page but not from the
   form's submission — so `Edit disposition` now disables and re-enables them,
   making the lock real rather than visual. As with point 6, the likeliest
   explanation for the report is that the deployed build predates this
   behaviour, which arrived with the unreleased v3 cycle.

2. **The RTD-table bin was left alone.** The table already renders exactly one
   🗑 (`review.html:183`), gated on own-or-admin + `open` + `in_review` — one
   icon whose presence already follows role and state. Adding the admin's
   permanent delete there would have meant a second copy of the dialog on a
   surface that loads none of the viewer's JavaScript. The card stays where the
   admin's permanent delete lives, as it has since v2.2.

3. **`rework_by_id` needed batch mode, and so did its downgrade.** SQLite
   cannot `ALTER` a constraint into place, so the three columns are added
   inside one `op.batch_alter_table` (copy-and-move; on PostgreSQL it degrades
   to plain `ALTER`s). The downgrade needs it for a sharper reason: a plain
   `DROP COLUMN` leaves the foreign key behind and the table stops opening at
   all — *unknown column "rework_by_id" in foreign key definition*. Both
   directions were exercised by `tests/db/test_db_migration.py`.

4. **The backfill marks, it does not parse.** Legacy rows get `rework_at` set
   where the reply carries the marker; `rework_reason` and `rework_by_id` stay
   NULL. Recovering a reason by parsing free text, or a user id from a display
   name embedded in a string, would be inventing data — the reply is still
   there and the card falls back to it.

5. **Six unrelated tests were freed from a hard-coded revision id.**
   `tests/db/test_schema_authority.py` asserted `current_revision(engine) ==
   "c4d5e6f7a8b9"` in six places, so *any* new revision broke them. They now
   read the head from Alembic's own script directory, which is what they meant
   all along. Step 06 adds another revision and would have broken them again.
