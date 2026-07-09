---
title: Step 6 Decisions 2026-07-09
type: decision
permalink: malus/decisions/2026-07-09-step-06-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- ai
- step-6
---

# Step 6 Decisions 2026-07-09

Decisions and implementation choices settled with Alberto Boffi while adding AI
roles (owner / reviewer / moderator). Follows [[Step 5 Decisions 2026-07-09]].

## Observations
- [decision] AI engine is pluggable with a deterministic offline MockEngine as the
  default (all tests + dry-runs). The live engine uses the official `anthropic` SDK
  as an OPTIONAL extra (`pip install 'malus[ai]'`), lazily imported; the core still
  depends only on typer + pyyaml. Model `claude-opus-4-8`, key from the environment.
  Alberto delegated the choice ("best free option") #engine
- [decision] Added an optional `ai_drafted` bool to RID (serialized only when true),
  marking a reply/disposition an AI drafted pending human confirmation #schema
- [decision] `ai disposition` drafts the (enum-validated) disposition + reply and
  sets `ai_drafted`, but never advances status (stays open) or verifies — a human
  confirms; this is the mandatory control for mode 1 (AI owner) #guardrails
- [invariant] Guardrails enforced by construction: the `ai` sub-app has no
  verify/close command; `ai review` output is rejected unless the Step-2 parser
  accepts it and it is insertion-only; `ai disposition` writes only typed rtd fields;
  every AI artifact is attributed (reviewer name or `ai_drafted`) — no AI path to
  closure, in the CLI or the GUI #closure-authority
- [spec] `ai triage` proposes semantic duplicate clusters through the Step-3
  `ClusterProposal` interface and the same `--auto`/list confirmation flow #triage
- [context] Versioned prompt templates in `prompts/` at the repo root, loaded
  relative to the package (works in the editable install; packaging as package-data
  is a Step-7 concern). The live engine is not exercised by the suite #tooling

## Relations
- decides_for [[maluS — Index]]
- constrained_by [[Architecture Decisions 2026-07-03]]
- refines [[Roles Model]]
- follows [[Step 5 Decisions 2026-07-09]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09 (Step 6 implementation)
- docs/plan/06-ai-roles.md (## Deviations)
