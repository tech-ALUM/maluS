# RID Schema & Status Lifecycle — Normative Specification

**Status:** Normative. Frozen at Step 1 (Foundations). The transition table
is data (`src/malus/constants.py`) and is the single source of truth shared
by the CLI and the GUI. Changes require a recorded decision in
`memory/decisions/`.

The **RTD** (Revision Tracking Document, `rtd.yaml`) is the single canonical
artifact of a review (decision D2). The annotated merged DUR, tables, and
dashboards are generated *views*; only `rtd.yaml` is hand/tool-maintained.
Each tracked finding is one **RID** (Review Item Discrepancy).

## 1. File structure

`rtd.yaml` has a `meta:` header and a `rids:` list.

```yaml
meta:
  review_id: SIN-SRS-R1
  document: reviews/SIN-SRS-R1/baseline.md
  baseline_sha: 9f1c2ab                 # git SHA of the frozen baseline
  created: 2026-07-03
  owner: A. Boffi
  reviewers: [F. Miccoli, R. Bianchi]
rids:
  - rid: SIN-SRS-0042                    # <PROJECT>-<DOC>-<NNNN>, stable
    reviewer: F. Miccoli
    created: 2026-07-03
    anchor:
      section: "3.2.1"
      quote: "…the timeout shall be configurable…"
      line_hint: 142
      offset: 4207                       # v2, optional: baseline char offset
    kind: COMM                           # COMM | SUGG
    type: technical                      # typo | editorial | technical | process (null for SUGG)
    severity: major                      # minor | major | critical (null for SUGG)
    status: open                         # open | answered | closed | implemented | verified | withdrawn
    comment: >-
      The timeout must be bounded.
    reply: null
    disposition: null                    # accepted | rejected | deferred
    resolution: null                     # what was done; commit refs
    master: null                         # RID id if clustered as a duplicate
    duplicates: []
    verified_by: null
    verified_on: null
```

### `meta` fields

| Field | Meaning |
|-------|---------|
| `review_id` | Identifier of this review instance. |
| `rid_prefix` | *(optional)* Overrides the `<PROJECT>-<DOC>` RID id prefix; when absent it is derived from `review_id` (§2). |
| `document` | Path to the frozen baseline DUR. |
| `baseline_sha` | Git SHA of the frozen baseline commit. |
| `created` | Date the review was created (`YYYY-MM-DD`). |
| `owner` | Name (or seat) of the document owner. |
| `reviewers` | List of reviewer names. |

### RID fields

| Field | Type | Meaning |
|-------|------|---------|
| `rid` | str | Stable ID `<PROJECT>-<DOC>-<NNNN>` (see §2). |
| `reviewer` | str | Author of the finding. For a de-duplicated `SUGG`, the primary reviewer; co-authors listed in `duplicates`. |
| `created` | date | Date the finding was first harvested. |
| `anchor` | map | `{section, quote, line_hint, offset}` — location context (see comment-syntax §5). Any member may be null. `offset` (v2, **optional and additive**) is the finding's baseline **character offset**, filled at harvest and used by the document viewer to place markers; it is omitted from exports when unset, so pre-v2 files round-trip unchanged. |
| `kind` | enum | `COMM` or `SUGG`. |
| `type` | enum \| null | `typo` \| `editorial` \| `technical` \| `process` for a `COMM`; `null` for a `SUGG`. |
| `severity` | enum \| null | `minor` \| `major` \| `critical` for a `COMM`; `null` for a `SUGG`. |
| `status` | enum | Lifecycle state (see §3). |
| `comment` | str | The finding text (`COMM`) or a rendering of the `old -> new` change (`SUGG`). |
| `reply` | str \| null | Owner's response. |
| `disposition` | enum \| null | `accepted` \| `rejected` \| `deferred`; `null` until answered. |
| `resolution` | str \| null | What was done, including commit references. |
| `master` | str \| null | The RID id this one is clustered under, if it is a duplicate. |
| `duplicates` | list[str] | RID ids clustered under this one (this RID is the master). |
| `verified_by` | str \| null | Reviewer (or moderator on their behalf) who set `verified`. |
| `verified_on` | date \| null | Date of verification. |
| `ai_drafted` | bool | *(optional)* `true` when the reply/disposition was AI-drafted and awaits human confirmation; omitted when false. |

### Serialization conventions (git-friendliness)

To keep GUI/CLI saves as minimal git diffs (a hard constraint):

- Field order is preserved as listed above; keys are **not** re-sorted.
- Absent values are `null`; empty lists are `[]`.
- Dates are ISO `YYYY-MM-DD`.
- Untouched RIDs are never rewritten or reordered.

## 2. RID identity and stability

RID ids have the form `<PROJECT>-<DOC>-<NNNN>`:

- `PROJECT` and `DOC` are short uppercase alphanumeric tokens (e.g. `SIN`,
  `SRS`). The `<PROJECT>-<DOC>` prefix is `meta.rid_prefix` when set, otherwise
  `review_id` with its trailing `-<revision>` segment removed (e.g.
  `SIN-SRS-R1` → `SIN-SRS`).
- `NNNN` is a zero-padded sequence number (≥ 4 digits), assigned in
  **document order** (by anchor position) at the **first** harvest.

**Stability across re-harvests** — ids never churn:

- A block is matched to its existing RID by `(reviewer, content-hash)`, where
  the content-hash is taken over the normalized block: for a `COMM`,
  `kind + type + severity + text`; for a `SUGG`, `kind + old + new` (all
  unescaped). Matched blocks keep their existing `rid`.
- A newly appearing block gets the next `NNNN`.
- A block that has **disappeared** from a reviewer copy is set to status
  `withdrawn` — never deleted, never renumbered.

## 3. Status lifecycle

States: `open`, `answered`, `closed` (**v3** — the reviewer accepted the
owner's disposition), `implemented`, `verified`, `withdrawn`.

Forward graph (**v3** — the v2 direct path `answered → verified` is
**removed**: a `rejected`/`deferred` RID now stops at `closed`; only an
`accepted` one continues on to `implemented → verified`):

```
open ──▶ answered ──▶ closed ──▶ implemented ──▶ verified
  │
  └──▶ withdrawn
```

Allowed forward transitions:

| From | To | Actor | Condition |
|------|----|-------|-----------|
| `open` | `answered` | owner | Owner records `reply` + `disposition`. |
| `open` | `withdrawn` | the RID's **reviewer** only | Reviewer retracts the finding. |
| `answered` | `closed` | the RID's **reviewer**, or moderator on their behalf | **Accept disposition** (v3): the reviewer agrees the discussion is settled, whatever the disposition (`accepted`/`rejected`/`deferred`). |
| `closed` | `implemented` | owner | Only when `disposition = accepted`; requires ≥1 commit referencing the RID (traceability). A `rejected`/`deferred` RID never takes this edge — it stays `closed`. |
| `implemented` | `verified` | the RID's **reviewer**, or moderator on their behalf | Reviewer confirms the change resolves the finding. |

### Review phases (gates on which RID actions are available) — v3

Since v3, the per-RID graph above is further gated by the **review's own
phase** (`reviews.status` / `ReviewStatus`; normative detail in
`docs/spec/data-model.md`): `draft → in_review → closeout → finalized`, with
a human-global-admin escape hatch `closeout → in_review`.

| Phase | Entry gate | RID actions allowed in this phase |
|-------|-----------|-------------------------------------|
| `draft` | initial state, before the baseline is frozen | none — no RIDs exist yet |
| `in_review` | baseline frozen | comments/harvest, triage, `answer` (dispose), **accept disposition**, `reopen` |
| `closeout` | owner's **Start closeout**; gate: ≥1 non-withdrawn RID and none still `open`/`answered` | `implement`, `verify`, **request changes**, `link_change`; a human global admin may revert to `in_review` |
| `finalized` | owner's **Finalize**; gate: every RID `verified` or `withdrawn`, or `closed` with disposition `rejected`/`deferred` | terminal — no further RID actions |

Retracting a still-`open` comment (`retract_comment`) is gated to `in_review`
only (`_require_phase`, `src/malus/services/core.py`) — not phase-ungated: an
earlier draft of this spec claimed an "any-phase admin escape hatch" for
retract, but that never held, since `retract_comment`'s own internals
(re-harvesting) call `harvest`, which is itself `in_review`-gated. In
practice an `open` RID cannot exist past `in_review` anyway (the closeout
gate forbids it), so a plain reviewer withdraw was never reachable outside
`in_review`; what changed is the admin path, which is now explicit rather
than implicit: an admin who needs to withdraw a comment once the review has
left `in_review` uses `reopen_review` (`closeout → in_review`), then
`retract_comment`, then `start_closeout` again. The admin-only `purge_rid`
hard-delete escape hatch remains phase-ungated (any phase) — it is a
distinct, more drastic action from retract and was not part of this
correction.

Backward moves (`src/malus/lifecycle.py` helpers — direct field assignment,
**not** edges in the forward graph above; both require a mandatory reason
appended to the RID's `reply` thread):

| Helper | From → To | Actor | Phase |
|--------|-----------|-------|-------|
| `reopen` | `answered` \| `closed` \| `implemented` \| `verified` → `open` | the RID's **reviewer**, or moderator on their behalf | `in_review` only |
| `request-changes` | `implemented` \| `verified` → `closed` | the RID's **reviewer**, or moderator on their behalf | `closeout` only — the closeout-phase analogue of `reopen`; appends `"[changes requested by <reviewer>: <reason>]"` and clears `verified_by`/`verified_on` |

`reopen`'s helper (`reopen_rid`) accepts the full `answered | closed |
implemented | verified` set as its allowed-from statuses, but the *service*
wrapping it (`svc.reopen`) is itself `in_review`-only — so in practice an
`implemented`/`verified` RID can only be reopened after an admin
`reopen_review` has returned the review to `in_review` (those two statuses
cannot otherwise coexist with the `in_review` phase).

Owner-side edits (**v3**, `svc.update_rid`): `reply`/`resolution` are editable
in `in_review` and `closeout`; the `disposition` is editable only while the
finding is `open`/`answered` — once its reviewer accepted it (`closed` and
beyond) it is **settled** and changes only through the formal reopen. A
disposition may only be recorded at all once the finding's reviewer has
**submitted** their copy (a `draft` comment can still change).

`verified` and `withdrawn` are terminal. `closed` is terminal in practice for
a `rejected`/`deferred` RID — the only forward edge out of `closed` requires
`disposition = accepted` — but it is not itself in `TERMINAL_STATUSES`: an
accepted `closed` RID still moves on to `implemented`.

### Closure-authority invariant (critical control)

> **Only the reviewer — or a moderator (or human global admin) acting on
> their behalf — may set a RID to `closed` or `verified`. The owner may
> never issue either verdict. An AI may never set `closed` or `verified`,
> regardless of which seat it occupies.**

`closed` and `verified` are both reviewer verdicts, gated by the same
invariant: only the RID's own reviewer, or someone acting on their behalf
(moderator, or a human global admin per v1.10) — never the owner identity,
never an AI principal. **v3** extends the invariant from `verified` alone to
also cover `closed`, since accepting the disposition is now a distinct
reviewer act, separate from later verifying the implemented change.
Recording the **disposition** itself (`answer`, `open → answered`) remains an
owner/admin action; an AI principal may only draft it (`ai_drafted`), never
commit it.

This makes owner self-certification structurally impossible and is what makes
the AI-owner mode safe (decision D3). It is enforced in the transition logic
(`src/malus/models.py:transition`), not merely by convention.

### Scope enforced at Step 1 vs. later

Step 1 (`constants.py` + `models.py`) enforces the **status graph** and the
**closure-authority invariant** above. The following are documented here as
the normative contract but are enforced in **Step 5 (lifecycle enforcement)**:

- the disposition conditions in the table (`accepted → implemented`; a
  `rejected`/`deferred` RID stays `closed` instead — the v2 path
  `{rejected, deferred} → verified` no longer exists, v3);
- the traceability rule — an accepted RID needs ≥1 referencing commit between
  `baseline_sha` and `HEAD` before it may become `implemented`;
- finalize requires every RID to be `verified` or `withdrawn`, or `closed`
  with disposition `rejected`/`deferred` (v3 — previously `verified` covered
  rejected/deferred too); `deferred` RIDs export to a carry-over file for the
  next review cycle.

## Sources

- Design session with Alberto Boffi, 2026-07-03 (Claude chat): RID schema,
  reviewer-side closure (D3), single canonical RTD (D2).
- `memory/decisions/2026-07-03-architecture-decisions.md` — D2, D3.
- `memory/specs/rid-schema-and-lifecycle.md` — draft observations this
  document makes normative.
- `docs/plan/v3/00-design.md`, `docs/plan/v3/01-lifecycle.md` — the v3 design
  (approved by Alberto Boffi, 2026-07-29) and implementation plan for `closed`,
  the forward/backward graphs, the closure-authority extension, and the
  review-phase gate table this §3 update makes normative.
- `src/malus/constants.py` (`Status`, `TRANSITIONS`, `TERMINAL_STATUSES`),
  `src/malus/models.py` (`transition`), `src/malus/lifecycle.py`
  (`accept_disposition_rid`, `request_changes_rid`, `reopen_rid`),
  `src/malus/services/core.py` (`_require_phase`, `closeout_gate`,
  `start_closeout`, `reopen_review`, `finalize`) — the v3 implementation this
  §3 update was checked against.
- `memory/knowledge/roles-model.md` — owner/reviewer/moderator authority.
