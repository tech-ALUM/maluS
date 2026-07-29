# v3 Step 1 — Lifecycle: `closed` status, review phases, accept disposition

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** introduce the v3 state machine — RID status `closed` (reviewer accepted
the disposition), review phases `draft → in_review → closeout → finalized`,
phase-gated services, accept-disposition / request-changes actions, migration
backfill — with API + minimal web wiring so the suite stays green.

**Architecture:** the pure domain (`constants.py`, `models.py`, `lifecycle.py`)
learns the new vocabulary; phase enforcement lives ONLY in `services/core.py`
(`transition()` stays phase-agnostic); web/API stay thin wrappers over the same
services + authz (spec: `docs/plan/v3/00-design.md`).

**Tech stack:** Python 3.12, SQLModel, FastAPI, pytest. No new dependencies.

## Global constraints (apply to every task)

- Closure authority invariant: `accept disposition`, `verify`, `request changes`
  are reviewer/moderator/human-admin actions — **never owner, never AI** (`is_ai`
  absolute).
- No new runtime dependencies in this step.
- `python -m pytest -q` green at the end of every task that says so; commit after
  each green step with Conventional Commits.
- Forward transitions live in `TRANSITIONS`; backward moves (reopen /
  request-changes) live in `lifecycle.py` helpers with direct assignment — the
  established v2 pattern.

## Deliverables

- [x] `Status.CLOSED` + new forward transition graph (`constants.py`)
- [x] `transition()` closure authority extended to `closed` (`models.py`)
- [x] `accept_disposition_rid` / `request_changes_rid` helpers; `reopen_rid` extended (`lifecycle.py`)
- [x] `ReviewStatus` phases + phase-gated services + `start_closeout` / `reopen_review` (`services/core.py`)
- [x] Startup migration backfill `draft|active → in_review` (`db/session.py`)
- [x] API endpoints: accept, request-changes, start-closeout, reopen-review
- [x] Web wiring: routes + viewer buttons (Accept disposition / Verify / Request changes) + dashboard phase actions
- [ ] Spec docs updated (`docs/spec/rid-schema.md` §3, `docs/spec/data-model.md`)
- [x] Full suite green

---

### Task 1: `Status.CLOSED` and the v3 transition graph

**Files:**
- Modify: `src/malus/constants.py:37-84`
- Test: `tests/test_constants.py`

**Interfaces produced:** `Status.CLOSED = "closed"`; graph
`open→{answered,withdrawn}, answered→{closed}, closed→{implemented}, implemented→{verified}`;
`TERMINAL_STATUSES` unchanged (`verified`, `withdrawn`).

- [ ] **Step 1: failing tests** — append to `tests/test_constants.py`:

```python
def test_v3_closed_status_exists():
    assert Status("closed") is Status.CLOSED


def test_v3_forward_graph():
    assert is_allowed_transition(Status.ANSWERED, Status.CLOSED)
    assert is_allowed_transition(Status.CLOSED, Status.IMPLEMENTED)
    assert is_allowed_transition(Status.IMPLEMENTED, Status.VERIFIED)
    # v2 paths removed: no direct answered→verified/implemented
    assert not is_allowed_transition(Status.ANSWERED, Status.VERIFIED)
    assert not is_allowed_transition(Status.ANSWERED, Status.IMPLEMENTED)
```

- [ ] **Step 2:** `python -m pytest tests/test_constants.py -q` → FAIL (`CLOSED` missing).
- [ ] **Step 3: implement** — in `Status` add `CLOSED = "closed"` after `ANSWERED`
  with docstring note *"v3: the reviewer accepted the owner's disposition"*; replace the graph:

```python
TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.OPEN: frozenset({Status.ANSWERED, Status.WITHDRAWN}),
    Status.ANSWERED: frozenset({Status.CLOSED}),
    Status.CLOSED: frozenset({Status.IMPLEMENTED}),
    Status.IMPLEMENTED: frozenset({Status.VERIFIED}),
    Status.VERIFIED: frozenset(),
    Status.WITHDRAWN: frozenset(),
}
```

- [ ] **Step 4:** `python -m pytest tests/test_constants.py -q` → the two new tests PASS
  (older graph tests may now fail — fix their expectations to the v3 graph in the same commit;
  they assert the v2 paths `answered→implemented/verified`).
- [ ] **Step 5:** `git commit -m "feat(domain): v3 status 'closed' + forward transition graph"`

### Task 2: closure authority for `closed` in `transition()`

**Files:**
- Modify: `src/malus/models.py:264-341`
- Test: `tests/test_models.py`

**Interfaces produced:** `transition(rid, Status.CLOSED, actor_role=…)` enforces the
same authority as `VERIFIED` (no AI, no owner, reviewer only own RID). The
`answered→verified` disposition special-case (models.py:330-335) is deleted.

- [ ] **Step 1: failing tests** (adapt the existing test fixtures in `tests/test_models.py` for building a RID):

```python
def test_v3_owner_may_never_close(answered_rid):
    with pytest.raises(ClosureAuthorityError):
        transition(answered_rid, Status.CLOSED, actor_role=Role.OWNER, actor_name="own")


def test_v3_ai_may_never_close(answered_rid):
    with pytest.raises(ClosureAuthorityError):
        transition(answered_rid, Status.CLOSED, actor_role=Role.REVIEWER,
                   actor_name=answered_rid.reviewer, actor_is_ai=True)


def test_v3_reviewer_closes_own_rid(answered_rid):
    transition(answered_rid, Status.CLOSED, actor_role=Role.REVIEWER,
               actor_name=answered_rid.reviewer)
    assert answered_rid.status is Status.CLOSED
```

- [ ] **Step 2:** run → FAIL (illegal transition / no guard).
- [ ] **Step 3: implement** — change the verify guard to cover both closure verdicts and drop the dead special-case:

```python
    if target in (Status.VERIFIED, Status.CLOSED):
        if actor_is_ai:
            raise ClosureAuthorityError(
                f"an AI may never set {target.value!r} (closure-authority invariant)"
            )
        if actor_role is Role.OWNER:
            raise ClosureAuthorityError(
                f"the owner may never set {target.value!r}; closure belongs to the reviewer"
            )
        if (
            actor_role is Role.REVIEWER
            and actor_name is not None
            and actor_name != rid.reviewer
        ):
            raise ClosureAuthorityError(
                f"reviewer {actor_name!r} may not close a RID owned by {rid.reviewer!r}"
            )
```

  Delete the `answered → verified is only for rejected or deferred` block
  (models.py:330-335) — that path no longer exists in the graph. Update the
  docstring's three-gates description to the v3 lifecycle. Keep the
  `verified_by`/`verified_on` stamp for `VERIFIED` only.
- [ ] **Step 4:** `python -m pytest tests/test_models.py -q` → PASS (fix any v2-path assertions to v3 in the same commit).
- [ ] **Step 5:** `git commit -m "feat(domain): closure authority covers 'closed' (accept disposition)"`

### Task 3: lifecycle helpers — accept, request changes, reopen

**Files:**
- Modify: `src/malus/lifecycle.py`
- Test: `tests/test_lifecycle.py`

**Interfaces produced (consumed by services in Task 4):**

```python
def accept_disposition_rid(rtd, rid_id, *, reviewer: str, moderator: bool = False) -> RID
def request_changes_rid(rtd, rid_id, *, reviewer: str, reason: str, moderator: bool = False) -> RID
# reopen_rid: allowed-from set gains Status.CLOSED
```

- [ ] **Step 1: failing tests** — append to `tests/test_lifecycle.py` (reuse its RTD fixture helpers):

```python
def test_accept_disposition_closes(rtd_answered):
    rid = accept_disposition_rid(rtd_answered, RID_ID, reviewer=REVIEWER)
    assert rid.status is Status.CLOSED


def test_accept_disposition_owner_refused(rtd_answered):
    with pytest.raises(ClosureAuthorityError):
        accept_disposition_rid(rtd_answered, RID_ID, reviewer=rtd_answered.meta.owner)


def test_request_changes_needs_reason(rtd_implemented):
    with pytest.raises(ValueError):
        request_changes_rid(rtd_implemented, RID_ID, reviewer=REVIEWER, reason="  ")


def test_request_changes_reworks_implemented(rtd_implemented):
    rid = request_changes_rid(rtd_implemented, RID_ID, reviewer=REVIEWER, reason="heading untouched")
    assert rid.status is Status.CLOSED
    assert "[changes requested by" in rid.reply


def test_request_changes_reworks_verified(rtd_verified):
    rid = request_changes_rid(rtd_verified, RID_ID, reviewer=REVIEWER, reason="regressed")
    assert rid.status is Status.CLOSED and rid.verified_by is None


def test_reopen_from_closed(rtd_closed):
    rid = reopen_rid(rtd_closed, RID_ID, reviewer=REVIEWER, reason="changed my mind")
    assert rid.status is Status.OPEN
```

- [ ] **Step 2:** run → FAIL (names undefined).
- [ ] **Step 3: implement** in `lifecycle.py`:

```python
def accept_disposition_rid(
    rtd: RTD, rid_id: str, *, reviewer: str, moderator: bool = False
) -> RID:
    """Close a finding: the reviewer accepts the owner's disposition (v3).

    The review-phase endpoint of a discussion; verification of the actual
    document edit happens later, in closeout, for accepted RIDs only."""
    if not reviewer:
        raise ValueError("a reviewer name is required to accept a disposition")
    if reviewer == rtd.meta.owner:
        raise ClosureAuthorityError("the owner identity may never close a finding")
    rid = _find(rtd, rid_id)
    role = Role.MODERATOR if moderator else Role.REVIEWER
    transition(rid, Status.CLOSED, actor_role=role, actor_name=reviewer)
    return rid


def request_changes_rid(
    rtd: RTD, rid_id: str, *, reviewer: str, reason: str, moderator: bool = False
) -> RID:
    """Send an implemented (or verified) RID back to ``closed`` for rework (v3),
    with a mandatory reason appended to its thread."""
    if not reviewer:
        raise ValueError("a reviewer name is required to request changes")
    if not reason or not reason.strip():
        raise ValueError("requesting changes requires a reason")
    rid = _find(rtd, rid_id)
    if reviewer == rtd.meta.owner:
        raise ClosureAuthorityError("the owner identity may never issue a verdict")
    if not moderator and rid.reviewer != reviewer:
        raise ClosureAuthorityError(
            f"only the RID's own reviewer ({rid.reviewer!r}) may request changes"
        )
    if rid.status not in (Status.IMPLEMENTED, Status.VERIFIED):
        raise TransitionError(
            f"cannot request changes on a RID in status {rid.status.value!r}"
        )
    note = f"[changes requested by {reviewer}: {reason.strip()}]"
    rid.reply = f"{rid.reply}\n{note}" if rid.reply else note
    rid.status = Status.CLOSED
    rid.verified_by = None
    rid.verified_on = None
    return rid
```

  In `reopen_rid` change the allowed-from check to
  `(Status.ANSWERED, Status.CLOSED, Status.IMPLEMENTED, Status.VERIFIED)`.
  `pending_for_reviewer` keeps `(ANSWERED, IMPLEMENTED)` — update its docstring:
  *"answered = awaiting accept-disposition; implemented = awaiting verification."*
- [ ] **Step 4:** `python -m pytest tests/test_lifecycle.py -q` → PASS.
- [ ] **Step 5:** `git commit -m "feat(domain): accept-disposition / request-changes lifecycle helpers"`

### Task 4: review phases + phase-gated services

**Files:**
- Modify: `src/malus/db/models.py:32-43` (ReviewStatus), `src/malus/services/core.py`
- Test: `tests/services/test_phases.py` (new)

**Interfaces produced (consumed by API/web and later steps):**

```python
class ReviewStatus(str, Enum):  # db/models.py
    DRAFT = "draft"; IN_REVIEW = "in_review"; CLOSEOUT = "closeout"; FINALIZED = "finalized"

class PhaseError(TransitionError): ...            # services/core.py → HTTP 409
def closeout_gate(session, review) -> list[str]   # [] when closeout may start
def start_closeout(session, review, *, by) -> Review
def reopen_review(session, review, *, by) -> Review          # closeout → in_review
def accept_disposition(session, review, rid_id, *, reviewer, moderator=False)
def request_changes(session, review, rid_id, *, reviewer, reason, moderator=False)
```

- [x] **Step 1: failing tests** — create `tests/services/test_phases.py` modeled on the
  existing service tests' session/review fixtures (see `tests/services/` for the pattern):

```python
def test_freeze_moves_review_to_in_review(session, review_factory):
    review = review_factory()          # created draft
    svc.freeze_baseline(session, review, "# doc", by=None)
    assert review.status == ReviewStatus.IN_REVIEW.value


def test_closeout_gate_requires_all_closed(session, review_with_rids):
    review = review_with_rids(statuses=["open"])
    assert svc.closeout_gate(session, review)          # blocked: open RID
    review2 = review_with_rids(statuses=["closed", "withdrawn"])
    assert svc.closeout_gate(session, review2) == []


def test_closeout_gate_requires_at_least_one_finding(session, review_with_rids):
    review = review_with_rids(statuses=["withdrawn"])
    assert svc.closeout_gate(session, review)          # blocked: nothing to review


def test_start_closeout_sets_phase(session, review_with_rids, owner):
    review = review_with_rids(statuses=["closed"])
    svc.start_closeout(session, review, by=owner)
    assert review.status == ReviewStatus.CLOSEOUT.value


def test_accept_disposition_only_in_review_phase(session, review_with_rids, reviewer_name):
    review = review_with_rids(statuses=["answered"])
    ReviewRepo(session).set_status(review, ReviewStatus.CLOSEOUT.value)  # force phase
    with pytest.raises(svc.PhaseError):
        svc.accept_disposition(session, review, RID_ID, reviewer=reviewer_name)


def test_verify_only_in_closeout(session, review_with_rids, reviewer_name):
    review = review_with_rids(statuses=["implemented"])   # phase still in_review
    with pytest.raises(svc.PhaseError):
        svc.verify(session, review, RID_ID, reviewer=reviewer_name)
```

  (Write the fixtures concretely in the file: `review_factory` wraps
  `svc.create_review`; `review_with_rids` freezes a baseline, harvests one
  comment per requested status via the existing test helpers in
  `tests/services/`, then force-sets RID statuses through the repo. Follow the
  established fixture style you find there — do not invent a parallel one.)
- [x] **Step 2:** run → FAIL.
- [x] **Step 3: implement** in `services/core.py`:

```python
class PhaseError(TransitionError):
    """The review is not in the phase this action requires (v3) → HTTP 409."""


def _require_phase(review: Review, *phases: ReviewStatus) -> None:
    if review.status not in {p.value for p in phases}:
        allowed = " | ".join(p.value for p in phases)
        raise PhaseError(
            f"review {review.review_id_str} is in phase {review.status!r}; "
            f"this action requires {allowed}"
        )
```

  Wire the gates (each is one line at the top of the existing function):

  | Service | Phase required |
  |---|---|
  | `add_reviewer_copy`, `harvest`, `answer`, `update_rid`, `discard_disposition_draft`, `apply_suggestions`, `reopen` | `IN_REVIEW` |
  | `accept_disposition` (new) | `IN_REVIEW` |
  | `implement`, `verify`, `request_changes` (new), `link_change` | `CLOSEOUT` |
  | `finalize` | `CLOSEOUT` |
  | `freeze_baseline` | `DRAFT` — and on success `ReviewRepo(session).set_status(review, ReviewStatus.IN_REVIEW.value)` |

  New services (same shape as `verify`/`reopen` at `core.py:517-556`):

```python
def accept_disposition(
    session: Session, review: Review, rid_id: str, *,
    reviewer: str, moderator: bool = False,
):
    _require_phase(review, ReviewStatus.IN_REVIEW)
    rtd = export_rtd(session, review)
    accept_disposition_rid(rtd, rid_id, reviewer=reviewer, moderator=moderator)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(
        action="accept_disposition", target=f"rid:{rid_id}",
        actor=UserRepo(session).get_or_create(reviewer),
        detail={"moderator": moderator},
    )
    return RidRepo(session).get(review, rid_id)


def request_changes(
    session: Session, review: Review, rid_id: str, *,
    reviewer: str, reason: str, moderator: bool = False,
):
    _require_phase(review, ReviewStatus.CLOSEOUT)
    rtd = export_rtd(session, review)
    request_changes_rid(rtd, rid_id, reviewer=reviewer, reason=reason, moderator=moderator)
    sync_rtd_to_review(session, review, rtd)
    AuditRepo(session).log(
        action="request_changes", target=f"rid:{rid_id}",
        actor=UserRepo(session).get_or_create(reviewer),
        detail={"reason": reason},
    )
    return RidRepo(session).get(review, rid_id)


def closeout_gate(session: Session, review: Review) -> list[str]:
    """Empty list when closeout may start (spec §Closeout entry): ≥1
    non-withdrawn finding and none still open/answered (legacy v2
    implemented/verified rows pass)."""
    rows = RidRepo(session).list(review)
    errors: list[str] = []
    live = [r for r in rows if r.status != Status.WITHDRAWN.value]
    if not live:
        errors.append("closeout needs at least one non-withdrawn finding")
    stuck = [r.rid_str for r in live
             if r.status in (Status.OPEN.value, Status.ANSWERED.value)]
    if stuck:
        errors.append("findings not yet closed: " + ", ".join(sorted(stuck)))
    return errors


def start_closeout(session: Session, review: Review, *, by=None) -> Review:
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.IN_REVIEW)
    errors = closeout_gate(session, review)
    if errors:
        raise PhaseError("; ".join(errors))
    ReviewRepo(session).set_status(review, ReviewStatus.CLOSEOUT.value)
    AuditRepo(session).log(action="start_closeout",
                           target=f"review:{review.review_id_str}", actor=by)
    return review


def reopen_review(session: Session, review: Review, *, by=None) -> Review:
    """Admin escape hatch: closeout → in_review (spec §Closeout entry)."""
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.CLOSEOUT)
    ReviewRepo(session).set_status(review, ReviewStatus.IN_REVIEW.value)
    AuditRepo(session).log(action="reopen_review",
                           target=f"review:{review.review_id_str}", actor=by)
    return review
```

  `implement()` needs no transition change (Task 1 moved `IMPLEMENTED`'s source to
  `CLOSED` in the graph; the function body is unchanged). Update the v3
  `finalize()` gate (replacing `core.py:621-625`):

```python
    blocking = [
        r.rid for r in rtd.rids
        if not (
            r.status in (Status.VERIFIED, Status.WITHDRAWN)
            or (r.status is Status.CLOSED
                and r.disposition in (Disposition.REJECTED, Disposition.DEFERRED))
        )
    ]
    if blocking:
        errors.append("findings not yet verified/closed: " + ", ".join(blocking))
```

  Update `ReviewStatus` in `db/models.py`: `DRAFT/IN_REVIEW/CLOSEOUT/FINALIZED`
  (delete `ACTIVE`; refresh the docstring — the phase model is no longer provisional).
- [x] **Step 4:** `python -m pytest tests/services -q` → PASS. Then the FULL suite:
  many existing service/web/api/mcp/e2e tests exercise v2 flows (`verify`
  straight from `answered`, no phases). Update them to the v3 flow using this
  mapping — mechanical, no semantics choices left:

  | v2 test flow | v3 equivalent |
  |---|---|
  | `answer → verify` (rejected/deferred) | `answer → accept_disposition` (status `closed` is their terminal) |
  | `answer → implement → verify` | `answer → accept_disposition → start_closeout → implement → verify` |
  | `reopen` from `verified` | in closeout use `request_changes`; from `answered/closed` keep `reopen` |
  | review created then acted on | freeze already flips it to `in_review` (web fixtures unaffected) |
  | `finalize` precondition | accepted → `verified`; rejected/deferred → `closed` |
  | legacy v0 GUI constants (`tests/test_gui_constants.py`, `tests/test_gui.py::test_generated_constants_in_sync_with_python`) | regenerate the JS constants block in `gui/rtd.html` from `malus.gui_constants` so it matches the v3 `Status`/`TRANSITIONS` |
- [x] **Step 5:** `python -m pytest -q` → 354 passed, 6 failed (unchanged from
  before this task — `tests/api/test_api.py::test_full_pipeline_over_http`,
  `tests/e2e/test_v1_e2e.py`, `tests/web/test_admin_superuser.py`,
  `tests/web/test_document_viewer.py`, `tests/web/test_editor.py`,
  `tests/web/test_web.py`; all four owned by Task 6/Task 7, not yet done).
  `git commit -m "feat(services): v3 review phases + accept/request-changes + phase gates"`

#### Deviations

- `tests/services/` did not exist yet; added `tests/services/conftest.py`
  (mirrors `tests/db/conftest.py`'s `engine`/`session` fixtures verbatim) so
  `test_phases.py` has a session to run against.
- `test_phases.py` implements the brief's 6 illustrative tests plus ~21 more,
  one per phase-gated service in the table above (both the "blocked outside
  its phase" and one representative happy path each), since this is the
  pivotal task of the cycle and the gate table has no other test coverage.
- The legacy importer (`legacy/importer.py`) needed **no change**: it calls
  `create_review` (→ `DRAFT`) then `freeze_baseline`, which now flips the
  phase to `IN_REVIEW` on its own. A v0 import with an already-finalized
  review isn't exercised by any fixture (`tests/fixtures/sample-review` has
  no RIDs), so that case is deferred to whoever needs it (no fixture forces a
  decision either way).
- `stale __pycache__` directories left over from an earlier checkout at a
  different path (`ALUM/code/maluS`) were baking wrong `co_filename`s into
  cached bytecode and were deleted repo-wide before running any tests (not a
  code change, just build-cache hygiene).

### Task 5: startup migration backfill

**Files:**
- Modify: `src/malus/db/session.py` (where `create_all`/init runs)
- Test: `tests/db/test_migration_v3.py` (new)

- [ ] **Step 1: failing test:**

```python
def test_backfill_draft_with_baseline_becomes_in_review(engine, session):
    review = svc.create_review(session, review_id="R-1", document_name="d.md", owner="own")
    svc.freeze_baseline(session, review, "# doc", by=None)
    ReviewRepo(session).set_status(review, "draft")     # simulate a pre-v3 row
    migrate_review_phases(session)
    assert review.status == "in_review"


def test_backfill_leaves_unfrozen_draft(engine, session):
    review = svc.create_review(session, review_id="R-2", document_name="d.md", owner="own")
    migrate_review_phases(session)
    assert review.status == "draft"
```

- [ ] **Step 2:** run → FAIL. **Step 3: implement** in `db/session.py`:

```python
def migrate_review_phases(session: Session) -> None:
    """v3 one-time backfill: pre-v3 'draft'/'active' reviews with a frozen
    baseline become 'in_review'. Idempotent."""
    from malus.db.models import Review, ReviewStatus
    from malus.repo import ReviewRepo, VersionRepo

    rows = session.exec(
        select(Review).where(Review.status.in_(("draft", "active")))
    ).all()
    for review in rows:
        if VersionRepo(session).baseline(review) is not None:
            ReviewRepo(session).set_status(review, ReviewStatus.IN_REVIEW.value)
```

  Call it right after `create_all` in the existing init path (open a short-lived
  session there, matching how init already gets one).
- [ ] **Step 4:** run new tests + full suite → PASS.
- [ ] **Step 5:** `git commit -m "feat(db): v3 phase backfill for pre-v3 reviews"`

### Task 6: API endpoints

**Files:**
- Modify: `src/malus/api/routes.py` (beside verify/reopen at :432-447 and finalize at :491-502)
- Test: `tests/api/test_lifecycle_v3.py` (new; model on the existing verify-route tests)

**Interfaces produced:** `POST /reviews/{id}/rids/{rid}/accept`,
`POST /reviews/{id}/rids/{rid}/request-changes` (JSON body `{"reason": str}`),
`POST /reviews/{id}/start-closeout`, `POST /reviews/{id}/reopen-review`.

- [ ] **Step 1: failing tests** covering: reviewer accepts own answered RID (200,
  status `closed`); owner accept → 403; AI accept → 403; accept in closeout → 409;
  start-closeout with an open RID → 409 and with all closed → 200 phase `closeout`;
  request-changes without reason → 422; reopen-review by non-admin → 403.
- [ ] **Step 2:** run → FAIL. **Step 3: implement** — each route mirrors
  `verify`'s shape: resolve review + RID (404), `authz.require_verify` for
  accept/request-changes (returns `moderator` flag), `authz.require_owner` for
  start-closeout, admin check (`user.is_admin and not user.is_ai`, else 403) for
  reopen-review; call the Task-4 service; `PhaseError` already maps to 409 via the
  `TransitionError` handler in `api/errors.py` (verify this and add the case if not).
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(api): v3 lifecycle endpoints (accept, request-changes, closeout)"`

### Task 7: web wiring — routes, viewer buttons, dashboard phase actions

**Files:**
- Modify: `src/malus/web/router.py` (mutations block :362-432; `_document_context`
  :535-627; `review_page` :233+; `_FACET_VALUES` :201)
- Modify: `src/malus/web/static/document-viewer.js` (cardEl action block :334-356)
- Modify: `src/malus/web/templates/review.html` (owner actions block :18-31)
- Modify: `src/malus/web/templates/document.html` (role banners :7-34)
- Test: `tests/web/test_lifecycle_v3.py` (new) + existing web tests updated

- [x] **Step 1: failing web tests** covering: POST `…/rids/{rid}/accept` as the RID's
  reviewer → 303 and RID `closed`; as owner → 403; POST `…/start-closeout` as owner
  with gate satisfied → 303 and phase `closeout`; POST `…/rids/{rid}/request-changes`
  in closeout → 303 and RID back to `closed` with reason in reply; dashboard HTML
  contains `Start closeout` only for owner with gate satisfied.
- [x] **Step 2:** run → FAIL. **Step 3: implement:**

  Router — add beside `verify_action` (`router.py:401`), same shape (auth,
  404, `authz.require_verify` / `authz.require_owner`, redirect to
  `…/document?focus={rid}` or the dashboard):

```python
@web.post("/ui/reviews/{review_id}/rids/{rid}/accept")
def accept_action(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    ...
    on_behalf = authz.require_verify(session, review, user, row)
    svc.accept_disposition(session, review, rid, reviewer=user.display_name, moderator=on_behalf)
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/request-changes")
def request_changes_action(review_id: str, rid: str, request: Request,
                           reason: str = Form(...), session: Session = Depends(get_session)):
    ...  # authz.require_verify, then:
    svc.request_changes(session, review, rid, reviewer=user.display_name,
                        reason=reason, moderator=on_behalf)


@web.post("/ui/reviews/{review_id}/start-closeout")
def start_closeout_action(review_id: str, request: Request, session: Session = Depends(get_session)):
    ...  # authz.require_owner + forbid_ai_commit, then:
    svc.start_closeout(session, review, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)


@web.post("/ui/reviews/{review_id}/reopen-review")
def reopen_review_action(review_id: str, request: Request, session: Session = Depends(get_session)):
    ...  # admin human only (403 otherwise), then svc.reopen_review
```

  `_document_context`: add `"phase": review.status` to `data` (top level, beside
  `reviewId`). `review_page`: compute `phase = review.status`,
  `closeout_errors = svc.closeout_gate(session, review) if phase == 'in_review' else []`,
  pass both to the template; add `"closed"` to `_FACET_VALUES["status"]` (after
  `"answered"`); count `closed` in the progress metric as settled
  (`closed|verified|withdrawn` over total).

  `document-viewer.js` — replace the verify/reopen block (:334-356) with
  phase-aware buttons (`var phase = data.phase;` once at the top of `cardEl`):

```js
    if (r && r.canVerify && phase === "in_review" && r.status === "answered") {
      var accept = document.createElement("button");
      accept.type = "button";
      accept.className = "primary cp-accept";
      accept.textContent = "Accept disposition";
      accept.addEventListener("click", function (ev) {
        ev.stopPropagation();
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/accept", {});
      });
      actions.appendChild(accept);
    }
    if (r && r.canVerify && phase === "in_review" && (r.status === "answered" || r.status === "closed")) {
      var reopen = document.createElement("button");
      reopen.type = "button";
      reopen.className = "cp-reopen";
      reopen.textContent = "Reopen…";
      reopen.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var reason = window.prompt("Reopen reason for " + r.rid + ":");
        if (reason) post(base + "/rids/" + encodeURIComponent(r.rid) + "/reopen", { reason: reason });
      });
      actions.appendChild(reopen);
    }
    if (r && r.canVerify && phase === "closeout" && r.status === "implemented") {
      var verify = document.createElement("button");
      verify.type = "button";
      verify.className = "primary cp-verify";
      verify.textContent = "Verify";
      verify.addEventListener("click", function (ev) {
        ev.stopPropagation();
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/verify", {});
      });
      actions.appendChild(verify);
      var rc = document.createElement("button");
      rc.type = "button";
      rc.className = "warn cp-request-changes";
      rc.textContent = "Request changes…";
      rc.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var reason = window.prompt("What still needs work on " + r.rid + "?");
        if (reason) post(base + "/rids/" + encodeURIComponent(r.rid) + "/request-changes", { reason: reason });
      });
      actions.appendChild(rc);
    }
    if (r && r.canVerify && phase === "closeout" && r.status === "verified") {
      // reopen a verdict during closeout = request changes (verified → closed)
      var undo = document.createElement("button");
      undo.type = "button";
      undo.className = "cp-reopen";
      undo.textContent = "Reopen…";
      undo.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var reason = window.prompt("Reopen reason for " + r.rid + ":");
        if (reason) post(base + "/rids/" + encodeURIComponent(r.rid) + "/request-changes", { reason: reason });
      });
      actions.appendChild(undo);
    }
```

  Also gate the dispose toggle (`:317`) on phase: `data.canDispose && r.status === "open" && phase === "in_review"`.

  `review.html` owner actions block (:18-31) — replace the implement link with
  phase-aware actions:

```jinja
  {% if phase == 'in_review' %}
    {% if not closeout_errors %}
    <form method="post" action="/ui/reviews/{{ review.review_id_str }}/start-closeout" class="inline"
          onsubmit="return confirm('Start closeout? New comments will be locked; the owner implements the accepted findings and reviewers verify them.')">
      <button class="primary">Start closeout</button>
    </form>
    {% else %}
    <span class="muted" title="{{ closeout_errors|join('; ') }}">Closeout unlocks when every comment is closed.</span>
    {% endif %}
  {% elif phase == 'closeout' %}
    <a class="btn" href="/ui/reviews/{{ review.review_id_str }}/implement">Closeout workspace</a>
    {% if user.is_admin %}
    <form method="post" action="/ui/reviews/{{ review.review_id_str }}/reopen-review" class="inline"
          onsubmit="return confirm('Reopen the review phase? Reviewers can comment again.')">
      <button class="linkbtn">Back to review</button>
    </form>
    {% endif %}
  {% endif %}
```

  (The `/implement` page is replaced by the closeout workspace in step 02; here
  just add `svc._require_phase(review, ReviewStatus.CLOSEOUT)` — via a small
  public helper or by catching `PhaseError` → 409 — to `implement_page`/`implement_submit`.)
  Update the owner/reviewer banners in `document.html` to mention the two phases
  (reviewer in closeout: *"verify the changes made for your comments"*).
- [x] **Step 4:** `python -m pytest -q` → full suite PASS.
- [x] **Step 5:** `git commit -m "feat(web): v3 phase-aware actions — accept disposition, closeout, request changes"`

### Task 8: spec docs

**Files:**
- Modify: `docs/spec/rid-schema.md` (§3 lifecycle), `docs/spec/data-model.md` (Review.status)

- [ ] **Step 1:** update §3: the v3 status list (`open, answered, closed, implemented,
  verified, withdrawn`), the forward graph from Task 1, the backward moves
  (reopen, request-changes) with their authority, and the phase table
  (`draft/in_review/closeout/finalized`, entry/exit gates). Mark v2's
  `answered→verified` path as removed in v3. Note in data-model.md that
  `ReviewStatus.ACTIVE` was dropped and backfilled.
- [ ] **Step 2:** `git commit -m "docs(spec): v3 lifecycle — closed status, review phases"`

## Deviations

- Task 4 (review follow-up): `triage` gained an `IN_REVIEW` phase gate — the
  spec's phase table did not enumerate it, but triage is a review-phase
  activity by process definition. `retract_comment` stays deliberately
  ungated: a reviewer withdraw needs an OPEN rid (impossible in closeout by
  gate), admin withdraw remains the any-phase escape hatch. To be ratified by
  Alberto at step close.
- Task 4: imported already-finalized v0 reviews keep status `finalized`
  (no fixture exercises re-freezing them; importer unchanged).
- Task 7: the brief's dashboard hint (`title="{{ closeout_errors|join('; ') }}"`)
  was changed to a count (`title="{{ closeout_errors|length }} check(s) not yet
  met…"`), dropping the RID names `svc.closeout_gate` embeds in its message —
  literal RID text in a page-wide `title` attribute broke five pre-existing
  `tests/web/test_filters.py` assertions that check a filtered-out RID's
  absence from the *whole* page. The findings table already shows which rows
  are open/answered, so no information is lost; only its placement changed.
  To be ratified by Alberto at step close.
- Task 7: `tests/e2e/test_v1_e2e.py::test_full_multi_user_review_to_finalize`
  needed a v3 rewrite (dispose → accept → start-closeout → implement → verify,
  per-actor) since the new `implement` phase guard 409s the old dispose→implement
  shortcut; per the task brief this was in scope as "the last one standing."
- Task 7: `implement_page`'s `accepted` filter moved from `status is ANSWERED`
  to `status is CLOSED` — in v3 an accepted RID is `closed` (post-accept) by
  the time closeout is reached, never `answered` (the closeout gate forbids
  entering closeout with any `answered` RID), so the old predicate would have
  always rendered "No accepted findings are awaiting implementation."

## Definition of Done

- [ ] All deliverables checked; `python -m pytest -q` green.
- [ ] Manual smoke (`malus serve`): review with 1 comment → dispose → Accept
  disposition → Start closeout appears → phase flips → verify buttons appear
  only in closeout.
- [ ] No new runtime dependencies (`pyproject.toml` untouched).

## Out of scope (later steps)

Closeout workspace UI (02), per-RID diff (03), finalize GUI/downloads/PDF (04),
signing (05).
