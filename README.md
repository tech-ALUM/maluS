# maluS

Document review management for Markdown documents, modeled on formal
aerospace-style RID (Review Item Discrepancy) review processes.

maluS runs a complete review cycle on a Markdown Document Under Review (DUR):

1. **Freeze** a baseline of the DUR; each reviewer gets a personal copy.
2. Reviewers insert structured inline comment blocks
   (`{COMM|type=...|sev=...: ...}`, `{SUGG: "old" -> "new"}`) — never edit the text itself.
3. **Harvest** extracts all comments into a canonical Revision Tracking
   Document (`rtd.yaml`), one RID per finding.
4. **Triage** clusters duplicate findings and batch-applies mechanical suggestions.
5. The **owner** dispositions each RID (accept / reject / defer) in a
   self-contained single-file GUI (`gui/rtd.html` — any browser, no install, no paid software).
6. Accepted RIDs are implemented with RID-referenced commits;
   **reviewers — not the owner — verify and close** each RID.
7. **Finalize** produces the new document baseline plus review minutes.

The three roles (owner, reviewer, moderator) can each be a human or an AI:
the workflow is identical whether the owner seat is occupied by a person
or by a model. Reviewer-side closure authority is the safety control that
makes the AI-owner mode sound.

## Status

Pre-development. Development plan: `docs/plan/00-general-plan.md`.

## Stack

Python 3.12+ · PyYAML · Typer (CLI) · vanilla HTML/JS single-file GUI · git.

## Repository layout

| Path | Content |
|---|---|
| `docs/plan/` | Development plan — one detailed MD per step |
| `src/malus/` | Python package (CLI + core logic) |
| `gui/rtd.html` | Self-contained RTD GUI |
| `tests/` | pytest suite |
| `memory/` | basic-memory project (design decisions, specs) |
