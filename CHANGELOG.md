# Changelog

## v1.7.1 — 2026-07-15 (harden the AI-owner guard)

- **Fix (AI guardrail)**: an AI co-owner could still mutate review content —
  `freeze`, `set-document`, `create-change`, `apply-suggs` were only behind
  `require_owner`, so only the finding transitions (answer/implement/finalize)
  were guarded. The `is_ai` commit guard now also covers `freeze_baseline`,
  `save_version` and `apply_suggestions`, so an AI co-owner can **only** draft a
  disposition. Human owners are unaffected (the guard is `is_ai`-specific). Found
  by a post-release self-review; no schema change.

## v1.7.0 — 2026-07-15 (reviewer draft-save + AI co-owner drafted dispositions)

Ships two feature sets developed back-to-back (planned as v1.6 and v1.7); cut as
one release since both were merged before the release was tagged.

- **Reviewer draft-save + submission panel** (v1.6): the reviewer copy now has a
  **Save draft** action (persist + harvest, *not* submitted) alongside
  **Submit**, so reviewers comment incrementally across sessions and see their
  comments in the RTD table immediately; reopening the editor shows prior
  comments. The dashboard gains a **reviewer-submission panel** — each reviewer
  shown as not-started / draft / submitted, an N/M count, and a soft "all
  submitted" notice that blocks nothing (the owner decides when to proceed). API
  parity: `PUT /reviews/{id}/copies/{user}` saves a draft, `POST …/submit`
  submits. The editor form opts out of `hx-boost` so the clicked button's action
  reaches the server (htmx 2.x drops a submit button's value). No schema change.
- **AI co-owner drafted dispositions, human-confirmed** (v1.7): an AI account can
  hold the **owner role** as a co-owner and **draft** dispositions — over the API
  or the new `submit_disposition` MCP tool — where a draft is a still-`OPEN` RID
  marked `ai_drafted`. A **human owner confirms** it in the GUI (the existing
  dispose form, pre-filled) or **discards** it. The `is_ai` guard refuses every
  committing owner transition (`answer` / `implement` / `finalize` → 403) in the
  services and at the API boundary; verify/close stay reviewer-side, so the
  closure invariant is untouched. GUI: an "AI proposal" banner + Confirm/Discard,
  an RTD "AI" badge, and a dashboard "AI proposals" tile. No new role or status,
  no schema change.

## v1.5.0 — 2026-07-12 (delete a review)

- **Delete a review from the GUI**: the primary owner (or a global admin) can
  permanently delete a whole review from the dashboard, behind a confirmation
  page. A transactional `delete_review` cascades the review's children
  (`RidChange`, `RID`, `ReviewerCopy`, `ReviewerNote`, `ReviewMember`,
  `DocumentVersion`, `Document`) then the `Review`, and writes a `delete_review`
  audit entry (audit rows are kept). Reviewers and moderators are refused (403)
  and never see the control. Irreversible; no schema change.

## v1.4.2 — 2026-07-12

- **Fix (packaging)**: the app icon and web-app manifest were missing from a
  non-editable install (the Docker image), so a deployed instance served the
  `<link rel="icon">` but 404'd on `/static/icon.svg` — no favicon. The
  setuptools `package-data` for `malus.web` only matched `*.css`/`*.js`; the new
  `icon.svg`/`manifest.json` were excluded. Broadened to `static/*` +
  `static/vendor/*` so all static assets ship. **Rebuild the image**
  (`docker compose up -d --build`) to pick it up.

## v1.4.1 — 2026-07-12

- **Reviewer editor polish**: the A4 sheet no longer clips its white background
  before the end of a long document (the fixed A4 aspect-ratio is dropped; the
  page now grows with its content). The rendered document is **~50% wider** — the
  editor breaks out of the 960px content column.
- **App icon**: a coral **"S"** is now the browser-tab favicon and the web-app
  manifest icon, so maluS shows a proper icon in the tab and when installed
  (`icon.svg`, `manifest.json`, `theme-color`).

## v1.4.0 — 2026-07-12 (reviewer editor: A4 view + comments panel)

- **Reviewer editor redesign**: the reviewer's copy now opens as a single
  **rendered A4 sheet** (no more raw two-column split). Comments render **in
  red** inline; a **Word-style comments panel** lists them and, on click,
  scrolls to the marker and highlights it briefly. Comments are added by
  **selecting text** in the sheet. Each comment carries a **private per-reviewer
  note** (new `ReviewerNote` store + migration; `GET/PUT /ui/reviews/{id}/my-notes`,
  reviewer-scoped, never harvested or shared). The Markdown copy is reconstructed
  on submit and posted to the unchanged edit-copy endpoint (same freeze
  validation + harvest); the owner's implement editor is untouched. No new
  runtime dependency.

## v1.3.0 — 2026-07-12 (admin hard-delete of users)

- **Admin hard-delete of a user account** from the GUI
  (`/ui/admin/users/{username}/delete`): a confirmation step transfers each
  review the user primary-owns to an admin-chosen **new owner**, reassigns their
  findings, verifications, document versions and audit entries to a shared
  **"Deleted user"** sentinel (records preserved, identity erased), removes their
  memberships and draft copies, then deletes the account. Guards: admin-only;
  you cannot delete yourself or the sentinel (409); an owned review without a
  valid new owner is refused (422). **Deactivate** remains the reversible soft
  option. No schema change / no migration.

## v1.2.0 — 2026-07-12 (member management & reviewer onboarding)

- **Reviewer account picker + member management** (Step 1): the Members page
  assigns *existing* accounts through a searchable typeahead (by stable
  `username`) — a typo can no longer spawn a phantom user; plus inline role
  change and member removal. An owner-safety guard keeps the primary owner
  (`Review.owner_id`) from being demoted/removed, so a review always has ≥1
  owner; removing a member preserves their harvested RIDs.
- **Reviewer onboarding & hand-off** (Step 2): after assignment a reviewer is
  pointed straight to commenting — a prominent landing CTA on the review page, a
  "Copy review link" control for owner/admin, and a "to comment" badge in the
  review list that clears once the reviewer submits. No email/SMTP: the link is
  the existing authenticated review URL.
- **API hardening**: `POST /reviews/{id}/reviewers` now requires an existing,
  active account and rejects an unknown/inactive name (422) instead of creating
  a placeholder — consistent with the GUI. Bulk `create_review` and the legacy
  `import` path are unchanged (import still materializes placeholder users from
  `rtd.yaml` names by design).

## v1.1.0 — 2026-07-10 (self-hosting hardening)

- **Account-management GUI** (Step 10): self-service password change, admin user
  CRUD (create incl. AI reviewer, deactivate/reactivate, reset password), and
  per-review role assignment — server-side, admin-gated; forced password change
  at first login. Closure invariant unchanged.
- **Caddy in docker-compose** (Step 11): a `caddy` service terminates TLS on
  80/443 and proxies to the app (loopback-only) over the compose network;
  `MALUS_DOMAIN` for auto-HTTPS. One-command HTTPS deploy.
- **Create a review from the GUI** (Step 12): `/ui/reviews/new` (create + freeze
  in one step; creator = owner); login now shows an error on wrong credentials.

## v1.0.0 — 2026-07-10

maluS becomes a **self-hosted web application**. The reusable domain core
(`models`, `parser`, `triage`, `lifecycle`, `report`) is unchanged; persistence
and transport are replaced.

### Added
- **Database store** (SQLModel on SQLite/WAL, Postgres-ready) + Alembic
  migrations; `docs/spec/data-model.md`. Freeze is an immutable `DocumentVersion`
  (content hash); RID traceability is `RidChange` + an `AuditLog` (ADR 0001/0002).
- **Repository + service layer** — the whole pipeline runs on the DB.
- **HTTP API** (FastAPI, OpenAPI at `/docs`) — one typed contract for the GUI and
  the AI agent; `malus serve`.
- **Authentication & RBAC** — argon2 passwords, httponly `SameSite=strict`
  session cookies, review-scoped roles (owner/reviewer/moderator + global admin),
  first-run admin bootstrap. Closure invariant enforced server-side; every
  mutation is attributed in the audit log.
- **Web GUI** (server-rendered Jinja + HTMX, ALUM styling): login, review list,
  dashboard, filterable RTD table, disposition/verify, and an in-browser Markdown
  **editor** (reviewer commenting + owner implementation with RID-linked versions).
- **AI reviewer via MCP** — `malus mcp` exposes review tools driven by an
  interactive Claude Code session; **no paid Anthropic API** on the server. AI
  principals can never verify/close/confirm (`is_ai` guardrail). Optional paid
  server-side engine behind `MALUS_AI_ENGINE`, off by default.
- **Deployment** — Dockerfile + docker-compose (optional Postgres), `.env.example`,
  reverse-proxy TLS sample, backup/restore scripts, `/health`, JSON logging,
  `docs/ops/runbook.md`.
- **v0 import** — `malus import <dir>` loads a legacy review directory into the DB;
  `rtd.yaml` survives as an import/export interchange format.
- Multi-user end-to-end tests (human + AI reviewer, GUI + API + MCP, finalized).

### Changed
- `malus` CLI is now `serve` / `mcp` / `import` (the v0 file pipeline is retired).
- Documentation rewritten for the web app (`README.md`, `docs/usage.md`).

### Removed
- **git** as store/transport (no git call anywhere in `src/`).
- The v0 file/CLI pipeline and the v0 `--engine anthropic` reviewer path.

### Legacy
- `gui/rtd.html` (v0 single-file GUI) retained, clearly marked legacy.

## v0.1.0

Initial local, git-based, text-first CLI: freeze → per-reviewer copies → harvest
`rtd.yaml` → triage → disposition (single-file `gui/rtd.html`) → verify →
finalize. See `docs/plan/00-general-plan.md`.
