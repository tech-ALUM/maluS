# Step 5 — Lifecycle, Verification, Reporting

## Objective

Close the loop: enforce the RID lifecycle end-to-end, tie implementation
commits to RIDs, run reviewer-side verification, and generate all reports.

## Deliverables

- [x] Transition enforcement shared by CLI and GUI (single constant source)
- [x] `malus verify` — verification workflow + traceability checks
- [x] `malus report` — validation + generated outputs:
      `report.md` (review minutes) and a status dashboard section
- [x] `malus finalize` — produce new baseline + archive the review
- [x] Commit↔RID traceability checker

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

## Deviations

Decisions settled 2026-07-09 (candidates for `memory/decisions/`):

- **Verify** uses non-interactive flags (`--check`, `--reviewer`, `--rid`,
  `--reopen`, `--moderator`); an interactive step-through walk was deferred.
- **Finalize** writes `final.md` (from `working.md`, else the baseline),
  `report.md`, `carryover.yaml` (deferred findings), and a `FINALIZED` marker
  inside the review folder; the next revision is started with `init`. "Read-only
  archive" is a marker file, not filesystem permissions.

Implementation choices / revisions:

- **Freeze SHA revised** from the baseline *blob* hash (Step 2 choice) to the
  *commit* SHA (`git rev-parse HEAD`), because traceability checks the commit
  range `baseline_sha..HEAD`. `freeze` now requires the review to be inside a
  git repo with a commit. This revises the Step-2 decision.
- **Disposition gating** was added to `transition()` and mirrored in the GUI
  (`attemptTransition`), re-verified in a browser.
- **Traceability**: a RID is *referenced* when its id appears in a commit message
  in `baseline_sha..HEAD`. Enforced via `verify --check` (exit 1 on anomalies),
  which the owner runs before finalizing; because marking *implemented* is the
  GUI's job (no git in the browser), the "before implemented" rule is a check
  rather than a hard block at the transition.
- **Owner identity** (`== meta.owner`) can never verify or reopen — enforced in
  addition to the role check.
- **Minutes** (`report.md`) are generated entirely from `rtd.yaml`; validation is
  repo-free (traceability is the separate, git-aware check).

## Sources

Design session 2026-07-03 — reviewer-side closure authority as the critical
control (D3 in `memory/decisions/…`).
