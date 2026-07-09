# Step 5 — Lifecycle, Verification, Reporting

## Objective

Close the loop: enforce the RID lifecycle end-to-end, tie implementation
commits to RIDs, run reviewer-side verification, and generate all reports.

## Deliverables

- [ ] Transition enforcement shared by CLI and GUI (single constant source)
- [ ] `malus verify` — verification workflow + traceability checks
- [ ] `malus report` — validation + generated outputs:
      `report.md` (review minutes) and a status dashboard section
- [ ] `malus finalize` — produce new baseline + archive the review
- [ ] Commit↔RID traceability checker

## Key behaviors

- **Traceability**: every `accepted` RID must be referenced by ≥1 commit
  message between baseline SHA and HEAD before it can be marked
  `implemented`; `malus verify --check` lists accepted-but-unreferenced RIDs
  and referenced-but-not-accepted anomalies.
- **Verification**: `malus verify --reviewer <name>` walks that reviewer's
  implemented/answered RIDs, shows the resolution and the relevant document
  diff, records verdict (`verified` or reopen → back to `open` with a
  mandatory reason appended to the thread). Owner identity can never issue
  verdicts (enforced, not conventional).
- **Finalize** requires: all RIDs `verified` or `withdrawn`. Produces the
  new `baseline.md` (next revision), final `report.md` (minutes: per-reviewer
  stats, dispositions, open-deferred register carried to next cycle),
  archives the review folder read-only.
- Deferred RIDs export into a carry-over file consumable by the next
  review's `malus init`.

## Definition of Done

Fixture review driven from harvest to finalize entirely via CLI+GUI with
every guard exercised by tests (self-certification attempt fails,
unreferenced accepted RID blocks implemented, reopen path works); suite green.

## Sources

Design session 2026-07-03 — reviewer-side closure authority as the critical
control (D3 in `memory/decisions/…`).
