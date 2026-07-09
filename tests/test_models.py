"""Tests for the RTD dataclasses and their YAML round-trip."""

import datetime as dt

from malus.constants import CommentType, Kind, Severity, Status
from malus.models import RID, RTD, Anchor, Meta


def _sample_rtd() -> RTD:
    return RTD(
        meta=Meta(
            review_id="SIN-SRS-R1",
            document="reviews/SIN-SRS-R1/baseline.md",
            baseline_sha="9f1c2ab",
            created=dt.date(2026, 7, 3),
            owner="A. Boffi",
            reviewers=["F. Miccoli", "R. Bianchi"],
        ),
        rids=[
            RID(
                rid="SIN-SRS-0042",
                reviewer="F. Miccoli",
                created=dt.date(2026, 7, 3),
                kind=Kind.COMM,
                type=CommentType.TECHNICAL,
                severity=Severity.MAJOR,
                anchor=Anchor(section="3.2.1", quote="…timeout…", line_hint=142),
                comment="The timeout must be bounded.",
            ),
            RID(
                rid="SIN-SRS-0043",
                reviewer="R. Bianchi",
                created=dt.date(2026, 7, 3),
                kind=Kind.SUGG,
                comment='"colour" -> "color"',
            ),
        ],
    )


def test_rid_construction_defaults() -> None:
    r = RID(rid="X-Y-0001", reviewer="A. One", created=dt.date(2026, 7, 3), kind=Kind.COMM)
    assert r.status is Status.OPEN
    assert r.type is None
    assert r.severity is None
    assert r.disposition is None
    assert r.duplicates == []
    assert isinstance(r.anchor, Anchor)
    assert r.verified_by is None and r.verified_on is None


def test_yaml_round_trip_preserves_everything() -> None:
    rtd = _sample_rtd()
    restored = RTD.from_yaml(rtd.to_yaml())
    assert restored == rtd


def test_yaml_emits_plain_scalars() -> None:
    text = _sample_rtd().to_yaml()
    assert "kind: COMM" in text
    assert "type: technical" in text
    assert "severity: major" in text
    assert "!!python" not in text  # no python object tags
    assert "created: 2026-07-03" in text  # dates unquoted


def test_yaml_preserves_schema_key_order() -> None:
    text = _sample_rtd().to_yaml()
    i_rid = text.index("rid: SIN-SRS-0042")
    i_reviewer = text.index("reviewer: F. Miccoli")
    i_kind = text.index("kind: COMM")
    i_status = text.index("status: open")
    assert i_rid < i_reviewer < i_kind < i_status


def test_sugg_type_and_severity_are_null_in_yaml() -> None:
    text = _sample_rtd().to_yaml()
    assert "type: null" in text
    assert "duplicates: []" in text


def test_meta_rid_prefix_optional_round_trip() -> None:
    m = Meta(
        review_id="SIN-SRS-R1",
        document="baseline.md",
        baseline_sha="abc",
        created=dt.date(2026, 7, 3),
        owner="A. Boffi",
        rid_prefix="SIN-SRS",
    )
    text = RTD(meta=m, rids=[]).to_yaml()
    assert "rid_prefix: SIN-SRS" in text
    assert RTD.from_yaml(text).meta.rid_prefix == "SIN-SRS"


def test_meta_without_rid_prefix_omits_key() -> None:
    assert "rid_prefix" not in _sample_rtd().to_yaml()
