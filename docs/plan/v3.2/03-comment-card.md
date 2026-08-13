# v3.2 Step 3 — The comment card: one bin, a locked disposition, quiet sections

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** the card stops offering four ways to destroy a comment, stops
leaving a saved disposition editable in place, stops opening every section by
default, and stops hiding the reviewer's rework reason inside a string.

Feedback points **7, 8, 9, 10** of the v3.2 wave.

## Deliverables

- [ ] Exactly one 🗑 control per comment, in the card and in the RTD row
- [ ] A saved disposition is read-only until `Edit disposition` is pressed
- [ ] `Changes` and `History` are collapsed by default in closeout
- [ ] The reviewer's rework reason is a column, and a callout the owner cannot
      miss
- [ ] Alembic revision applied on top of `c4d5e6f7a8b9`, idempotent
- [ ] `python -m pytest -q` green

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

- [ ] **Step 1:** decide what the single icon does, from `(role, status,
      phase)`:

      | Case | On click |
      |---|---|
      | unsaved local comment | remove it from the copy, no server call |
      | own comment, `open`, `in_review`, reviewer | confirm → retract |
      | admin, `open`, `in_review` | dialog: `Withdraw` or `Delete permanently` |
      | admin, anything else | confirm → `Delete permanently` |
      | nobody with authority | the icon is **not rendered** |

- [ ] **Step 2:** build the two-choice dialog with the native `<dialog>`
      element — it is HTML, needs no library (ADR 0003 stays untouched), is
      focus-trapped and Esc-closable for free. `confirm()` cannot offer two
      destructive choices, and inventing a modal component is out of
      proportion. The purge branch keeps its double confirmation.
- [ ] **Step 3:** the RTD table in `review.html` carries its own withdraw
      control (the v1.8 one, own + `open`). Locate it by content and give it
      the same single-icon treatment and the same dialog, so the rule "one bin"
      holds on both surfaces.
- [ ] **Step 4:** tests — for each `(role, status, phase)` pair in the table
      above, assert how many destructive controls the rendered card and the
      rendered RTD row contain (the answer is always 0 or 1), and that the
      owner sees none. Authority tests for the endpoints already exist
      (`tests/web/test_retraction.py`) and must stay green untouched.
- [ ] **Step 5:** commit `feat(web): one bin per comment, role-aware`.

### Task 2: the disposition locks after saving (point 8)

**Files:** modify `src/malus/web/static/document-viewer.js`

The dispose form is built at `document-viewer.js:574-604`; on an `answered`
finding it is hidden behind an `Edit disposition` toggle
(`document-viewer.js:386-396`). Alberto's report is that after pressing
`Save disposition` the fields stay editable — establish first whether the
defect is the post-save state (before the redirect repaints the card) or the
toggle's own markup.

- [ ] **Step 1:** reproduce and record which of the two it is.
- [ ] **Step 2:** after a save, the card shows the disposition and the reply as
      **read-only text**, with a single `Edit disposition` button. The fields
      are not merely visually hidden — they must be unreachable by keyboard and
      not submittable while locked.
- [ ] **Step 3:** pressing `Edit disposition` restores **exactly** the
      first-time form: same fields, same order, same submit label. One code
      path renders both states so they cannot drift.
- [ ] **Step 4:** the server rule is unchanged and remains the authority:
      `update_rid` accepts `open|answered` only (`services/core.py:562-565`),
      so an `Edit disposition` button must never appear once the reviewer has
      accepted. Assert that in a test.
- [ ] **Step 5:** commit `feat(web): a saved disposition locks until you edit it`.

### Task 3: quiet sections in closeout (point 9)

**Files:** modify `src/malus/web/static/document-viewer.js`,
`src/malus/web/static/app.css`

- [ ] **Step 1:** `Changes` becomes a `<details>` (today a plain
      `<div class="cp-changes">`, always expanded, `document-viewer.js:310-333`)
      with a summary carrying the count, e.g. `Changes (2)`.
- [ ] **Step 2:** both `Changes` and `History` are **closed by default**, and
      `setFocus` stops forcing history open (`document-viewer.js:689-690`).
      Focusing a card still expands the card itself and its containing group —
      that is v3.1 behaviour and it stays.
- [ ] **Step 3:** manual verification: enter closeout, open a card in each of
      the four queue groups → both sections closed; open one → it stays open
      while you interact with the card; `?focus=RID` → card open, sections
      closed.
- [ ] **Step 4:** commit `feat(web): comment sections start closed in closeout`.

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

- [ ] **Step 1:** add to `rids`: `rework_reason: str | None`,
      `rework_by_id: int | None` (FK `users.id`), `rework_at: datetime | None`.
- [ ] **Step 2:** write the Alembic revision on top of the current head
      **`c4d5e6f7a8b9`** — but run `alembic heads` first and use what it
      reports, because step 06 adds a second revision and whichever lands
      later must branch from the earlier one. Follow the project convention
      (`CLAUDE.md`, revision `b9e4d5f6a701`): inspect with
      `sa.inspect(op.get_bind())` before every DDL operation so the revision
      is idempotent, and write the backfill as **set-based SQLAlchemy Core
      statements, never through the ORM**.
- [ ] **Step 3:** backfill from history: existing rows whose `reply` contains
      `[changes requested by …]` get the parsed reason and, where the audit
      log identifies the actor, `rework_by_id` and `rework_at`. Rows that
      cannot be parsed keep `NULL` — do not guess.
- [ ] **Step 4:** the request-changes service writes the columns. Keep writing
      the reply text as well **for this release**: `report.md`, the PDF and
      the history timeline read it, and changing all of them belongs to a
      different step. The columns are the new authority for *logic*; the reply
      string stays the human-readable trace.
- [ ] **Step 5:** the bucket logic reads `rework_at is not None` instead of the
      substring (`web/router.py:797`). `tests/web/test_closeout_page.py` covers
      this grouping — it must stay green.
- [ ] **Step 6:** the card renders the reason as a **callout at the top of the
      body** whenever the RID is in rework: reviewer name, timestamp, the text.
      Visible to every role, but it is the owner's work item — it must read as
      an instruction, not as a log line. It also stays in `History`.
- [ ] **Step 7:** tests — migration backfill from a legacy reply string;
      bucket computed from the column; the callout renders for the owner;
      `pytest tests/db -q` proves the models/migrations parity guard
      (`tests/db/test_db_migration.py::test_migrations_match_the_models_exactly`)
      still holds, since a model change without a revision is a bug.
- [ ] **Step 8:** commit `feat(db): the rework reason is a first-class column`
      and `feat(web): the rework reason is a callout, not a buried string`.

## Definition of Done

- [ ] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [ ] `alembic upgrade head` on a fresh DB **and** on a copy of a pre-step DB
      both succeed, and running it twice is a no-op
- [ ] For every `(role, status, phase)` pair, at most one destructive control
      renders — verified by test, not by eye
- [ ] Closure authority untouched: the owner still cannot accept, verify or
      request changes; `is_ai` still absolute
- [ ] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Changing what `report.md` or the PDF print for a reworked finding.
- Widening who may purge. The dialog routes to existing services; it grants
  nothing new.

## Verification

_Filled in during implementation._

## Deviations

_None yet._
