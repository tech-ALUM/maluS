---
title: Step 7 Decisions 2026-07-09 (v0.1.0 release)
type: decision
permalink: malus/decisions/2026-07-09-step-07-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- release
- step-7
---

# Step 7 Decisions 2026-07-09 (v0.1.0 release)

The final step — end-to-end validation and the v0.1.0 release. Follows
[[Step 6 Decisions 2026-07-09]]. Completes the seven-step plan.

## Observations
- [milestone] maluS v0.1.0: the full pipeline is implemented and tested — init →
  freeze → copies → harvest → triage → apply-suggs → (GUI/AI) disposition →
  implement → verify → report → finalize, plus AI in any seat. Tagged `v0.1.0` #release
- [decision] Packaging: PEP 621, `pipx install .` / `pip install .`, version 0.1.0.
  Prompt templates moved into the package (`src/malus/prompts/`, package-data,
  loaded via `importlib.resources`) so `malus ai` works from a plain install —
  verified in a clean non-editable venv. Refines the Step-6 repo-root location #packaging
- [spec] `examples/srs-demo/` is a fully synthetic ~10-section SRS with three
  scripted reviewer copies (a duplicate technical-major pair, two mechanical
  suggestions, one baseline-editing freeze violation); `tests/test_e2e.py` drives
  the whole pipeline in a temp git repo including a reopen, asserting finalize #e2e
- [context] The README describes and links the GUI but embeds no screenshot/GIF —
  a headless environment can't persist an image into the repo; the visual pass is
  in docs/spec/gui-test-checklist.md #docs
- [context] docs/usage.md is the newcomer guide (both modes); its quickstart runs
  from the maluS repo root (captures `$MALUS`) since the example ships in the repo #docs

## Relations
- decides_for [[maluS — Index]]
- follows [[Step 6 Decisions 2026-07-09]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09 (Step 7 / v0.1.0)
- docs/plan/07-e2e.md (## Deviations)
