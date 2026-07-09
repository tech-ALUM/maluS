---
title: Step 5 Decisions 2026-07-09
type: decision
permalink: malus/decisions/2026-07-09-step-05-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- lifecycle
- step-5
---

# Step 5 Decisions 2026-07-09

Decisions and implementation choices settled with Alberto Boffi while closing the
lifecycle loop (verification, traceability, reporting, finalize). Follows
[[Step 4 Decisions 2026-07-09]].

## Observations
- [spec] Disposition routing is enforced in `transition()` and mirrored in the GUI
  `attemptTransition`: a disposition is required to answer; accepted →
  implemented → verified; rejected/deferred → verified straight from answered #lifecycle
- [decision] `malus verify` is non-interactive: `--check` (traceability),
  `--reviewer` (list a reviewer's pending RIDs), `--rid [--reopen "reason"]`
  (record a verdict), `--moderator`; an interactive step-through walk was deferred #verify
- [decision] `malus finalize` refuses unless every RID is verified/withdrawn and
  rtd.yaml validates, then writes `final.md` (from `working.md`, else the
  baseline), `report.md`, `carryover.yaml` (deferred findings), and a `FINALIZED`
  marker in the review folder; the next revision is started with `init`. The
  read-only archive is a marker file, not filesystem permissions #finalize
- [spec] Traceability: a RID is *referenced* when its id appears in a commit
  message in `baseline_sha..HEAD`; `check_traceability` flags accepted-unreferenced
  and referenced-not-accepted, and `verify --check` exits non-zero on anomalies.
  Because marking implemented is the GUI's job (no git in the browser), the
  "before implemented" rule is a check the owner runs before finalizing, not a hard
  transition block #traceability
- [decision] Freeze SHA revised from the baseline *blob* hash (Step 2) to the git
  *commit* SHA (`git rev-parse HEAD`) so the traceability range resolves; `freeze`
  now requires the review to be inside a git repo with a commit. Supersedes the
  freeze-SHA observation in [[Step 2 Decisions 2026-07-09]] #freeze
- [invariant] The owner *identity* (`== meta.owner`) can never verify or reopen, on
  top of the role-based closure-authority rule (D3) #closure-authority
- [spec] `malus report` validates rtd.yaml (unique ids; verified needs a non-owner
  verifier; answered-or-later needs a disposition; consistent master/duplicate
  links) and generates `report.md` minutes entirely from rtd.yaml; validation is
  repo-free (traceability is the separate git-aware check) #report

## Relations
- decides_for [[maluS — Index]]
- constrained_by [[Architecture Decisions 2026-07-03]]
- follows [[Step 4 Decisions 2026-07-09]]
- supersedes [[Step 2 Decisions 2026-07-09]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09 (Step 5 implementation)
- docs/plan/05-lifecycle.md (## Deviations)
