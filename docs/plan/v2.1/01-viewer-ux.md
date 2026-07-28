# v2.1 Step 1 — Viewer UX: click focus, history timeline, unified actions

## Objective

Three entangled card/viewer changes: focus driven purely by clicks (no
explicit controls), an append-only per-RID history timeline, and one
role-filtered action row per card.

## Files

- Modify: `src/malus/repo/repositories.py` — `AuditRepo.for_targets(targets)
  -> list[AuditLog]` (one grouped query, ordered by ts).
- Modify: `src/malus/services/core.py` — enrich `answer` detail
  (`{"disposition", "reply"?}`) and `update_rid` detail
  (`{"changed": {field: new_value}}`).
- Modify: `src/malus/web/router.py` — `_document_context` adds per-RID
  `history`: `[{action, actor, ts (iso), detail}]` from audit rows with
  `target == f"rid:{rid}"`.
- Modify: `src/malus/web/static/document-viewer.js` — card: record view
  (disposition/reply/resolution as text), History section, unified action
  row; focus: click marker/card = focus, click another = move, click
  elsewhere or ESC = exit (history.replaceState, no reload), remove
  `cp-focus-close`; selection never exits focus.
- Modify: `src/malus/web/static/app.css` — timeline + action-row styles.
- Test: extend `tests/web/test_document_viewer.py`.

## Deliverables (TDD)

- [x] Failing tests: payload rids carry `history` with the `answer` event
      (action, actor display name, iso ts, disposition in detail) after a
      dispose; `update_rid` events carry `changed`; history ordered by ts;
      a RID with no events has `history: []`.
- [x] Implement repo + service enrichment + payload.
- [x] JS/CSS rework (focus semantics, record view, timeline, action row).
- [x] Browser verification: dispose → change disposition → both events in
      timeline; focus moves between comments by click; click-away and ESC
      exit; reviewer selection with focus active still opens the popover.
- [x] Suite green; commit
      `feat(web): click focus, per-RID history timeline, unified card actions (v2.1 step 1)`.

## Definition of Done

No focus buttons remain; saved values are never shown as editable defaults
without an explicit action; every card shows only usable buttons; timeline
is append-only and survives disposition changes.

## Sources

- `00-design.md` decisions 1–3; audit calls in `services/core.py:399-511`.
