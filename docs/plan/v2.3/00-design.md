# maluS v2.3 — Design (validated)

**Status:** approved by Alberto Boffi, 2026-07-28 (this session). No schema
change, no migration.

## Decisions

| Topic | Decision |
|---|---|
| Filters | Chips (v2.2) are replaced by a **filter builder**: field (status, reviewer, type, severity, disposition, comment) + operator (`=`, `≠`; `contains` for comment) + value, added as removable **tokens**. Different fields AND together; multiple `=` on one field are OR (IN); `≠` always excludes. URL encoding `?f=facet:op:value` (repeated). The builder form submits plain GET params (`facet`/`op`/`value`) that the server folds into the canonical `?f=` URL via 303 — works without JS; a tiny inline script swaps the value control (select ⇄ text) when the field is `comment`. Withdrawn stay hidden unless `status = withdrawn` is an active condition. |
| Dispose | The Dispose… button appears **only on open findings** (AI proposals included). "Change disposition" is removed: changing an answered finding goes through the formal **reopen** (status back to open → Dispose reappears). Timeline unchanged (append-only). |
| Withdraw/Purge | In the viewer card the "✕ delete" link becomes a **Withdraw** button with the same visual weight as **Purge permanently** — amber vs red. **Both admin-only in the card.** Reviewers keep managing their own comments via the local editor delete; the RTD-table control keeps its v1.8 authz (own+open reviewer, admin) but is relabeled "withdraw". The owner sees neither. |
| Focus/hover colors | No foreign colors on cards: hover border, active ring, and focus glow all use the card's `--rev-color` (reviewer's color) — the teal focus ring and the coral (pink) hover override are removed, incl. the `.sugg` teal border-left override. |
| Users table | Restructured to fit the viewport (no horizontal scroll at ≥1024px): Account (name + @username stacked), Status (kind/active/pw pills), Color, compact Actions with reset-password inside a "⋯" menu. Vertical scroll only. |

## Steps

| # | File | Scope |
|---|---|---|
| 1 | `01-filters.md` | filter builder + tokens + `?f=` parser |
| 2 | `02-card-actions.md` | dispose-open-only, Withdraw/Purge pair, rev-color focus/hover |
| 3 | `03-users-table.md` | Users page layout fits viewport |
| 4 | `04-release.md` | CHANGELOG, bump 2.3.0, tag, push, Open Brain |

## Sources

- Alberto's five requests, this session (2026-07-28); current
  `review.html`/`document-viewer.js`/`app.css`/`admin_users.html`.
