# v2.2 Step 1 — Dashboard declutter, chip filters, withdrawn hidden

## Files

- Modify: `src/malus/web/router.py` — `review_page`: filter params become
  lists (FastAPI repeated query params); `keep()` matches against sets;
  withdrawn excluded when no status filter is active; context gains
  `accepted_waiting` (accepted+answered count), `withdrawn_count`, and
  `chips` (per-facet: value, active, toggle href — hrefs built server-side
  with urlencode).
- Modify: `src/malus/web/templates/review.html` — actions row (conditional
  Implement + `<details class="menu">` with Copy link + Delete review; no
  Members button), compact metrics strip (ring + findings + non-zero
  status pills), slim submissions row, chips row replacing the filter form.
- Modify: `src/malus/web/static/app.css` — `.menu` dropdown, `.metrics-strip`,
  `.chip-filter` (+ active), slim submissions.
- Test: extend `tests/web/test_web.py` / new `tests/web/test_filters.py`.

## Deliverables (TDD)

- [ ] Failing tests: withdrawn rows absent by default and present with
      `?status=withdrawn`; multi-select works (`?status=open&status=answered`
      shows both, others excluded); combined facets AND together; chips
      carry toggle hrefs (active chip's href removes its value); Implement
      button only with accepted+answered findings; Members button gone.
- [ ] Implement route + template + CSS.
- [ ] Browser verification: declutter layout, chip toggling, withdrawn flow.
- [ ] Suite green.

## Definition of Done

Default dashboard shows no withdrawn rows and no zero-count noise; every
filter facet is multi-selectable via chips; no functional regression
(implement/copy-link/delete still reachable).
