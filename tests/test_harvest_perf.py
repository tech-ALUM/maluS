"""Equivalence + performance tests for the linear freeze matcher (v2 step 1).

The old implementation ran character-level ``difflib.SequenceMatcher`` twice
per copy; v2 replaces it with a single linear two-pointer alignment
(``_align_ws``). Freeze semantics (normative, plan 01): the residue is valid
iff it equals the baseline after removing every whitespace character. The
difflib oracle is reproduced locally here to prove behavioral equivalence on
realistic corpora.
"""

import difflib
import random
import time

import pytest

from malus.harvest import (
    FreezeViolation,
    _align_ws,
    _build_r2b,
    _remove_spans,
    validate_insertion_only,
)
from malus.parser import scan

# --------------------------------------------------------------------------- #
# corpus
# --------------------------------------------------------------------------- #

DOC = (
    "# Sinapsi SRS — Résumé\n"
    "\n"
    "## 1 Introduction\n"
    "\n"
    "The system shall operate 24/7 with a mean latency ≤ 20 ms.\n"
    "\n"
    "| Param | Min | Max | Unit |\n"
    "|-------|-----|-----|------|\n"
    "| t_out | 1   | 300 | s    |\n"
    "| n_ch  | 1   | 64  | —    |\n"
    "\n"
    "## 2 Behaviour\n"
    "\n"
    "```python\n"
    "def timeout(cfg):\n"
    "    return cfg.get(\"t_out\", 30)\n"
    "```\n"
    "\n"
    "- The timeout shall be configurable.\n"
    "- Logs are written to disk.\n"
    "- Übermäßige Größen sind zu vermeiden.\n"
)

COMM = "{COMM|type=technical|sev=major: bound the timeout}"
SUGG = '{SUGG: "disk" -> "the log store"}'


def _oracle_violation_line(baseline: str, residue: str):
    """The pre-v2 difflib check: None if accepted, else the reported line."""
    matcher = difflib.SequenceMatcher(a=baseline, b=residue, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if baseline[i1:i2].strip() or residue[j1:j2].strip():
            return baseline[:i1].count("\n") + 1
    return None


def _new_violation_line(baseline: str, residue: str):
    try:
        _align_ws(baseline, residue)
    except FreezeViolation as exc:
        return exc.line
    return None


def _ws_perturbations(text: str) -> list[str]:
    rng = random.Random(42)
    out = [
        text,
        text.replace(" ", "  ", 3),
        text.replace("\n\n", "\n\n\n", 2),
        text.replace(" shall ", " \t shall "),
        text + "\n\n",
        "\n" + text,
    ]
    # random single-space insertions at stable pseudo-random points
    for _ in range(4):
        pos = rng.randrange(len(text))
        out.append(text[:pos] + " " + text[pos:])
    return out


def _real_edits(text: str) -> list[str]:
    return [
        text.replace("disk", "tape"),
        text.replace("The system shall operate 24/7 with a mean latency ≤ 20 ms.\n", ""),
        text.replace("configurable", "con figurable x"),
        text.replace("| t_out | 1   | 300 | s    |", "| t_out | 1   | 999 | s    |"),
        text + "\nextra trailing clause",
        "PREFIX " + text,
    ]


# --------------------------------------------------------------------------- #
# equivalence with the difflib oracle
# --------------------------------------------------------------------------- #


def test_ws_only_variants_accepted_by_both() -> None:
    for variant in _ws_perturbations(DOC):
        assert _oracle_violation_line(DOC, variant) is None
        assert _new_violation_line(DOC, variant) is None


def test_real_edits_rejected_by_both() -> None:
    for variant in _real_edits(DOC):
        assert _oracle_violation_line(DOC, variant) is not None
        assert _new_violation_line(DOC, variant) is not None


def test_violation_line_exact_on_handcrafted_edit() -> None:
    # "disk" lives on the "- Logs are written to disk." line
    bad = DOC.replace("disk", "tape")
    expected_line = DOC[: DOC.index("disk")].count("\n") + 1
    with pytest.raises(FreezeViolation) as exc:
        _align_ws(DOC, bad)
    assert exc.value.line == expected_line


def test_validate_insertion_only_contract_unchanged() -> None:
    copy = DOC.replace("configurable.", "configurable. " + COMM).replace(
        "disk.", "disk. " + SUGG
    )
    blocks = validate_insertion_only(DOC, copy)
    assert len(blocks) == 2
    with pytest.raises(FreezeViolation):
        validate_insertion_only(DOC, copy.replace("24/7", "12/5"))


# --------------------------------------------------------------------------- #
# r2b mapping invariants
# --------------------------------------------------------------------------- #


def test_r2b_identity_on_equal_strings() -> None:
    r2b = _align_ws(DOC, DOC)
    assert r2b == list(range(len(DOC) + 1))


def test_r2b_monotone_and_char_exact_on_real_copy() -> None:
    copy = DOC.replace("configurable.", "configurable. " + COMM).replace(
        "disk.", "disk. " + SUGG
    )
    blocks = scan(copy)
    residue = _remove_spans(copy, [(b.start, b.end) for b in blocks])
    r2b = _build_r2b(DOC, residue)
    assert len(r2b) == len(residue) + 1
    assert r2b[len(residue)] == len(DOC)
    assert all(r2b[k] <= r2b[k + 1] for k in range(len(residue)))
    for j, ch in enumerate(residue):
        if not ch.isspace():
            assert DOC[r2b[j]] == ch  # non-ws chars align exactly


# --------------------------------------------------------------------------- #
# performance guard
# --------------------------------------------------------------------------- #


def test_large_document_validates_fast() -> None:
    big = DOC * 400  # ~300 KB
    copy = big
    step = len(copy) // 21
    # insert 20 blocks at paragraph boundaries (after a newline)
    for k in range(20, 0, -1):
        pos = copy.index("\n", k * step) + 1
        copy = copy[:pos] + COMM + "\n" + copy[pos:]
    t0 = time.perf_counter()
    blocks = validate_insertion_only(big, copy)
    residue = _remove_spans(copy, [(b.start, b.end) for b in blocks])
    _build_r2b(big, residue)
    elapsed = time.perf_counter() - t0
    assert len(blocks) == 20
    assert elapsed < 1.0, f"freeze validation took {elapsed:.2f}s on ~300KB"
