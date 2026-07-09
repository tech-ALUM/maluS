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
    kind: COMM                           # COMM | SUGG
    type: technical                      # typo | editorial | technical | process (null for SUGG)
    severity: major                      # minor | major | critical (null for SUGG)
    status: open                         # open | answered | implemented | verified | withdrawn
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
| `anchor` | map | `{section, quote, line_hint}` — location context (see comment-syntax §5). Any member may be null. |
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

### Serialization conventions (git-friendliness)

To keep GUI/CLI saves as minimal git diffs (a hard constraint):

- Field order is preserved as listed above; keys are **not** re-sorted.
- Absent values are `null`; empty lists are `[]`.
- Dates are ISO `YYYY-MM-DD`.
- Untouched RIDs are never rewritten or reordered.

## 2. RID identity and stability

RID ids have the form `<PROJECT>-<DOC>-<NNNN>`:

- `PROJECT` and `DOC` are short uppercase alphanumeric tokens (e.g. `SIN`,
  `SRS`).
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

States: `open`, `answered`, `implemented`, `verified`, `withdrawn`.

```
open ──▶ answered ──▶ implemented ──▶ verified
  │          │                            ▲
  │          └───────────(rejected/deferred)──┘
  └──▶ withdrawn
```

Allowed transitions:

| From | To | Actor | Condition |
|------|----|-------|-----------|
| `open` | `answered` | owner | Owner records `reply` + `disposition`. |
| `open` | `withdrawn` | the RID's **reviewer** only | Reviewer retracts the finding. |
| `answered` | `implemented` | owner | Only when `disposition = accepted`; requires ≥1 commit referencing the RID (traceability). |
| `answered` | `verified` | the RID's **reviewer**, or moderator on their behalf | Only when `disposition ∈ {rejected, deferred}`; reviewer acknowledges the disposition. |
| `implemented` | `verified` | the RID's **reviewer**, or moderator on their behalf | Reviewer confirms the change resolves the finding. |

`verified` and `withdrawn` are terminal.

### Closure-authority invariant (critical control)

> **Only the reviewer — or a moderator acting on their behalf — may set a
> RID to `verified`. The owner may never verify. An AI may never set
> `verified` regardless of which seat it occupies.**

This makes owner self-certification structurally impossible and is what makes
the AI-owner mode safe (decision D3). It is enforced in the transition logic
(`src/malus/models.py`), not merely by convention.

### Scope enforced at Step 1 vs. later

Step 1 (`constants.py` + `models.py`) enforces the **status graph** and the
**closure-authority invariant** above. The following are documented here as
the normative contract but are enforced in **Step 5 (lifecycle enforcement)**:

- the disposition conditions in the table (`accepted → implemented`,
  `{rejected, deferred} → verified`);
- the traceability rule — an accepted RID needs ≥1 referencing commit between
  `baseline_sha` and `HEAD` before it may become `implemented`;
- finalize requires every RID to be `verified` or `withdrawn`; `deferred`
  RIDs export to a carry-over file for the next review cycle.

## Sources

- Design session with Alberto Boffi, 2026-07-03 (Claude chat): RID schema,
  reviewer-side closure (D3), single canonical RTD (D2).
- `memory/decisions/2026-07-03-architecture-decisions.md` — D2, D3.
- `memory/specs/rid-schema-and-lifecycle.md` — draft observations this
  document makes normative.
- `memory/knowledge/roles-model.md` — owner/reviewer/moderator authority.
