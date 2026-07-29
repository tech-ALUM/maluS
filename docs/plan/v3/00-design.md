# maluS v3 — Design (validated)

**Status:** approved by Alberto Boffi, 2026-07-29 (this session), section by
section (§1 phases/lifecycle, §2 closeout workspace, §3 verification/export,
§4 signing/migration/tests). Breaking workflow change → version **3.0.0**.

## Problem

In v2.x a reviewer "verifies" a finding right after the owner's disposition,
even though the document has not been touched yet: verification and review
closure are conflated. v3 separates them: the review phase ends when every
comment's disposition is *agreed*; implementation and verification of the
actual document edits happen in a distinct **closeout** phase, with full
per-comment traceability of the Markdown changes, and the finished review
yields a downloadable final MD + archived PDF (optionally signed).

## Decisions

| Topic | Decision |
|---|---|
| Review phases | `ReviewStatus` becomes a real state machine: `draft → in_review → closeout → finalized`. The dead `active` value is removed. The web GUI (create + freeze in one step) takes a review straight to `in_review`; `draft` remains for API-created reviews without a baseline. Phase enforcement lives in the service layer; the pure `transition()` in `src/malus/models.py` stays phase-agnostic. |
| Closeout entry | Owner action **Start closeout**, allowed iff ≥1 non-withdrawn RID exists **and** every RID is in `closed \| withdrawn` (legacy `implemented`/`verified` rows also pass). New comments are blocked in closeout. Safety valve: a human admin can revert `closeout → in_review` (audited). |
| RID lifecycle | New status **`closed`** = "the reviewer accepted the owner's disposition". Transitions: `open→answered` (Dispose, unchanged); `answered→closed` (**Accept disposition** — the former Verify button, renamed); `answered\|closed→open` (Reopen with reason, `in_review` only); `closed→implemented` (owner, closeout only, disposition=accepted only, requires ≥1 linked `RidChange`); `implemented→verified` (**Verify**, closeout); `implemented→closed` (**Request changes** with reason → rework; the reason is appended to the RID's reply/timeline like reopen and surfaced in the owner's work queue); `verified→closed` (reviewer reopen with reason until finalized); `open→withdrawn` (unchanged). The direct v2 path `answered→verified` is removed. |
| Rejected/deferred | Excluded from closeout verification: their story ends at `closed` (accept disposition). The review completes when every **accepted** RID is `verified`. |
| Closure authority | Invariant untouched and extended: `accept disposition`, `verify` and `request changes` belong to the RID's reviewer — or moderator / human global admin on their behalf — **never the owner, never an AI** (`is_ai` guard absolute, as `src/malus/models.py:299-315`). Dispose stays owner/admin. |
| Closeout workspace | New page `/ui/reviews/{id}/closeout` (owner/admin): work queue of accepted RIDs grouped by state (to implement / awaiting verification / verified / rework requested with the reviewer's reason) + MD editor evolved from the existing textarea+live-preview (`implement.html` + `editor.js`), loaded with the latest `DocumentVersion`. |
| Edit↔RID linkage | Every save requires selecting **≥1 accepted RID**: it creates one new `DocumentVersion` + one `RidChange` row per selected RID (model already exists, `src/malus/db/models.py:216`) + audit. A save with no text change or no RID selection is rejected — every document edit is comment-traceable by construction. Multi-RID saves allowed (e.g. duplicates); a RID may span several saves. **Mark implemented** stays an explicit per-RID action (reuses `svc.implement`): requires ≥1 linked change, does `closed→implemented`. |
| Per-RID diff | In the unified viewer (closeout+), an accepted RID's card gains a **Changes** section: for each version linked via `RidChange`, a word-level diff vs its parent version, computed **server-side with stdlib `difflib`** (zero new deps), rendered as inline ins/del with ±3 lines of context. A "Full diff" page shows baseline ↔ latest. Verify / Request changes buttons sit under the diff for the RID's reviewer. |
| Finalize | When the gate holds (all accepted `verified`; rejected/deferred `closed` — legacy v2 `verified` rejected/deferred also pass; withdrawn ignored) the owner sees **Finalize review** → `svc.finalize` (gate updated; currently `src/malus/services/core.py:615`) → last version stamped `is_final`, phase `finalized`. |
| Downloads | Finalized reviews expose `final.md` (attachment) and a **PDF generated once at finalize** and archived in a new table **`ReviewArtifact(review_id, kind, content, sha256, created_at)`**. Bonus: RTD report MD download (`svc.report` already exists). |
| PDF pipeline | Markdown→HTML via `markdown-it-py`, HTML→PDF via **WeasyPrint**, both in the optional pip extra **`malus[pdf]`** (requires system Pango) — recorded as **ADR 0004** (first sanctioned optional runtime deps). Layout: cover with review metadata, page/hash footer, and a final **signature page** (SHA-256 of the document + audit trail of who verified what, when) always present. Without the extra: PDF button disabled with explanation + zero-dep browser print-CSS fallback. |
| Digital signature [SHOULD] | Optional extra **`malus[sign]`** (pyHanko, MIT), feature-flagged, off by default. Owner uploads their P12 certificate; at sign time a form asks the passphrase (never persisted, never logged) → visible **PAdES B-B** signature on the signature page, applied to the archived PDF via incremental update → stored as artifact `pdf_signed` + audit. ALUM internal CA documented (openssl procedure in docs), no in-app CA tooling. Certificates: no free Adobe/eIDAS-trusted certs exist; internal-CA signatures validate org-wide once the CA cert is distributed (Adobe otherwise shows "validity unknown"). Full legal weight (QES, e.g. Aruba/Namirial ~25–35 €/3 yr) stays **out-of-band**: download, sign with own kit, re-upload. Signing is the **last** operation on the PDF. |
| Migration | Light, v2-style: `create_all` adds `ReviewArtifact`; one-time backfill `draft → in_review` for reviews with a frozen baseline; existing RIDs keep their status (gates tolerate legacy `implemented`/`verified`). |
| Versioning | Workflow semantics change (Verify button meaning, new mandatory phase) → **v3.0.0**. |

## RID state machine (v3)

```
open ──dispose──▶ answered ──accept disposition──▶ closed ──[accepted, closeout]──▶ implemented ──verify──▶ verified
  │                  │  ▲                            │  ▲                              │                      │
  ▼                  │  └──reopen (reason)───────────┘  └───request changes (reason)───┘                      │
withdrawn            └──reopen (reason)──▶ open         └◀─────────reopen (reason, until finalized)──────────┘
```

Terminal at finalize: `verified` (accepted), `closed` (rejected/deferred), `withdrawn`.

## Testing

Unit: transitions incl. `closed`, phase gates. Service: accept_disposition,
save-with-RIDs, mark-implemented, verify/request-changes, finalize, artifacts.
Web: authz matrix (owner/AI barred from accept+verify, admin on-behalf), diff
renderer, downloads. PDF and signing via `pytest.importorskip`. One E2E:
review → closeout → verify → finalize → download.

## Steps

| # | File | Scope |
|---|---|---|
| 1 | `01-lifecycle.md` | `closed` status + transitions, phase state machine, service gates, accept-disposition / request-changes services, migration backfill |
| 2 | `02-closeout-workspace.md` | owner closeout page: work queue, editor, save+RidChange, mark implemented |
| 3 | `03-verification.md` | difflib diff renderer, viewer Changes section, Verify / Request changes, full-diff page |
| 4 | `04-finalize-export.md` | finalize GUI, `ReviewArtifact`, MD/report download, PDF pipeline + ADR 0004, signature page, print fallback |
| 5 | `05-signing.md` | [SHOULD] `malus[sign]`: pyHanko, P12 upload, sign flow, CA docs |
| 6 | `06-release.md` | CHANGELOG, bump 3.0.0, tag, push, Open Brain |

## Sources

- Alberto's v3 request + 4 clarifying answers + approach/section approvals,
  this session (2026-07-29): accept-disposition closes a comment; rejected /
  deferred excluded from closeout; multi-RID saves; rework inside closeout;
  approach A; signing as final optional step.
- Current code: `src/malus/constants.py:37-79` (statuses/transitions),
  `src/malus/models.py:264-341` (closure authority), `src/malus/db/models.py`
  (RidChange 216, DocumentVersion 110, ReviewStatus 32),
  `src/malus/services/core.py` (implement 495, verify 517, finalize 615),
  `src/malus/web/` (document-viewer.js cardEl, implement.html, editor.js).
- PDF/signature research (web, 2026-07-29): WeasyPrint https://pypi.org/project/weasyprint/
  + https://doc.courtbouillon.org/weasyprint/stable/first_steps.html ;
  pyHanko https://github.com/MatthiasValvekens/pyHanko ;
  Adobe trust/"validity unknown" https://helpx.adobe.com/acrobat/kb/selected-certificate-has-errors-invalid-signature.html ;
  eIDAS/Italy legality https://helpx.adobe.com/legal/esignatures/regulations/italy.html ;
  QES cost 2026 https://chitelodice.it/firma-digitale/firma-digitale-quanto-costa-2026/ ;
  AgID trust providers https://www.agid.gov.it/it/piattaforme/firma-elettronica-qualificata/prestatori-di-servizi-fiduciari-attivi-in-italia ;
  incremental-update pitfalls https://bfo.com/blog/2019/10/03/imperfect_pdf_digital_signatures/ .
