# maluS v2.2 — Design (validated)

**Status:** approved by Alberto Boffi, 2026-07-28; briefly deferred, then
**implemented and released as v2.2.0 in the same session** on Alberto's
request. No schema change, no migration.

## Decisions

| Topic | Decision |
|---|---|
| Declutter | Actions row: only "Implement accepted findings", shown **only when** accepted+answered findings exist; "Copy review link" + "Delete review" move into a CSS `<details>` "⋯" menu; the "Members" button is removed (duplicate of the sidebar). The 7 metric cards become one compact strip: progress ring + findings count + **non-zero** status pills (withdrawn muted). Submissions slims to a single inline row. |
| Filters | The 5 single-select dropdowns + Filter button become **toggle chips** grouped per facet; each chip is a plain link that adds/removes its value from the query string (repeated params, e.g. `?status=open&status=answered`) — multi-select, zero JS, shareable URLs. |
| Withdrawn | Hidden from the RTD table **by default** (no status filter active). A muted "withdrawn (N)" chip re-includes them. Progress semantics unchanged (withdrawn still counts as closed). |
| Purge | Delete keeps v1.8 semantics (pristine → hard-delete, acted-upon → withdrawn). NEW: **admin-only "Purge permanently"** in the viewer focus card — removes the RID definitively (traceability links cleared, duplicate back-refs nulled), double confirmation, audit `purge_rid` records the comment text as the final trace. |

## Steps

| # | File | Scope |
|---|---|---|
| 1 | `01-dashboard.md` | declutter + chip filters + withdrawn default-hidden |
| 2 | `02-purge.md` | purge_rid service + admin route + viewer control |
| 3 | `03-release.md` | CHANGELOG, bump 2.2.0, tag, push |

## Sources

- Alberto's request + dashboard screenshot, this session (2026-07-28).
- `src/malus/web/router.py` (review_page filters), `review.html`,
  `services/core.py` (retract_comment / delete_review patterns).
