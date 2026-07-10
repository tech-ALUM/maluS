# Step 7 — AI Reviewer via Claude Code (no paid Anthropic API)

## Objective

Let Claude Code act as a reviewer through maluS's own interface, driven
**interactively** under the user's Claude subscription — so no `ANTHROPIC_API_KEY`
and no paid Anthropic API are used on the server.

## The design decision (why it is this way)

Server-side headless Claude Code (`claude -p` / Agent SDK) is **not** free:
since 2026-06-15 its usage is metered on a separate Agent SDK credit and then
billed at API rates. Therefore the default, free path is:

> maluS exposes an **MCP server** (over its Step-3 API). The user runs Claude
> Code **interactively** (covered by the subscription) and connects it to
> maluS; the agent reads the baseline and submits comment blocks / RIDs through
> maluS. maluS never calls a model itself, so it never incurs model billing.

## Deliverables

- [ ] `src/malus/mcp/` — an MCP server exposing review tools:
      `list_reviews`, `get_baseline`, `submit_reviewer_comments`
      (validated by the parser), `list_rids`, `propose_triage`
- [ ] Auth: the agent authenticates as a reviewer identity (Step 4); the policy
      flag blocks any verify/close/disposition-confirm tool for AI principals
- [ ] All AI-submitted content attributed (`ai_drafted` / reviewer = the agent
      identity) and never advances on its own
- [ ] `docs/usage/ai-reviewer.md` — how to connect Claude Code to maluS
      interactively (no API key), and how to add an AI reviewer to a review
- [ ] Optional, clearly-labeled **paid** path: a server-side engine behind a
      config flag (`MALUS_AI_ENGINE=anthropic`, off by default) for unattended
      runs — documented as billed at API rates
- [ ] Tests: a scripted MCP client drives an AI review end-to-end against a
      local stub; guardrails proven (AI cannot verify/close)

## Key behaviors

- AI input enters only through the same validated endpoints as a human's — no
  side channel. Invalid comment blocks are rejected by the parser.
- The free path uses zero server-side model calls; the paid path is opt-in and
  isolated behind the flag.

## Definition of Done

An AI reviewer copy can be produced and harvested through the MCP/API with no
Anthropic API key set; the guardrail tests pass (AI verify/close impossible);
the connect-Claude-Code doc is followed successfully; suite green.

## Out of scope

AI as owner (disposition drafting) can reuse the same MCP tools later; not
required for v1.

## Sources

v1 design session 2026-07-09; Anthropic Claude Code billing change 2026-06-15
(programmatic usage separated from the interactive subscription pool) — the
reason the free path is interactive + MCP rather than server-side headless.
