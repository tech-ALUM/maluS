"""Tests for the AI engine abstraction and guardrailed role operations (mock engine)."""

import datetime as dt

import pytest

from malus.ai import (
    MockEngine,
    ai_disposition,
    ai_review,
    ai_triage,
    get_engine,
    load_prompt,
)
from malus.constants import CommentType, Disposition, Kind, Severity, Status
from malus.models import RID, RTD, Anchor, Meta

BASELINE = "# Doc\n\nThe timeout is fixed.\n"


def _rtd(rids):
    return RTD(
        meta=Meta(
            review_id="SIN-SRS-R1",
            document="baseline.md",
            baseline_sha="s",
            created=dt.date(2026, 7, 3),
            owner="A. Boffi",
            reviewers=["claude"],
        ),
        rids=rids,
    )


def _comm(rid_id, text="unclear", section="1", status=Status.OPEN, reviewer="F. Miccoli"):
    return RID(
        rid=rid_id,
        reviewer=reviewer,
        created=dt.date(2026, 7, 3),
        kind=Kind.COMM,
        anchor=Anchor(section=section),
        type=CommentType.EDITORIAL,
        severity=Severity.MINOR,
        status=status,
        comment=text,
    )


def test_prompts_load() -> None:
    for role in ("reviewer", "owner", "moderator"):
        assert load_prompt(role).strip()


def test_get_engine() -> None:
    assert isinstance(get_engine("mock"), MockEngine)
    with pytest.raises(ValueError):
        get_engine("nope")


# --- ai review (validated by the Step-2 parser) ---


def test_ai_review_produces_valid_copy() -> None:
    copy = ai_review(MockEngine(), BASELINE)
    assert "The timeout is fixed." in copy  # baseline text preserved
    assert "{COMM" in copy


def test_ai_review_rejects_text_edit() -> None:
    bad = MockEngine(review="# Doc\n\nThe timeout is CHANGED.\n{COMM: x}\n")
    with pytest.raises(ValueError):
        ai_review(bad, BASELINE)


def test_ai_review_rejects_when_no_blocks() -> None:
    with pytest.raises(ValueError):
        ai_review(MockEngine(review=BASELINE), BASELINE)  # unchanged, no blocks


# --- ai disposition (drafts only; never closes) ---


def test_ai_disposition_drafts_and_marks() -> None:
    rtd = _rtd([_comm("SIN-SRS-0001")])
    assert ai_disposition(MockEngine(), rtd) == 1
    r = rtd.rids[0]
    assert r.disposition is Disposition.ACCEPTED
    assert r.ai_drafted is True
    assert r.reply
    assert r.status is Status.OPEN  # never advances or verifies


def test_ai_disposition_skips_non_open() -> None:
    rtd = _rtd([_comm("SIN-SRS-0001", status=Status.ANSWERED)])
    assert ai_disposition(MockEngine(), rtd) == 0


def test_ai_disposition_ignores_invalid_disposition() -> None:
    rtd = _rtd([_comm("SIN-SRS-0001")])
    assert ai_disposition(MockEngine(disposition='{"disposition":"bogus","reply":"x"}'), rtd) == 0
    assert rtd.rids[0].disposition is None
    assert rtd.rids[0].ai_drafted is False


# --- ai triage (Step-3 proposal shape) ---


def test_ai_triage_default_is_empty() -> None:
    rtd = _rtd([_comm("SIN-SRS-0001"), _comm("SIN-SRS-0002")])
    assert ai_triage(MockEngine(), rtd) == []


def test_ai_triage_builds_proposals_and_drops_unknown_ids() -> None:
    rtd = _rtd([_comm("SIN-SRS-0001"), _comm("SIN-SRS-0002")])
    engine = MockEngine(
        triage='[{"master":"SIN-SRS-0001","duplicates":["SIN-SRS-0002","SIN-SRS-9999"]}]'
    )
    proposals = ai_triage(engine, rtd)
    assert len(proposals) == 1
    assert proposals[0].master == "SIN-SRS-0001"
    assert [link.duplicate for link in proposals[0].links] == ["SIN-SRS-0002"]
