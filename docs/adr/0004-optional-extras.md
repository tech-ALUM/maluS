# ADR 0004 — Optional runtime extras (`malus[pdf]`, `malus[sign]`)

**Status:** accepted (v3 step 04). **Date:** 2026-07-30.

## Context

v3 finalizes a review into a downloadable final Markdown and an archived PDF
(cover + document + sign-off page), optionally signed (step 05). ADR 0002
keeps the core runtime dependency-clean (PyYAML, Typer, FastAPI/SQLModel
family); Markdown→PDF cannot be done with the stdlib.

## Decision

New capabilities that need third-party code ship as **optional pip extras**,
feature-detected at import and degrading with a visible notice — never a
runtime download, never a hard core dependency:

- `malus[pdf]` — `weasyprint` (HTML→PDF, needs the system Pango libraries)
  + `markdown-it-py` (Markdown→HTML). Without it, finalize still works; the
  PDF download is disabled with an explanation and the zero-dependency
  browser print view remains available.
- `malus[sign]` — `pyhanko` (PAdES signing of the archived PDF, step 05,
  feature-flagged off by default).

`src/malus/pdfgen.py` (and later `signing.py`) is the single module allowed
to import the extra; everything else checks its `PDF_AVAILABLE` flag.

## Consequences

- Deploys wanting PDF must `pip install malus[pdf]` and have Pango installed
  (`libpango-1.0-0`, `libpangoft2-1.0-0` on Debian/Ubuntu) — documented in
  the README.
- Tests for extra-dependent code run under `pytest.importorskip`; the core
  suite stays green without any extra installed.

## Sources

- v3 design `docs/plan/v3/00-design.md` §PDF pipeline, §Digital signature
  (research links in its Sources section).
- ADR 0002 (stack), ADR 0003 (vendored front-end).
