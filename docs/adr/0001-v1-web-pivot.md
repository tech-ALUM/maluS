# ADR 0001 — Move maluS from a git-based CLI to a self-hosted web application

- **Status:** Accepted
- **Date:** 2026-07-09
- **Deciders:** Alberto Boffi (v1 design session); implemented by Claude Code
- **Supersedes:** the v0 storage/transport model in
  `memory/decisions/2026-07-03-architecture-decisions.md` (D1 git-branch freeze,
  git-based traceability). The domain invariants D1–D5 themselves are retained.

## Context

v0.1.0 is a local, text-first CLI. The canonical store is `rtd.yaml`; history
and traceability come from git — one branch per reviewer, the baseline pinned to
a commit SHA, and RID ids referenced in commit messages. Every participant needs
the repository, git, and the CLI installed.

This does not scale to the target usage: 10+ reviewers per review, owners who are
not developers, and AI participants, all inside one company. It also carries an
AI-billing problem: as of 2026-06-15 Anthropic separates *programmatic* Claude
Code usage (`claude -p`, the Agent SDK) from the *interactive* subscription pool,
so the v0 `--engine anthropic` path bills per run. v1 must let the AI reviewer
run at no additional cost.

## Decision

Turn maluS into a **self-hosted web application** and remove git as store and
transport:

1. **Database is the canonical store.** `rtd.yaml` is demoted to an
   import/export interchange format (round-trip fidelity is proven in Step 1).
2. **Freeze becomes an immutable `DocumentVersion`** identified by a content
   hash, replacing the baseline commit SHA.
3. **RID traceability becomes data:** in-app edits linked to the RIDs they
   resolve (`RidChange`) plus an append-only `AuditLog`, replacing "RID id in the
   commit message".
4. **The domain core is reused unchanged** (`models`, `parser`, `triage`,
   `lifecycle`, `report`); only persistence and transport are replaced. The
   lifecycle logic — especially the closure-authority invariant (D3) — is **not**
   forked.
5. **Invariants are enforced server-side:** only a reviewer (or a moderator on
   their behalf) may set a RID `verified` — never the owner, never an AI;
   reviewers may add only comment blocks to a copy (freeze rule, D1); every AI
   submission is attributed and can never verify/close.
6. **The AI reviewer is free by design.** maluS exposes an MCP server and REST
   API; the user drives Claude Code *interactively* under their own subscription.
   maluS makes no server-side model calls on the default path. A server-side
   headless engine survives only behind an off-by-default flag, documented as
   paid.

## Consequences

- **(+)** 10+ human or AI reviewers work through a browser behind login; no
  git/CLI per participant.
- **(+)** Freeze and traceability become first-class, queryable data (hashes,
  links, audit) instead of git conventions.
- **(+)** Domain invariants live and are enforced in one server-side place.
- **(−)** New operational surface: a server, a database, auth, migrations,
  backups, deployment (see ADR 0002).
- **(−)** `rtd.yaml` must be maintained as a faithful interchange format; its
  round-trip is a Step-1 acceptance test.
- **(−)** Existing v0 reviews are onboarded via `rtd.yaml` import (Step 9).

## Alternatives considered

- **Keep git, add a thin web layer over it.** Rejected: git-per-reviewer does not
  scale to non-technical/AI participants and leaves the paid-AI problem unsolved.
- **Hosted SaaS.** Out of scope: the requirement is self-hosting on the company
  server.

## Sources

- `docs/plan/v1/00-overview.md` — the v1 pivot, "What changes vs v0", "What is
  kept", "Invariants preserved", and Sources (2026-07-09 design session).
- `docs/plan/v1/01-architecture-and-data-model.md` — Step 1 objective and the
  AI-billing note under Sources.
- `memory/decisions/2026-07-03-architecture-decisions.md` — D1–D5, in particular
  D3 (reviewer-side closure) which this pivot preserves.
- Anthropic support/pricing change of 2026-06-15 (programmatic vs interactive
  Claude Code usage), as recorded in the v1 design session.
