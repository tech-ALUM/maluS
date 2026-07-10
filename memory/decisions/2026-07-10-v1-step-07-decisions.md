---
title: v1 Step 7 — AI Reviewer via MCP Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-07-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- ai
- mcp
---

# v1 Step 7 — AI Reviewer via MCP Decisions

Claude Code acts as a reviewer through maluS's MCP server, interactively, with
no paid Anthropic API on the server (docs/plan/v1/07-ai-reviewer-mcp.md).

## Observations

- [decision] maluS exposes an MCP server (src/malus/mcp) whose tools drive the Step-3 HTTP API as a reviewer identity: list_reviews, get_baseline, list_rids, submit_reviewer_comments, propose_triage. No verify/close/disposition tool exists. maluS makes zero server-side model calls — the free path is an interactive Claude Code session (subscription), run via `malus mcp` (FastMCP, stdio) #mcp
- [decision] Programmatic auth = HTTP Basic (the agent uses the AI reviewer's credentials); this is the token path deferred from Step 4. get_current_user falls back from the session cookie to Basic #auth
- [decision] AI principals (is_ai) are guardrailed server-side: verify/reopen -> 403 regardless of role; AI-submitted comments enter only through the parser-validated submit endpoint (baseline tampering -> 422); findings are attributed to the agent identity and never advance on their own #guardrail
- [decision] New API endpoints for the agent: POST /reviews/{id}/copies/{user}/submit (validate+save+harvest) and GET /reviews/{id}/baseline; triage proposals (auto=false, read-only) opened to any member, applying stays moderator-only #api
- [decision] Paid path: MALUS_AI_ENGINE=anthropic behind engine.py — off by default, refuses unless enabled, documented as billed at API rates; the unattended engine is not implemented in v1 #paid
- [context] Deps: mcp>=1.2 (optional extra [mcp]). Tests drive the tools against a FastAPI TestClient stub end-to-end and assert the FastMCP server builds with exactly the five tools (no verify/close). docs/usage/ai-reviewer.md documents the interactive connect flow. 159 tests pass #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 6 — Markdown Editor & Reviewer Workflow Decisions]]
- realises [[ADR 0001 — v1 web pivot]] (free interactive AI, no paid API)

## Sources
- docs/plan/v1/07-ai-reviewer-mcp.md; Anthropic billing change 2026-06-15
- Implementation: src/malus/mcp/ (tools, server, engine); Basic auth in auth/deps.py; submit/baseline endpoints in api/routes.py; malus mcp in cli.py
- Claude Code session with Alberto Boffi, 2026-07-10
