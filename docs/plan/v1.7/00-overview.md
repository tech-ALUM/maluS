# maluS v1.7 — AI Co-Owner: Drafted Dispositions, Human-Confirmed

Requested by Alberto Boffi, 2026-07-15 (this repo, Claude Code). Target workflow:
**Claude is a co-owner** of a review; humans (Alberto, Francesco) are reviewers;
Claude reads all their comments over the API (Claude Desktop / MCP), discusses
them with a human in chat, then uploads a **distilled disposition as a draft**;
a **human owner confirms** it in the GUI before it takes effect.

## Why this fits the invariant (and why it needs a guard)

- The closure invariant — *"closure authority belongs to reviewers, never the
  owner"* — is about **verify/close**, which stays reviewer-side; the `is_ai`
  guard already forbids AI verify/reopen (`src/malus/api/authz.py:63`). A
  **disposition** is an owner power, not closure, so an AI owner drafting one
  does not touch the invariant — and humans still hold the final say by closing.
- But today **nothing** stops an AI owner from *committing* `answer` /
  `implement` / `finalize` via the API. The "draft, human-confirmed" model
  requires a new guard so an `is_ai` principal may only **draft**, never commit
  a finding-advancing owner decision — mirroring the existing verify/reopen block.

## The lightweight representation (decided with Alberto)

- The AI takes the **owner role** as a co-owner (assignable today from the
  members GUI, `src/malus/web/templates/members.html:20`); the **human primary
  owner** (`Review.owner_id`) is unchanged, so a confirmed disposition stays
  attributed to the human (`svc.answer` uses `review.owner`,
  `src/malus/services/core.py:230`). **No ownership-transfer feature, no new
  role.**
- A **draft** = a RID still `OPEN` with `disposition`(+`reply`/`resolution`) set
  and `ai_drafted=True`. `ai_drafted` already exists but is never written today
  (`src/malus/db/models.py:197`); this is its intended use. **No new Status, no
  schema change, no migration.**
- **Confirm** = the existing `answer` transition → `ANSWERED`, run by the human
  owner. **Discard** = clear the draft fields (`ai_drafted=False`) back to `OPEN`.

## Role-seat note (operational)

Confirming is an owner power and commenting is a reviewer power, and a user has
one role per review — so the human confirmer cannot also be a commenting reviewer
on the same review. Alberto chooses the seats per review: be the human owner
(confirm; others comment) or a reviewer (comment; another human owns).

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-ai-coowner-drafted-dispositions.md` | `is_ai` commit guard (authz + services); `ai_drafted` auto-set on AI draft; `submit_disposition` MCP tool; GUI confirm/discard of AI proposals + badge/count | v1 Step 4 (authz), Step 7 (MCP), Step 5 (GUI RTD/finding) |

## Global Definition of Done

- `python -m pytest -q` green; no schema change / no migration.
- An AI owner can write a draft disposition (RID stays `OPEN`, `ai_drafted=True`)
  but is refused (403) on `answer` / `implement` / `finalize`, in **both** the API
  authz layer and the services (defense-in-depth); the existing "AI never
  verify/close" invariant test stays green.
- A human owner sees AI proposals, confirms one (→ `ANSWERED`, attributed to the
  human) or discards it (→ clean `OPEN`).
- The `submit_disposition` MCP tool writes a draft through the same API a human
  uses (validated, authorized).

## Sources

- Design session with Alberto Boffi, 2026-07-15 (this repo, Claude Code):
  AI as co-owner; dispositions are **drafts confirmed by a human owner in the
  GUI** (chosen over immediate-authoritative); reuse the existing owner role +
  `ai_drafted` flag; no ownership transfer / no new role/state.
- Reserved intent already recorded in project memory (`ai_drafted`, "AI-as-owner
  disposition drafting"). Model + guards in `src/malus/api/authz.py`,
  `src/malus/api/routes.py` (`patch_rid:381`), `src/malus/mcp/tools.py`,
  `src/malus/db/models.py`.
