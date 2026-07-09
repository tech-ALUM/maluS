# Step 6 — AI Roles

## Objective

Fill any of the three seats with an AI: owner (mode 1), reviewer (mode 2),
moderator (triage assist) — without weakening any human control.

## Deliverables

- [ ] `src/malus/ai.py` — Anthropic API client wrapper (model/key via env +
      config; no key ever stored in repo)
- [ ] `prompts/` — versioned prompt templates per role
- [ ] `malus ai review --reviewer <name>` — AI produces its own reviewer
      copy with syntactically valid comment blocks (validated by the
      step-2 parser before acceptance)
- [ ] `malus ai disposition` — AI-owner drafts replies + dispositions into
      rtd.yaml (marked `ai-drafted: true` until a human or the pipeline
      confirms per configured mode)
- [ ] `malus ai triage` — semantic duplicate proposals through the step-3
      proposal interface (same confirmation flow)
- [ ] Guardrails documented + enforced

## Guardrails (non-negotiable)

- AI never sets `verified` and never closes RIDs. Closure authority stays
  with human reviewers in mode 1; in mode 2 the AI reviewer's RIDs are
  verified by the human owner's implementation being checked by the AI, but
  final closure still requires the configured human sign-off.
- AI output enters the system only through the same validated formats
  (comment blocks, rtd.yaml fields) — no side channels.
- Every AI-generated artifact is attributed (`reviewer: claude` /
  `ai-drafted`) — provenance is always visible.

## Definition of Done

Mode-1 and mode-2 dry runs on the fixture review with a mocked API in tests
(live API behind an env flag); guardrail violations impossible via CLI/GUI;
suite green.

## Sources

Design session 2026-07-03 — three-roles abstraction (any seat human or AI)
as the mode-agnostic design (D5 in `memory/decisions/…`).
