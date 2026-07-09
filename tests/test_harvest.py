"""Tests for freeze validation, anchoring, and rtd.yaml assembly."""

import datetime as dt

import pytest

from malus.constants import CommentType, Disposition, Kind, Severity, Status
from malus.harvest import FreezeViolation, build_rtd, validate_insertion_only
from malus.models import RTD, Meta

BASELINE = (
    "# Spec\n"
    "\n"
    "## 3.2.1 Timeouts\n"
    "\n"
    "The timeout shall be configurable.\n"
    "\n"
    "## 3.3 Logging\n"
    "\n"
    "Logs are written to disk.\n"
)

COMM_A = "{COMM|type=technical|sev=major: the timeout must be bounded}"
SUGG_SHARED = '{SUGG: "disk" -> "the log store"}'
COMM_B = "{COMM|type=editorial: tighten this wording}"


def _insert_after(text: str, marker: str, snippet: str) -> str:
    idx = text.index(marker) + len(marker)
    return text[:idx] + snippet + text[idx:]


def _meta() -> Meta:
    return Meta(
        review_id="SIN-SRS-R1",
        document="baseline.md",
        baseline_sha="abc1234",
        created=dt.date(2026, 7, 3),
        owner="A. Boffi",
        reviewers=["F. Miccoli", "R. Bianchi"],
    )


def _copy_a() -> str:
    t = _insert_after(BASELINE, "configurable.", " " + COMM_A)
    return _insert_after(t, "disk", " " + SUGG_SHARED)


def _copy_b() -> str:
    t = _insert_after(BASELINE, "disk", " " + SUGG_SHARED)  # identical SUGG
    return _insert_after(t, "Logs are written", " " + COMM_B)


# --- freeze validation ---


def test_validate_accepts_insertion_only() -> None:
    blocks = validate_insertion_only(BASELINE, _copy_a())
    assert len(blocks) == 2


def test_validate_rejects_text_edit() -> None:
    with pytest.raises(FreezeViolation):
        validate_insertion_only(BASELINE, BASELINE.replace("disk", "tape"))


# --- id assignment, fields, anchoring ---


def test_ids_assigned_in_document_order_with_derived_prefix() -> None:
    res = build_rtd(BASELINE, _meta(), {"F. Miccoli": _copy_a()})
    assert [r.rid for r in res.rtd.rids] == ["SIN-SRS-0001", "SIN-SRS-0002"]
    assert res.rtd.rids[0].kind is Kind.COMM  # timeouts precede logging
    assert res.rtd.rids[1].kind is Kind.SUGG


def test_comm_fields_and_anchor() -> None:
    res = build_rtd(BASELINE, _meta(), {"F. Miccoli": _copy_a()})
    comm = res.rtd.rids[0]
    assert comm.reviewer == "F. Miccoli"
    assert comm.type is CommentType.TECHNICAL
    assert comm.severity is Severity.MAJOR
    assert comm.comment == "the timeout must be bounded"
    assert comm.anchor.section == "3.2.1 Timeouts"
    assert comm.anchor.line_hint == 5


def test_prefix_override() -> None:
    meta = _meta()
    meta.rid_prefix = "XYZ-DOC"
    res = build_rtd(BASELINE, meta, {"F. Miccoli": _copy_a()})
    assert res.rtd.rids[0].rid == "XYZ-DOC-0001"


# --- dedup, violations ---


def test_identical_suggs_dedup_across_reviewers() -> None:
    res = build_rtd(
        BASELINE, _meta(), {"F. Miccoli": _copy_a(), "R. Bianchi": _copy_b()}
    )
    suggs = [r for r in res.rtd.rids if r.kind is Kind.SUGG]
    assert len(suggs) == 1


def test_violating_copy_reported_others_processed() -> None:
    res = build_rtd(
        BASELINE,
        _meta(),
        {"F. Miccoli": _copy_a(), "R. Bianchi": BASELINE.replace("disk", "tape")},
    )
    assert any(v.reviewer == "R. Bianchi" for v in res.violations)
    assert len(res.rtd.rids) == 2  # F's findings still harvested


def test_malformed_block_is_a_violation() -> None:
    bad = _insert_after(BASELINE, "configurable.", " {COMM|type=bogus: x}")
    res = build_rtd(BASELINE, _meta(), {"F. Miccoli": bad})
    assert res.violations
    assert res.rtd.rids == []


# --- re-harvest stability ---


def test_reharvest_preserves_ids_and_owner_fields() -> None:
    meta = _meta()
    first = build_rtd(BASELINE, meta, {"F. Miccoli": _copy_a()}).rtd
    first.rids[0].status = Status.ANSWERED
    first.rids[0].reply = "agreed"
    first.rids[0].disposition = Disposition.ACCEPTED
    second = build_rtd(BASELINE, meta, {"F. Miccoli": _copy_a()}, existing=first).rtd
    assert [r.rid for r in second.rids] == [r.rid for r in first.rids]
    assert second.rids[0].status is Status.ANSWERED
    assert second.rids[0].reply == "agreed"
    assert second.rids[0].disposition is Disposition.ACCEPTED


def test_vanished_comment_becomes_withdrawn_not_deleted() -> None:
    meta = _meta()
    first = build_rtd(BASELINE, meta, {"F. Miccoli": _copy_a()}).rtd
    second = build_rtd(BASELINE, meta, {"F. Miccoli": BASELINE}, existing=first).rtd
    assert len(second.rids) == len(first.rids)
    assert all(r.status is Status.WITHDRAWN for r in second.rids)


def test_new_comment_on_reharvest_gets_next_number() -> None:
    meta = _meta()
    first = build_rtd(BASELINE, meta, {"F. Miccoli": _copy_a()}).rtd
    copy2 = _insert_after(_copy_a(), "Logs are written", " " + COMM_B)
    second = build_rtd(BASELINE, meta, {"F. Miccoli": copy2}, existing=first).rtd
    assert len(second.rids) == 3
    assert any(r.rid == "SIN-SRS-0003" for r in second.rids)


def test_harvest_is_idempotent() -> None:
    meta = _meta()
    copies = {"F. Miccoli": _copy_a(), "R. Bianchi": _copy_b()}
    y1 = build_rtd(BASELINE, meta, copies).rtd.to_yaml()
    y2 = build_rtd(BASELINE, meta, copies, existing=RTD.from_yaml(y1)).rtd.to_yaml()
    assert y1 == y2
