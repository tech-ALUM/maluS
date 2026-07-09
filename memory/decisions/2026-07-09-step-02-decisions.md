---
title: Step 2 Decisions 2026-07-09
type: decision
permalink: malus/decisions/2026-07-09-step-02-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- harvest
- step-2
---

# Step 2 Decisions 2026-07-09

Decisions and implementation choices settled with Alberto Boffi while building
the harvest step (parser, freeze validation, rtd.yaml assembly). Follows
[[Step 1 Decisions 2026-07-09]].

## Observations
- [decision] Reviewer copies are files (`reviews/<id>/reviewers/<name>.md`), not
  git branches — a deliberate deviation from D1's branch phrasing; `copies`/
  `harvest` are pure file+diff operations and git-branch mode is deferred #freeze
- [decision] RID id prefix `<PROJECT>-<DOC>` is `meta.rid_prefix` when set, else
  `review_id` minus its trailing `-<revision>` segment (SIN-SRS-R1 → SIN-SRS);
  `rid_prefix` added as an optional Meta field, serialized only when set #ids
- [decision] `freeze` records the baseline SHA into meta and can bootstrap
  rtd.yaml when absent. SUPERSEDED 2026-07-09: it originally recorded the git
  *blob* hash (`git hash-object`), but freeze now records the git *commit* SHA
  (`git rev-parse HEAD`) so the Step-5 traceability range `baseline_sha..HEAD`
  resolves; freeze now requires a git repo with a commit. See
  [[Step 5 Decisions 2026-07-09]]. (`init` is no longer a stub — see
  [[init Command 2026-07-09]].) #freeze
- [spec] Freeze validation = strip parsed comment blocks from a copy; the residue
  must differ from baseline.md only in whitespace (char-level difflib). Violating
  or malformed copies are reported per-copy; the others still harvest #validation
- [decision] Identical `{SUGG}`s dedup to one RID credited to the first reviewer
  in document order; multi-reviewer credit is left to triage (Step 3) #sugg
- [spec] `to_yaml` disables YAML anchors/aliases (SafeDumper.ignore_aliases →
  True); required for byte-idempotent re-harvest and clean git diffs #serialization
- [open-question] Anchor `quote` is the ~120 preceding chars (whitespace-collapsed)
  and may span a heading boundary — acceptable as a context hint, refine later #anchoring

## Relations
- decides_for [[maluS — Index]]
- refines [[RID Schema and Lifecycle]]
- constrained_by [[Architecture Decisions 2026-07-03]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09 (Step 2 implementation)
- docs/plan/02-harvest.md (## Deviations)
- docs/spec/rid-schema.md, docs/spec/comment-syntax.md
