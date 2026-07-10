# Claude Code — v1 Kickoff Prompt

Paste the block below as the first message of a Claude Code session started in
the maluS repository root.

---

We are starting **maluS v1**: turning the v0.1.0 local/git CLI into a
self-hosted web application. Read, in full, before writing any code:
`CLAUDE.md`, `docs/plan/v1/00-overview.md`, and
`docs/plan/v1/01-architecture-and-data-model.md`. Also read the existing v0
memory under `memory/decisions/` and `memory/specs/` — the domain invariants
still hold. Skim `src/malus/` so you know what is being reused.

Context you must respect:
- **Git is being removed** as store/transport; a database replaces it. Freeze
  becomes an immutable document version (content hash); RID traceability becomes
  in-app edits linked to RIDs plus an audit log. `rtd.yaml` survives only as an
  import/export format.
- **Reuse the domain core** (`models`, `parser`, `triage`, `lifecycle`,
  `report`). Replace only persistence and transport. Do not fork the lifecycle
  logic — especially the closure invariant.
- **Invariants that never bend:** only a reviewer (or moderator on their behalf)
  may mark a finding `verified` — never the owner, never an AI; reviewers may add
  only comment blocks to a copy (freeze rule); every AI submission is attributed
  and can never verify/close. Enforce all of these **server-side**.
- **Stack (from ADR 0002):** Python 3.12, FastAPI, SQLModel on SQLite (WAL,
  Postgres-ready), Alembic, argon2 auth, an MCP server for the AI reviewer,
  Docker for deploy. No runtime CDN; vendor front-end assets. No secret ever
  committed.
- **AI reviewer is free by design:** maluS exposes an MCP/API and the user runs
  Claude Code *interactively* (their subscription) to submit a review. maluS
  makes no server-side model calls on the default path. A server-side headless
  engine exists only behind an off-by-default flag and is documented as paid.

Your task now: implement **Step 1 only** (`01-architecture-and-data-model.md`):
the two ADRs, the SQLModel schema in `src/malus/db/`, Alembic setup + initial
migration, `docs/spec/data-model.md`, and the model/relationship tests. Prove
lossless `rtd.yaml` ↔ DB mapping for the RID fields.

Workflow:
1. Restate your Step-1 plan in ≤10 lines and wait for my OK.
2. Build test-driven where practical; run `python -m pytest -q` as you go.
3. Finish by ticking every checkbox in `01-…md`, recording any deviation under
   a `## Deviations` heading there and, if architectural, in
   `memory/decisions/`. Report the Definition-of-Done checklist pass/fail.

Rules: do not start Step 2. Conventional Commits, small and scoped. If any spec
point is ambiguous, stop and ask before deviating.

---
