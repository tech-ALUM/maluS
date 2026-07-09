# Comment Syntax — Normative Specification

**Status:** Normative. Frozen at Step 1 (Foundations). Later steps build on
this grammar; changes require a recorded decision in `memory/decisions/`.

Inline comment blocks are the **only** modification a reviewer may make to
their frozen copy of the Document Under Review (DUR). This is the *freeze
rule* (decision D1): reviewer copies never receive text edits, only inserted
blocks, so consolidation is a diff-extraction rather than an N-way merge.

Two block types exist:

- `{COMM …}` — a discussion comment; each one becomes a discussion-grade RID.
- `{SUGG …}` — a mechanical text-replacement suggestion; batch-appliable
  without discussion (decision D4).

## 1. Block recognition

A block begins with `{` immediately followed by a tag (`COMM` or `SUGG`) and
ends at the **first unescaped `}`** (see [§4 Escaping](#4-escaping)). Blocks
do **not** nest. A `{` that is not the start of a `{COMM`/`{SUGG` opener is
ordinary text and needs no escaping; only `}` is significant inside a block.

Block content may span multiple lines; the block extends across newlines
until its closing `}`.

## 2. `{COMM}` — discussion comment

```
{COMM|type=<t>|sev=<s>: free text}
```

Grammar (EBNF; `SP` = optional inline whitespace):

```ebnf
comm-block = "{COMM" , { "|" , param } , ":" , SP , text , "}" ;
param      = "type=" , type-value | "sev=" , sev-value ;
type-value = "typo" | "editorial" | "technical" | "process" ;
sev-value  = "minor" | "major" | "critical" ;
text       = ? one or more characters; first unescaped "}" closes the block ? ;
```

- **Parameters are optional and order-free.** `{COMM|sev=major|type=technical: …}`
  and `{COMM|type=technical|sev=major: …}` are equivalent.
- Each parameter may appear **at most once**. A duplicated or unknown
  parameter, or a value outside the enumerations above, is a **parse error**
  (rejected at harvest, Step 2).
- No whitespace is permitted inside the parameter section (between `{COMM`
  and the `:`). Leading/trailing whitespace of the free `text` is trimmed.

### Defaults

| Parameter | Values | Default when omitted |
|-----------|--------|----------------------|
| `type`    | `typo`, `editorial`, `technical`, `process` | `editorial` |
| `sev`     | `minor`, `major`, `critical` | `minor` |

The fourth `type` value is **`process`** (a comment about compliance with a
standard, structure, or the review process itself). Settled with Alberto
Boffi on 2026-07-09, resolving the `process`-vs-`question` open question from
`memory/specs/comment-syntax.md`.

### Examples

```markdown
{COMM: this sentence reads awkwardly}
{COMM|type=typo: "recieve" → "receive"}
{COMM|type=technical|sev=critical: the timeout must be bounded; an
unbounded wait deadlocks the harvester}
{COMM|sev=major|type=process: section 4 lacks the mandatory traceability
matrix required by the review checklist}
```

The first example uses both defaults (`editorial`, `minor`).

## 3. `{SUGG}` — mechanical suggestion

```
{SUGG: "exact old text" -> "new text"}
```

Grammar:

```ebnf
sugg-block = "{SUGG:" , SP , qstring , SP , "->" , SP , qstring , SP , "}" ;
qstring    = '"' , { char | '\"' | '\}' } , '"' ;
```

- `old` is the **first** quoted string, `new` is the **second**; `->` (a
  literal two-character arrow) separates them. Whitespace around the `:`,
  the arrow, and before the closing `}` is ignored.
- `old` must be **non-empty** and is expected to match the baseline text
  verbatim; a SUGG whose `old` string is not found is flagged at apply time
  (Step 3). `new` **may be empty** (`""`) to express a deletion.
- **A `{SUGG}` carries no discussion, rationale, or parameters.** Settled
  with Alberto Boffi on 2026-07-09: SUGG stays purely mechanical so it
  remains batch-appliable and safely de-duplicable. A reviewer who needs to
  justify a change attaches a separate `{COMM}` next to the `{SUGG}`.

### Deduplication and default disposition

- Two `{SUGG}` blocks are **identical** when their `(old, new)` pairs are
  byte-identical after unescaping. Identical suggestions from any number of
  reviewers collapse to a single RID (all contributing reviewers credited).
- A `{SUGG}` carries a default **disposition proposal of `accepted`**
  (batch-apply). The owner may still reject it during disposition.

### Examples

```markdown
{SUGG: "the the" -> "the"}
{SUGG: "colour" -> "color"}
{SUGG: "  redundant clause, removed" -> ""}
{SUGG: "a \"quoted\" word" -> "a 'quoted' word"}
```

## 4. Escaping

The only characters that need escaping inside a block are the block
terminator and (inside `{SUGG}` operands) the string delimiter:

| Sequence | Meaning |
|----------|---------|
| `\}`     | a literal `}` (does **not** terminate the block) |
| `\"`     | a literal `"` — **only inside `{SUGG}` quoted operands** |

Any backslash not part of `\}` or `\"` is an ordinary literal backslash.
There is no escape for `{`.

> Escaping details beyond the `\}` rule recorded in
> `memory/specs/comment-syntax.md` (the `\"` operand escape, "otherwise
> literal backslash") are completions made while writing this normative
> contract; they are flagged as candidate notes for `memory/decisions/`.

## 5. Placement and anchoring

Blocks may appear anywhere between words or lines of the reviewer copy. They
are the only permitted change to that copy (freeze rule, §0).

At harvest (Step 2) each block is anchored to:

1. **section** — the nearest preceding Markdown heading,
2. **quote** — a preceding text fragment (~120 characters) for human context,
3. **line_hint** — the block's line number in the baseline.

These populate the RID `anchor` field (see
[`rid-schema.md`](rid-schema.md)). The anchoring mechanics are implemented in
Step 2; only the block grammar above is frozen at Step 1.

## 6. Relationship to RIDs

- Each `{COMM}` block yields exactly one discussion-grade RID (`kind: COMM`).
- Each distinct `{SUGG}` yields one mechanical RID (`kind: SUGG`); identical
  SUGGs are de-duplicated as described in §3.
- RID identity, fields, and the status lifecycle are specified in
  [`rid-schema.md`](rid-schema.md).

## Sources

- Design session with Alberto Boffi, 2026-07-03 (Claude chat): comment
  syntax, freeze rule (D1), differentiated comments (D4).
- `memory/decisions/2026-07-03-architecture-decisions.md` — D1, D4.
- `memory/specs/comment-syntax.md` — draft observations this document makes
  normative.
- Step 1 decisions settled with Alberto Boffi, 2026-07-09: fourth `{COMM}`
  `type` = `process`; `{SUGG}` remains mechanical-only (no rationale
  parameter).
