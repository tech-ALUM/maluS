# maluS — User Guide (v1, web application)

maluS runs a formal RID-based review of a Markdown document as a self-hosted web
app. The baseline is frozen; each reviewer comments on their own copy (comment
blocks only); comments are harvested into RIDs; the owner dispositions them; the
owner implements accepted ones (creating linked document versions); reviewers
verify and close; the review is finalized. A database is the store — **no git**.

Deployment is covered in [ops/runbook.md](ops/runbook.md); connecting an AI
reviewer in [usage/ai-reviewer.md](usage/ai-reviewer.md). This guide is the
end-to-end user walkthrough for both modes.

## Roles

| Role | Can | Cannot |
|------|-----|--------|
| **admin** | manage users | touch review content |
| **owner** | edit/freeze the DUR, dispose RIDs, implement, finalize | **verify** |
| **reviewer** | edit *their own* copy; verify/reopen *their own* RIDs | others' copies/RIDs |
| **moderator** | harvest, triage, verify **on a reviewer's behalf** | — |
| **AI principal** | comment (as a reviewer identity), propose triage | **verify / close / confirm** |

**Closure authority (the safety control):** only a reviewer — or a moderator on
their behalf — may set a RID `verified`. The owner never can; an AI never can.
Enforced server-side, so it holds regardless of the GUI or API.

## Human-owner mode (walkthrough)

1. **Admin** logs in (first-run bootstrap admin; change the password) and creates
   accounts: an owner, reviewers, a moderator (Users page / `POST /users`).
2. **Owner** creates a review, sets the document, and **freezes** the baseline;
   then adds members with roles (reviewers + a moderator).
3. **Reviewers** open *Edit my copy*, insert `{COMM|…}` / `{SUGG:…}` blocks
   (baseline text stays frozen), and **submit** — which harvests server-side.
   Tampering with baseline text is rejected by the parser.
4. **Moderator** runs **triage** to cluster duplicates.
5. **Owner** opens each finding and records a **disposition** (accept/reject/defer)
   with a reply.
6. **Owner** opens *Implement accepted findings*, edits the DUR, ticks the RIDs the
   edit resolves, and saves — creating a new version linked to those RIDs.
7. **Reviewers** verify their findings; the **moderator** verifies an AI reviewer's
   findings on its behalf. Reopen with a reason if a fix is incomplete.
8. **Owner** views the **report** (minutes) and **finalizes** once every RID is
   verified or withdrawn.

## AI-reviewer mode

Add an AI reviewer (an `is_ai` user) to a review, then connect Claude Code
**interactively** to maluS's MCP server — no API key, no server-side model calls.
The agent reads the baseline and submits comment blocks through the same
validated endpoint a human uses; its findings are attributed to it and can never
be verified/closed by the AI. See [usage/ai-reviewer.md](usage/ai-reviewer.md).

*(AI-owner mode — an AI drafting dispositions, marked `ai_drafted` for human
confirmation — reuses the same tools and is planned beyond v1.)*

## Interfaces

- **Browser GUI** at `/ui/…` — login, review list, dashboard, RTD table, finding
  detail, the editor.
- **HTTP API** — the same operations, typed, documented at `/openapi.json` and
  `/docs`. Everything the GUI and the AI agent do goes through this one contract.
- **CLI** — `malus serve` (run the app), `malus mcp` (AI reviewer server),
  `malus import <dir>` (load a v0 review).

## Migrating a v0 review

```sh
malus import path/to/reviews/<review-id> --db "$MALUS_DB_URL"
```

Loads `baseline.md`, `rtd.yaml`, and `reviewers/*.md` into the database. The v0
single-file GUI (`gui/rtd.html`) remains available as legacy.

## Sources

- Normative contracts: `docs/spec/comment-syntax.md`, `rid-schema.md`, `data-model.md`.
- Architecture: `docs/adr/`. Plan: `docs/plan/v1/`.
