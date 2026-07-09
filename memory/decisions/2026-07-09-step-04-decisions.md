---
title: Step 4 Decisions 2026-07-09
type: decision
permalink: malus/decisions/2026-07-09-step-04-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- gui
- step-4
---

# Step 4 Decisions 2026-07-09

Decisions and implementation choices settled with Alberto Boffi while building the
single-file RTD GUI (`gui/rtd.html`). Follows [[Step 3 Decisions 2026-07-09]].

## Observations
- [decision] The GUI reads/writes YAML with a small targeted reader plus a surgical
  writer that rewrites only edited field lines, so untouched YAML stays byte-identical
  (minimal git diffs) — the plan's allowed "minimal YAML subset" option, chosen over
  vendoring js-yaml #gui
- [spec] This relies on every rtd.yaml value being on one line; `models.to_yaml` now
  double-quotes newline strings and disables wrapping (`width` large). Single-line
  values keep PyYAML's default style, so Step 1–3 output/tests are unchanged #serialization
- [spec] The GUI's status graph and enums are generated from `malus.constants` by
  `malus.gui_constants` and spliced between markers in rtd.html; `tests/test_gui.py`
  fails if the block drifts (single source of truth) #enforcement
- [invariant] The GUI enforces closure authority at the UI: the owner's and any other
  reviewer's "→ verified" button is disabled with a tooltip; only the RID's own
  reviewer (or a moderator) can verify — mirroring `models.transition` #closure-authority
- [decision] "Threaded reply" is the single `reply` field (the frozen RID schema has one
  reply); no multi-level threading #gui
- [context] DoD "passes malus report validation" is deferred to Step 5 (`report` is a
  stub); the GUI-saved file is validated with `RTD.from_yaml` for now #report
- [tooling] Local browser preview uses a gitignored `.claude/launch.json` (http.server);
  the GUI needs no server in real use (opens from file://) #tooling

## Relations
- decides_for [[maluS — Index]]
- constrained_by [[Architecture Decisions 2026-07-03]]
- follows [[Step 3 Decisions 2026-07-09]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09 (Step 4 implementation)
- docs/plan/04-gui.md (## Deviations); docs/spec/gui-test-checklist.md
