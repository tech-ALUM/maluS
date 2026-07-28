# v2.2 Step 2 — Admin-only permanent purge of a comment

## Files

- Modify: `src/malus/services/core.py` — `purge_rid(session, review, rid_id, *, by)`:
  guards (`by.is_admin` and not `by.is_ai` — route also gates), deletes the
  RID's `RidChange` rows, nulls `master_id` back-references from duplicates,
  deletes the RID row, audit `purge_rid` with
  `{"reviewer", "comment"}` as the final trace.
- Modify: `src/malus/web/router.py` — `POST /ui/reviews/{id}/rids/{rid}/purge`
  (admin-only → 403, missing → 404, redirect to the dashboard); viewer
  payload rids gain `canPurge` (admin && human).
- Modify: `src/malus/web/static/document-viewer.js` — "Purge permanently"
  (danger) in the card action row when `canPurge`, double `confirm()`.
- Test: `tests/web/test_purge.py` (new).

## Deliverables (TDD)

- [x] Failing tests: admin purges an acted-upon (answered/withdrawn) RID —
      row gone from table, payload and API; audit `purge_rid` written with
      the comment text; owner/reviewer/moderator/AI get 403; unknown RID 404;
      a duplicate pointing at the purged master survives with master cleared.
- [x] Implement service + route + JS.
- [x] Browser verification: purge a withdrawn comment via chip → focus → purge.
- [x] Suite green.

## Definition of Done

Only a human admin can purge; the RID disappears everywhere; the audit row
is the only remaining trace; normal delete semantics untouched.
