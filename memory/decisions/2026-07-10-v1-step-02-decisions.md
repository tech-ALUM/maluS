---
title: v1 Step 2 — Persistence Layer (core off files + git) Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-02-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- persistence
- repository
---

# v1 Step 2 — Persistence Layer Decisions

Decisions implementing v1 Step 2 (docs/plan/v1/02-persistence-off-git.md): the
reused core runs on the database; freeze and traceability are reimplemented
without git. Domain invariants D1–D5 unchanged.

## Observations

- [decision] Transport retired to legacy (Alberto's choice via AskUserQuestion): removed the v0 file/git `*_review` wrappers, git helpers (`_baseline_sha`, `commits_since`, git `check_traceability`), and `finalize_review`. The `malus` CLI is now `--version` + `import` (v0 dir → DB); `ai.py`/AI CLI deleted, rebuilt over MCP in Step 7. File reading survives only in `malus/legacy/import_review_dir` #transport
- [decision] The pure domain core (`harvest.build_rtd`, `triage`, `report.validate/render_report`, `lifecycle.verify_rid/reopen_rid/pending_for_reviewer`, `models.transition`) is reused unchanged; only persistence/transport moved #reuse
- [decision] DB↔RTD bridge: every mutating service exports the review to an RTD (Step-1 `rtd_io.export_rtd`), runs the pure core, then persists with `sync_rtd_to_review` (upsert RID rows by rid_str; duplicates derived from master_id) #bridge
- [decision] Repository layer `src/malus/repo/`: UserRepo, ReviewRepo, VersionRepo, ReviewerCopyRepo, RidRepo, AuditRepo (+ content_hash). Repos flush but never commit; the caller owns the transaction #repo
- [decision] Freeze = an immutable, hash-pinned baseline `DocumentVersion`; edits create new versions, the baseline is never mutated #freeze
- [decision] Traceability off git = `RidChange` rows (+ `AuditLog`); `services.check_traceability` flags accepted-unreferenced and referenced-not-accepted. The `implement` service is gated: an accepted RID needs ≥1 RidChange to a post-baseline version before answered→implemented — enforced in the service, not the pure transition #traceability
- [decision] Added services beyond the deliverable list to reproduce the full pipeline (owner disposition was GUI-only in v0): `answer`, `implement`, `save_version`, `link_change` #services
- [context] content_hash is sha256(content); a v0 import gets a sha256 baseline hash, not the old git SHA (the intended v1 identity) #hash
- [context] Suite 163 → 129: pure-core tests kept/trimmed; git/file/AI pipeline tests replaced by DB service tests + a legacy-import pipeline test over the sample fixture (incl. G. Verdi's freeze violation). No git call anywhere in src/ #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 1 — Architecture & Data Model Decisions]]
- realises [[ADR 0001 — v1 web pivot]] (git removal)

## Sources
- docs/plan/v1/02-persistence-off-git.md
- Implementation: src/malus/repo/, src/malus/services/, src/malus/legacy/; trimmed src/malus/{harvest,triage,report,lifecycle,cli}.py
- Claude Code session with Alberto Boffi, 2026-07-10
