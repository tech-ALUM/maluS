---
title: v1 Step 3 — HTTP API (FastAPI) Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-03-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- api
- fastapi
---

# v1 Step 3 — HTTP API Decisions

Decisions implementing v1 Step 3 (docs/plan/v1/03-api.md): the whole review
pipeline exposed as a typed HTTP API — the single contract for the GUI
(Steps 5–6) and the AI agent (Step 7). Auth is Step 4.

## Observations

- [decision] `src/malus/api/`: app factory (`create_app(engine)`, engine on `app.state` so tests inject in-memory), per-request `Session` dependency that commits on success / rolls back on error, typed Pydantic request+response schemas, routes. OpenAPI at `/openapi.json`, Swagger at `/docs` #api
- [decision] Every mutation goes through the Step-2 services; the API never bypasses `lifecycle.transition` or the parser. Routes are thin adapters #layering
- [decision] Actor identity (Alberto's choice via AskUserQuestion): supplied per request body (e.g. verify `{reviewer, moderator}`); the domain enforces the closure invariant regardless; Step 4 binds it to the authenticated principal #actor
- [decision] Error model (Alberto's choice): 403 closure-authority, 409 illegal state / unique conflict / unmet precondition, 404 not-found, 422 request validation. Implemented with a `ClosureAuthorityError(TransitionError)` subclass raised only in authority branches (behavior identical; MRO lookup returns 403 before the 409 base) #errors
- [decision] `POST /document` saves a working DocumentVersion; `POST /freeze` snapshots the current (or inline) content as the immutable baseline. `GET /traceability` added (not in the plan's map). RID `PATCH` routes status→answer/implement; verify/reopen are dedicated POSTs; reviewer withdraw not exposed yet #endpoints
- [decision] `malus serve` runs uvicorn; `create_all` on startup is a dev convenience, prod migrates via Alembic. `POST /reviews/import` + `GET /reviews/{id}/export` exchange text/plain rtd.yaml #serve
- [context] Added `update_rid` service (owner field edits without a transition) for the RID PATCH. Deps added: fastapi, uvicorn (runtime), httpx (dev, backs TestClient) #services
- [context] 137 tests pass; the full demo review runs headless over HTTP in a TestClient (create→freeze→copies→harvest→triage→disposition→change→verify→report→finalize), OpenAPI is served, export/import round-trips across databases #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 2 — Persistence Layer Decisions]]

## Sources
- docs/plan/v1/03-api.md
- Implementation: src/malus/api/ (app, deps, errors, schemas, routes); malus serve in cli.py; ClosureAuthorityError in models.py/lifecycle.py
- Claude Code session with Alberto Boffi, 2026-07-10
