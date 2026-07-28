# v2.3 Step 1 — Filter builder with operators

## Files
- Modify: `src/malus/web/router.py` — parse `f=facet:op:value` (split
  maxsplit 2; facets status/reviewer/type/severity/disposition/comment; ops
  eq/ne, contains for comment); builder params `facet`/`op`/`value` fold
  into canonical `?f=` via 303; context: `tokens` (with remove hrefs) +
  `filter_options`.
- Modify: `review.html` — builder form + token row (chips row removed).
- Modify: `app.css` — `.filter-bar`, `.token` styles.
- Test: rewrite `tests/web/test_filters.py`.

## Deliverables (TDD)
- [ ] Tests: OR within field (`f=status:eq:open&f=status:eq:answered`), AND
      across fields, `ne` excludes, `comment contains` matches
      case-insensitive, withdrawn hidden unless `status:eq:withdrawn`,
      builder GET → 303 canonical, token remove hrefs drop one condition,
      malformed `f` ignored (no 500).
- [ ] Implement + browser verification.
- [ ] Suite green.

## DoD
Complex simultaneous filters expressible and shareable; no dropdown-only
single-choice limitation; no JS required for core flow.
