# maluS — User Guide

maluS runs a formal review of a Markdown document. The document is frozen, each
reviewer annotates a personal copy with inline comment blocks, the comments are
harvested into one tracking file (`rtd.yaml`), the owner decides on each finding,
the accepted changes are implemented, and the reviewers — never the owner — close
their findings. It works the same whether the owner or a reviewer is a person or
an AI.

Everything is plain text plus one self-contained HTML page. There is no server and
nothing to pay for. Git provides the history.

## Install

Requires Python 3.12+ and git.

```sh
pipx install .        # or: pip install .
malus --help
```

The optional live-AI engine (Step "AI roles" below) needs one extra package:

```sh
pipx install '.[ai]'  # adds the 'anthropic' package; set ANTHROPIC_API_KEY to use it
```

## Key words

- **DUR** — the Document Under Review (a Markdown file).
- **baseline** — the frozen copy of the DUR the review is run against.
- **RID** — one tracked finding (id like `SIN-SRS-0001`).
- **rtd.yaml** — the one file that holds the review: a `meta` header + the findings.
- **disposition** — the owner's decision on a finding: accepted / rejected / deferred.
- Three **roles** — owner, reviewer, moderator — each a person or an AI.
- **The rule that never bends:** only a reviewer (or a moderator on their behalf)
  may mark a finding *verified*. The owner never can, and an AI never can.

## Comment syntax

Reviewers add only these blocks to their copy — never edit the document's text:

- `{COMM|type=<t>|sev=<s>: free text}` — a discussion comment. `type` is one of
  typo, editorial, technical, process (default editorial); `sev` is one of minor,
  major, critical (default minor). Both are optional and order-free.
- `{SUGG: "exact old text" -> "new text"}` — a mechanical replacement.

Write a literal `}` as `\}`; inside a `{SUGG}` write a literal `"` as `\"`.

## Quickstart — run the demo review

A ready-made synthetic review lives in `examples/srs-demo/`. Run it inside a git
repository (freeze and traceability need commits).

```sh
MALUS=$(pwd)                       # run this from the maluS repository root
mkdir /tmp/malus-demo && cd /tmp/malus-demo
git init -q && git commit --allow-empty -m start

# 1. create the review from the source document
malus init SIN-SRS-R1 --document "$MALUS/examples/srs-demo/srs.md" \
    --owner "A. Boffi" --reviewers "A. Rossi,B. Bianchi,C. Verdi"
git add -A && git commit -q -m "chore: init review"

REV=reviews/SIN-SRS-R1

# 2. freeze the baseline (records the commit id)
malus freeze --review $REV

# 3. make one copy per reviewer, then let each reviewer annotate their copy
malus copies --review $REV
cp "$MALUS/examples/srs-demo/reviewers/"*.md "$REV/reviewers/"   # demo shortcut

# 4. harvest the comments into rtd.yaml (a tampered copy is rejected, others proceed)
malus harvest --review $REV

# 5. group duplicate findings (one reviewer's is linked under another's)
malus triage --review $REV --auto

# 6. apply the mechanical suggestions to a working copy (preview first)
malus apply-suggs --review $REV --dry-run
malus apply-suggs --review $REV        # writes reviews/SIN-SRS-R1/working.md
```

### 7. Owner decides — in the GUI

Double-click `gui/rtd.html` in any browser (or serve the folder to use the
in-place file save). Open `$REV/rtd.yaml`, and for each finding write a reply,
choose accepted / rejected / deferred, and move it to *answered* / *implemented*.
Save — only the fields you changed are written, so the git diff stays small. The
GUI will not let you mark a finding *verified*: that button is disabled for the
owner.

### 8. Implement, then check the link

Edit the document for the accepted findings and commit, naming the RIDs in the
message:

```sh
git commit -am "fix(srs): bound the timeout — SIN-SRS-0001"
malus verify --review $REV --check      # lists accepted findings with no commit yet
```

### 9. Reviewers close their findings

```sh
malus verify --review $REV --reviewer "A. Rossi"                 # list their pending findings
malus verify --review $REV --rid SIN-SRS-0001 --reviewer "A. Rossi"
# not satisfied? send it back with a reason:
malus verify --review $REV --rid SIN-SRS-0001 --reviewer "A. Rossi" --reopen "still unclear"
```

### 10. Report and finalize

```sh
malus report --review $REV      # validates rtd.yaml and writes report.md (minutes)
malus finalize --review $REV    # requires every finding verified/withdrawn; writes
                                # final.md, report.md, carryover.yaml, and a FINALIZED marker
```

## The two modes

**Mode 1 — AI owner, human reviewers.** The AI drafts the owner's replies and
decisions; humans still verify. The AI's drafts are marked `ai_drafted: true` and
its findings never advance on their own:

```sh
malus ai disposition --review $REV        # drafts reply + decision for each open finding
# a human reviews the drafts in the GUI, confirms, and only a reviewer verifies
```

**Mode 2 — human owner, AI reviewer.** The AI writes its own reviewer copy; the
parser rejects anything that isn't valid comment blocks:

```sh
malus ai review --review $REV --reviewer claude   # writes reviewers/claude.md
malus harvest --review $REV                        # its comments join the review
```

`malus ai triage` proposes duplicate groups the same way `triage` does. All `ai`
commands use an offline mock engine by default; add `--engine anthropic` (and
install the `[ai]` extra + set `ANTHROPIC_API_KEY`) to use a live model. **No AI
command can verify or close a finding — there is none.**

## Command summary

| Command | What it does |
|---|---|
| `malus init <id> --document <f>` | create a review from a source document |
| `malus freeze --review <dir>` | freeze the baseline (record the commit id) |
| `malus copies --review <dir>` | make one blank copy per reviewer |
| `malus harvest --review <dir>` | parse the copies into rtd.yaml |
| `malus triage --review <dir> [--auto]` | group duplicate findings |
| `malus apply-suggs --review <dir> [--dry-run]` | apply mechanical suggestions |
| `malus verify --review <dir> [--check\|--reviewer\|--rid …]` | traceability + reviewer closure |
| `malus report --review <dir>` | validate + write the minutes |
| `malus finalize --review <dir>` | new baseline + minutes + carry-over |
| `malus ai review\|disposition\|triage` | drive an AI in a seat (mock by default) |

The disposition step itself is done in `gui/rtd.html` (or drafted by `malus ai
disposition`), not by a dedicated CLI command.
