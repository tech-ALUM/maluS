"""Tests for triage: duplicate clustering and mechanical suggestion apply."""

import datetime as dt

from malus.constants import CommentType, Disposition, Kind, Severity, Status
from malus.models import RID, RTD, Anchor, Meta
from malus.triage import apply_clusters, apply_suggs, parse_sugg_comment, propose_clusters


def _rtd(rids: list[RID]) -> RTD:
    return RTD(
        meta=Meta(
            review_id="DLG-SPEC-R1",
            document="baseline.md",
            baseline_sha="s",
            created=dt.date(2026, 7, 3),
            owner="o",
            reviewers=[],
        ),
        rids=rids,
    )


def _comm(rid: str, reviewer: str, text: str, section: str = "2.1", status: Status = Status.OPEN) -> RID:
    return RID(
        rid=rid,
        reviewer=reviewer,
        created=dt.date(2026, 7, 3),
        kind=Kind.COMM,
        anchor=Anchor(section=section, line_hint=5),
        type=CommentType.TECHNICAL,
        severity=Severity.MAJOR,
        status=status,
        comment=text,
    )


def _sugg(rid: str, old: str, new: str, disposition=None, status: Status = Status.OPEN) -> RID:
    return RID(
        rid=rid,
        reviewer="A. Uno",
        created=dt.date(2026, 7, 3),
        kind=Kind.SUGG,
        status=status,
        comment=f'"{old}" -> "{new}"',
        disposition=disposition,
    )


# --- clustering ---


def test_propose_groups_similar_comments_in_same_section() -> None:
    rtd = _rtd(
        [
            _comm("DLG-SPEC-0001", "A. Uno", "the sampling rate is not specified"),
            _comm("DLG-SPEC-0002", "B. Due", "the sampling rate is not specified anywhere"),
            _comm("DLG-SPEC-0003", "C. Tre", "the sampling rate is not specified"),
        ]
    )
    proposals = propose_clusters(rtd, threshold=0.6)
    assert len(proposals) == 1
    assert proposals[0].master == "DLG-SPEC-0001"
    assert {link.duplicate for link in proposals[0].links} == {"DLG-SPEC-0002", "DLG-SPEC-0003"}


def test_no_group_across_sections_or_dissimilar_text() -> None:
    rtd = _rtd(
        [
            _comm("DLG-SPEC-0001", "A. Uno", "the sampling rate is not specified"),
            _comm("DLG-SPEC-0002", "B. Due", "the enclosure must be waterproof", section="3.0"),
        ]
    )
    assert propose_clusters(rtd, threshold=0.6) == []


def test_apply_clusters_links_master_duplicates_and_status() -> None:
    master = _comm("DLG-SPEC-0001", "A. Uno", "the sampling rate is not specified", status=Status.ANSWERED)
    dup1 = _comm("DLG-SPEC-0002", "B. Due", "the sampling rate is not specified anywhere")
    dup2 = _comm("DLG-SPEC-0003", "C. Tre", "the sampling rate is not specified")
    rtd = _rtd([master, dup1, dup2])
    applied = apply_clusters(rtd, propose_clusters(rtd, threshold=0.6))
    assert applied == 2
    assert dup1.master == "DLG-SPEC-0001" and dup2.master == "DLG-SPEC-0001"
    assert master.duplicates == ["DLG-SPEC-0002", "DLG-SPEC-0003"]
    assert dup1.status is Status.ANSWERED and dup2.status is Status.ANSWERED  # follows master


def test_confidence_is_reported_for_each_link() -> None:
    rtd = _rtd(
        [
            _comm("DLG-SPEC-0001", "A. Uno", "the sampling rate is not specified"),
            _comm("DLG-SPEC-0002", "B. Due", "the sampling rate is not specified anywhere"),
        ]
    )
    link = propose_clusters(rtd, threshold=0.6)[0].links[0]
    assert 0.6 <= link.confidence <= 1.0


# --- suggestion apply ---


def test_apply_suggs_applies_match_and_flags_stale() -> None:
    text = "Data is stored locally.\n"
    rtd = _rtd(
        [
            _sugg("DLG-SPEC-0004", "stored locally", "stored on the device"),
            _sugg("DLG-SPEC-0005", "nonexistent phrase", "x"),
        ]
    )
    out, results = apply_suggs(text, rtd)
    assert out == "Data is stored on the device.\n"
    by_rid = {r.rid: r for r in results}
    assert by_rid["DLG-SPEC-0004"].applied is True
    assert by_rid["DLG-SPEC-0005"].applied is False
    assert "not found" in by_rid["DLG-SPEC-0005"].reason


def test_apply_suggs_skips_rejected() -> None:
    text = "Data is stored locally.\n"
    rtd = _rtd([_sugg("DLG-SPEC-0004", "stored locally", "x", disposition=Disposition.REJECTED)])
    out, results = apply_suggs(text, rtd)
    assert out == text
    assert results[0].applied is False


def test_parse_sugg_comment_roundtrips_escapes() -> None:
    old, new = parse_sugg_comment('"a \\"b\\"" -> "c \\} d"')
    assert old == 'a "b"'
    assert new == "c } d"
