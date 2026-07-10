# Step 3 — HTTP API (FastAPI, API-first)

## Objective

Expose the whole review pipeline as a typed HTTP API. This API is the single
spine consumed by both the web GUI (Steps 5–6) and the AI agent (Step 7).

## Deliverables

- [x] `src/malus/api/` — FastAPI app, routers, Pydantic request/response schemas
- [x] Endpoints covering the full lifecycle (see below)
- [x] Auto-generated OpenAPI served at `/docs` and `/openapi.json`
- [x] Consistent error model (validation, not-found, forbidden, conflict)
- [x] `malus serve` command launches the app (uvicorn)
- [x] API tests with FastAPI TestClient for every endpoint + the full pipeline

## Endpoint map (auth added in Step 4)

- `POST /reviews` · `GET /reviews` · `GET /reviews/{id}`
- `POST /reviews/{id}/document` (create/replace DUR) · `GET .../document`
- `POST /reviews/{id}/freeze`
- `POST /reviews/{id}/reviewers` (add) · `GET .../reviewers`
- `GET/PUT /reviews/{id}/copies/{user}` (reviewer copy content)
- `POST /reviews/{id}/harvest`
- `POST /reviews/{id}/triage` (`auto` flag) · `POST .../apply-suggs` (`dry_run`)
- `GET /reviews/{id}/rids` · `GET/PATCH /reviews/{id}/rids/{rid}`
  (reply, disposition, resolution, status transitions — server validates)
- `POST /reviews/{id}/rids/{rid}/verify` · `.../reopen`
- `POST /reviews/{id}/changes` (link an edit/version to RIDs)
- `GET /reviews/{id}/report` · `POST /reviews/{id}/finalize`
- `GET /reviews/{id}/export` (rtd.yaml) · `POST /reviews/import` (rtd.yaml)

## Key behaviors

- Every state transition goes through the Step-2 services; the API never
  bypasses `lifecycle.transition()` or the parser validation.
- Requests are typed; responses include the resource state so a client never
  has to guess. The pipeline is fully drivable headless via HTTP (this is what
  the E2E test and the AI agent both rely on).

## Definition of Done

The complete demo review (create → freeze → copies → harvest → triage →
disposition → change → verify → report → finalize) runs entirely through HTTP in
a TestClient script; OpenAPI validates; suite green.

## Out of scope

Login/permissions (Step 4 wraps these routes). Any HTML (Step 5).

## Deviations

Settled with Alberto before coding (actor mechanism + error statuses via
AskUserQuestion); details in `memory/decisions/2026-07-10-v1-step-03-decisions.md`.

- **Error model (chosen):** 403 for closure-authority violations, 409 for illegal
  state transitions / conflicts, 404 not-found, 422 validation. To split 403 vs
  409 cleanly, a `ClosureAuthorityError(TransitionError)` subclass was added to
  the core (behavior identical; existing `except TransitionError` unaffected).
- **Actor (chosen):** supplied per request body (e.g. `verify {reviewer,
  moderator}`); the domain still enforces the closure invariant server-side.
  Step 4 replaces the supplied value with the authenticated principal.
- **Added `GET /reviews/{id}/traceability`** (not in the endpoint map — the plan
  folded traceability into `verify --check`); exposed as a GET for GUI/agent.
- **document vs freeze:** `POST /document` saves a working `DocumentVersion`;
  `POST /freeze` snapshots the current (or inline-supplied) content as the
  immutable baseline.
- **RID PATCH** routes `status→answered/implemented` through `answer`/`implement`
  (traceability-gated); `verify`/`reopen` are dedicated POSTs. Reviewer
  `withdraw` is not exposed (absent from the plan's map; deferred).
- **`create_all` on app startup** is a dev convenience; production migrates via
  Alembic. `POST /reviews/import` consumes `text/plain` rtd.yaml (matches export).
- One cosmetic warning: Starlette's TestClient deprecates plain `httpx` (suite
  stays green).

## Sources

v1 design session 2026-07-09 (API-first rationale: one contract for GUI + agent).
