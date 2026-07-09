# Step 6 — AI Roles

## Objective

Fill any of the three seats with an AI: owner (mode 1), reviewer (mode 2),
moderator (triage assist) — without weakening any human control.

## Deliverables

- [x] `src/malus/ai.py` — Anthropic API client wrapper (model/key via env +
      config; no key ever stored in repo)
- [x] `prompts/` — versioned prompt templates per role
- [x] `malus ai review --reviewer <name>` — AI produces its own reviewer
      copy with syntactically valid comment blocks (validated by the
      step-2 parser before acceptance)
- [x] `malus ai disposition` — AI-owner drafts replies + dispositions into
      rtd.yaml (marked `ai-drafted: true` until a human or the pipeline
      confirms per configured mode)
- [x] `malus ai triage` — semantic duplicate proposals through the step-3
      proposal interface (same confirmation flow)
- [x] Guardrails documented + enforced

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

## Deviations

Decisions settled 2026-07-09 (candidates for `memory/decisions/`):

- **Engine:** pluggable, with a deterministic offline **mock** engine as the
  default (all tests + dry-runs). The live engine uses the official `anthropic`
  SDK as an **optional** extra (`pip install 'malus[ai]'`), lazily imported; the
  core still depends only on typer + pyyaml. Model `claude-opus-4-8`; key from the
  environment. (Alberto delegated the choice — "best free option".)
- **`ai_drafted`** optional RID field added (schema extension; serialized only when
  true).

Implementation choices:

- **`ai disposition` drafts but never advances status** — it writes the (enum-
  validated) disposition, the reply, and `ai_drafted: true`, leaving status `open`.
  A human confirms (the mandatory control for mode 1).
- **`ai triage`** proposes through the Step-3 `ClusterProposal` interface and the
  same `--auto`/list flow; the mock proposes nothing by default.
- **Guardrails enforced by construction:** the `ai` sub-app has no `verify`/`close`
  command; `ai review` output is rejected unless the Step-2 parser accepts it and it
  is insertion-only; `ai disposition` writes only typed fields; attribution is the
  reviewer name or `ai_drafted`.
- **Prompts** live in `prompts/` at the repo root, loaded relative to the package
  (works in the editable install; packaging as package-data is a Step-7 concern).
- **Live engine untested** in the suite (behind `--engine anthropic` + a key); the
  whole suite runs against the mock.

## Sources

Design session 2026-07-03 — three-roles abstraction (any seat human or AI)
as the mode-agnostic design (D5 in `memory/decisions/…`).
