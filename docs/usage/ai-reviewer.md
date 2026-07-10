# AI reviewer via Claude Code (free, interactive) — maluS v1

maluS lets **Claude Code** act as a reviewer through maluS's own MCP server,
driven **interactively** under your Claude subscription. maluS never calls a
model itself, so **no `ANTHROPIC_API_KEY` and no paid Anthropic API** are used on
the server.

> Why interactive? Since 2026-06-15 Anthropic meters *programmatic* Claude Code
> usage (`claude -p` / Agent SDK) on a separate Agent SDK credit billed at API
> rates. Running Claude Code interactively is covered by the subscription, so the
> default maluS AI path is: an MCP server over the maluS API + an interactive
> agent. (ADR 0001; `docs/plan/v1/07-ai-reviewer-mcp.md`.)

## 1. Create an AI reviewer account (admin)

An AI reviewer is an ordinary maluS user with the **`is_ai`** flag set. AI
principals may submit comments but can **never** verify, reopen, or confirm a
disposition — enforced server-side regardless of role.

```bash
# as an admin (cookie or Basic auth):
curl -u admin:PASSWORD -X POST https://malus.example.com/users \
  -H 'content-type: application/json' \
  -d '{"username":"aibot","password":"<strong-pw>","display_name":"AI Bot","is_ai":true}'
```

Then the review's **owner** adds the AI as a reviewer:

```bash
curl -u owner:PASSWORD -X POST https://malus.example.com/reviews/SIN-SRS-R1/reviewers \
  -H 'content-type: application/json' -d '{"name":"AI Bot","role":"reviewer"}'
```

## 2. Point Claude Code at the maluS MCP server

The MCP server authenticates to maluS with the AI reviewer's credentials (HTTP
Basic). Configure Claude Code to launch it (stdio):

```jsonc
// Claude Code MCP config
{
  "mcpServers": {
    "malus": {
      "command": "malus",
      "args": ["mcp"],
      "env": {
        "MALUS_URL": "https://malus.example.com",
        "MALUS_AI_USER": "aibot",
        "MALUS_AI_PASSWORD": "<strong-pw>"
      }
    }
  }
}
```

No API key is set anywhere. Claude Code runs under your subscription.

## 3. Run the review interactively

In an interactive Claude Code session, ask it to review, e.g.:

> Use the `malus` tools: read the baseline of review `SIN-SRS-R1`, then submit
> review comments for reviewer "AI Bot".

The available tools are:

| Tool | What it does |
|------|--------------|
| `list_reviews` | reviews the AI reviewer can see |
| `get_baseline(review_id)` | the frozen baseline text to comment on |
| `list_rids(review_id)` | the current findings |
| `submit_reviewer_comments(review_id, reviewer, content)` | submit the AI copy — **comment blocks only**; validated by the parser and harvested server-side |
| `propose_triage(review_id)` | propose duplicate clusters (read-only) |

There is **no** verify/close/disposition tool. AI-submitted content enters only
through the same validated endpoint a human uses: the copy must be the baseline
plus `{COMM|…}` / `{SUGG:…}` insertions only — any change to baseline text is
rejected (HTTP 422) by the parser. Findings the AI raises are attributed to the
agent identity and never advance on their own; a human reviewer/moderator
verifies them.

## 4. Optional: the paid server-side engine (off by default)

For unattended runs you may enable a server-side engine with
`MALUS_AI_ENGINE=anthropic` (requires an Anthropic API key). **This path is paid
— billed at Anthropic API rates** and is off by default. Prefer the free
interactive path above unless you specifically need unattended automation.

## Sources

- `docs/plan/v1/07-ai-reviewer-mcp.md`; ADR 0001 (AI-billing rationale).
- Anthropic Claude Code billing change, 2026-06-15 (programmatic usage separated
  from the interactive subscription pool).
- Implementation: `src/malus/mcp/` (tools, server, engine); `malus mcp` (CLI).
