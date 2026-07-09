---
title: Step 3 Decisions 2026-07-09
type: decision
permalink: malus/decisions/2026-07-09-step-03-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- triage
- step-3
---

# Step 3 Decisions 2026-07-09

Decisions and implementation choices settled with Alberto Boffi while building
triage (duplicate clustering and mechanical suggestion apply). Follows
[[Step 2 Decisions 2026-07-09]].

## Observations
- [decision] `malus apply-suggs` applies every `{SUGG}` unless it is explicitly
  rejected (or withdrawn) — default-accepted per D4, so batch-apply runs during
  triage rather than waiting for per-finding owner disposition #sugg
- [decision] `malus triage` lists proposed duplicate groups and changes nothing;
  `--auto` links the high-confidence groups and saves. Interactive per-group
  yes/no prompts were deferred #triage
- [spec] Duplicate grouping: `{COMM}` findings in the same anchor section whose
  normalized comments have difflib similarity ≥ threshold; master = lowest-
  numbered RID; propose threshold 0.60, auto-accept 0.82 (adjustable) #clustering
- [spec] A duplicate's status follows its master at clustering; ongoing sync when
  the master changes is enforced in Step 5 #lifecycle
- [spec] SUGG operands are escaped when rendered into `comment` so the stored
  string re-parses losslessly via `parse_sugg_comment` (the RID schema has no
  dedicated old/new fields) #sugg
- [decision] `apply-suggs` writes `<review>/working.md` derived from the frozen
  `baseline.md`; the baseline is never modified; `--dry-run` previews a unified
  diff #apply

## Relations
- decides_for [[maluS — Index]]
- constrained_by [[Architecture Decisions 2026-07-03]]
- follows [[Step 2 Decisions 2026-07-09]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09 (Step 3 implementation)
- docs/plan/03-triage.md (## Deviations)
