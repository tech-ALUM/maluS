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

## Install

Requires Python 3.12+ and git.

```sh
pipx install .          # or: pip install .
malus --help
```

The optional live-AI engine needs one extra package: `pipx install '.[ai]'`
(adds `anthropic`; set `ANTHROPIC_API_KEY` to use it). Everything else — the whole
review workflow, the GUI, and the tests — runs with no extra packages and no network.

## Quickstart

Run the bundled synthetic review end to end (inside a git repository):

```sh
MALUS=$(pwd)                       # from the maluS repository root
mkdir /tmp/malus-demo && cd /tmp/malus-demo && git init -q && git commit --allow-empty -m start
malus init SIN-SRS-R1 --document "$MALUS/examples/srs-demo/srs.md" \
    --owner "A. Boffi" --reviewers "A. Rossi,B. Bianchi,C. Verdi"
git add -A && git commit -q -m "chore: init review"
malus freeze  --review reviews/SIN-SRS-R1
malus copies  --review reviews/SIN-SRS-R1
cp "$MALUS/examples/srs-demo/reviewers/"*.md reviews/SIN-SRS-R1/reviewers/
malus harvest --review reviews/SIN-SRS-R1
malus triage  --review reviews/SIN-SRS-R1 --auto
```

Then open `gui/rtd.html` to disposition the findings, implement the accepted ones
with RID-referenced commits, and finish with `malus verify`, `malus report`, and
`malus finalize`. Full walkthrough (human-owner and AI-owner modes):
**[docs/usage.md](docs/usage.md)**.

## The GUI

`gui/rtd.html` is one self-contained file — open it by double-clicking; no server,
no network. It loads and saves `rtd.yaml`, shows a sortable/filterable table of
findings and a per-finding detail pane, and enforces the closure rule (the owner
can never mark a finding *verified*). Saves touch only the fields you edit, so git
diffs stay small.

## Status

**v0.1.0** — the full pipeline is implemented and covered by tests
(`python -m pytest -q`). Development plan: `docs/plan/00-general-plan.md`.

## Stack

Python 3.12+ · PyYAML · Typer (CLI) · vanilla HTML/JS single-file GUI · git.

## Repository layout

| Path | Content |
|---|---|
| `docs/plan/` | Development plan — one detailed MD per step |
| `docs/spec/` | Normative contracts (comment syntax, RID schema, GUI checklist) |
| `docs/usage.md` | User guide (both modes) |
| `src/malus/` | Python package (CLI + core logic) |
| `gui/rtd.html` | Self-contained RTD GUI |
| `src/malus/prompts/` | Versioned AI prompt templates (reviewer / owner / moderator) |
| `examples/srs-demo/` | Synthetic sample review |
| `tests/` | pytest suite with fixtures |
| `memory/` | basic-memory project (design decisions, specs) |
