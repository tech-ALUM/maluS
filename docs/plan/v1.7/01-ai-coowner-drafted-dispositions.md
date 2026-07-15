# Step 1 — AI co-owner drafts dispositions; a human owner confirms

## Objective

Enable an `is_ai` co-owner to submit **draft** dispositions (over MCP/API) that
do not take effect until a **human owner confirms** them in the GUI, while
guaranteeing server-side that an AI principal can never *commit* a
finding-advancing owner decision.

## Deliverables

### The `is_ai` commit guard (safety core)

- [ ] **authz**: an `is_ai` principal is refused (403) on the committing owner
      transitions — `answer` (status → `ANSWERED`), `implement`, `finalize` —
      while still allowed to write disposition fields without a transition
      (`update_rid`). Add to `src/malus/api/authz.py` and enforce at
      `patch_rid` / `finalize` in `src/malus/api/routes.py`.
- [ ] **services (defense-in-depth)**: `answer`, `implement`, `finalize` in
      `services/core.py` reject an `is_ai` actor (`by.is_ai`), mirroring how the
      services already enforce the closure invariant themselves.

### Drafting

- [ ] **`ai_drafted` auto-set**: when disposition fields are written by an
      `is_ai` actor via `update_rid` (no transition), set `ai_drafted=True`;
      a human write leaves the existing value (provenance is kept on confirm).
- [ ] **MCP tool** `submit_disposition(client, review_id, rid, disposition,
      reply, resolution)` in `src/malus/mcp/tools.py` (added to `TOOL_NAMES`):
      does `PATCH /reviews/{id}/rids/{rid}` with the fields and **no `status`** →
      draft. Update the module docstring (it currently states there is *no*
      disposition tool — the reviewer-only assumption changes for a co-owner).

### GUI (human owner confirm / discard)

- [ ] **`finding.html`**: when a RID is `OPEN` and `ai_drafted`, show an "AI
      proposal" banner with the proposed disposition/reply/resolution pre-filled
      into the existing dispose form; a **Confirm** button commits `answer`, a
      **Discard** button clears the draft (`ai_drafted=False`, fields cleared) →
      `OPEN`. Shown only to a human owner (`can_dispose and not user.is_ai`).
- [ ] **Discard route** `POST /ui/reviews/{id}/rids/{rid}/discard-draft`
      (human owner): clears the drafted fields; 403 for non-owner / AI.
- [ ] **Surfacing**: an "AI" badge on `ai_drafted` rows in the RTD table
      (`review.html`) and a dashboard tile "N AI proposals to confirm".

### Tests

- [ ] AI co-owner: `PATCH` with fields only → RID stays `OPEN`, `ai_drafted=True`
      (draft); `PATCH status=answered` and `status=implemented` → 403; `finalize`
      → 403; the `answer` / `implement` / `finalize` services raise on an `is_ai`
      actor.
- [ ] Human owner: confirms an AI proposal → `ANSWERED`, disposition persisted,
      attributed to the human owner, `ai_drafted` retained; discards → clean
      `OPEN` with `ai_drafted=False`.
- [ ] MCP: `submit_disposition` writes a draft end-to-end (TestClient); a human
      then confirms it.
- [ ] Regression: the existing invariant — AI may never verify/reopen — stays
      green; assigning the owner role to an AI account is accepted.

## Key behaviors

- Claude reads comments with the existing `list_rids` tool; the only new write
  surface is `submit_disposition`, which can only ever produce a **draft**.
- Provenance: `ai_drafted` stays `True` through confirmation (records "AI
  originated this"); the audit log carries both the AI draft action and the human
  confirm.
- The AI co-owner does **not** perform setup / freeze / implement / finalize —
  the human primary owner does (see Out of scope).

## Definition of Done

An AI co-owner drafts a disposition over MCP; it is held as an `OPEN` +
`ai_drafted` proposal; a human owner confirms it (→ `ANSWERED`, attributed to the
human) or discards it; the AI is refused (403) on every committing owner
transition in both authz and services; suite green; no migration.

## Out of scope

- AI-owner setup / freeze / document implementation / finalize (human owner
  only).
- Sole / primary AI ownership and any ownership-transfer action (the AI is a
  co-owner; the human stays primary owner).
- A new role or a new RID `Status` (drafts reuse `OPEN` + `ai_drafted`).
- Server-side model calls (maluS makes none; the AI is interactive Claude
  Desktop / Claude Code).

## Deviations

_None yet — agreed deviations are recorded here during implementation; the
settled decision goes to `memory/decisions/2026-07-15-v1.7-ai-coowner-draft.md`._

## Sources

- Design session with Alberto Boffi, 2026-07-15 (this repo, Claude Code):
  co-owner + human owner confirms; draft = `OPEN` + `ai_drafted`; `is_ai` commit
  guard; `submit_disposition` MCP tool.
- Verified in code: `src/malus/api/authz.py:63` (existing `is_ai` verify block),
  `src/malus/api/routes.py:381` (`patch_rid`: update vs answer/implement),
  `src/malus/services/core.py` (`answer:217`, `update_rid:238`, `implement:272`,
  `finalize:391`), `src/malus/mcp/tools.py:7` (docstring: "no disposition tool"),
  `src/malus/web/templates/finding.html`, `src/malus/db/models.py:197`
  (`ai_drafted`).
