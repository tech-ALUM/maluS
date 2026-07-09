---
title: init Command 2026-07-09
type: decision
permalink: malus/decisions/2026-07-09-init-command
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- cli
- init
---

# init Command 2026-07-09

`malus init` was built at Alberto's request (2026-07-09) to fill the
"create a new review" gap before Step 3 — it had been a stub after Steps 1–2.

## Observations
- [decision] Interface: `malus init <review_id> --document <src.md> [--dir reviews]
  [--owner NAME] [--reviewers a,b]`. Creates `<dir>/<review_id>/` with baseline.md
  (copied from the source DUR), an empty reviewers/ directory, and rtd.yaml
  (meta seeded, `rids: []`) #init
- [decision] init leaves `meta.baseline_sha` empty; `freeze` records it next, so
  freezing stays a distinct explicit action (process step 1) #init
- [decision] init refuses to overwrite an existing review (rtd.yaml present) #safety
- [context] `freeze` still bootstraps rtd.yaml when missing (kept as a fallback),
  but init is now the normal way to start a review #freeze

## Relations
- decides_for [[maluS — Index]]
- follows [[Step 2 Decisions 2026-07-09]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09
