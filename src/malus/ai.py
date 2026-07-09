"""AI engines and role operations (docs/plan/06-ai-roles.md).

An AI may fill any seat (owner / reviewer / moderator) but never weakens a human
control: it can never set ``verified`` or close a RID, its output enters only
through validated formats (parsed comment blocks, typed rtd.yaml fields), and
every AI artifact is attributed (reviewer name, or ``ai_drafted=true``).

Engines are pluggable. :class:`MockEngine` is deterministic and offline — the
default for tests and dry-runs. :class:`AnthropicEngine` calls the Anthropic API
(model ``claude-opus-4-8``), is opt-in behind ``--engine anthropic``, lazily
imports the optional ``anthropic`` package (``pip install 'malus[ai]'``), and
reads the key from the environment (never stored in the repo).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .constants import Disposition, Kind, Status
from .harvest import FreezeViolation, validate_insertion_only
from .models import RID, RTD
from .parser import ParseError
from .triage import ClusterProposal, DuplicateLink

DEFAULT_MODEL = "claude-opus-4-8"
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(role: str) -> str:
    path = _PROMPTS_DIR / f"{role}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


class Engine(Protocol):
    def complete(self, *, system: str, user: str, task: str) -> str: ...


class MockEngine:
    """Deterministic offline engine for tests and dry-runs (no network, no key)."""

    def __init__(
        self,
        *,
        review: str | None = None,
        disposition: str | None = None,
        triage: str | None = None,
    ) -> None:
        self._review = review
        self._disposition = disposition
        self._triage = triage

    def complete(self, *, system: str, user: str, task: str) -> str:
        if task == "review":
            return self._review if self._review is not None else _mock_review(user)
        if task == "disposition":
            return (
                self._disposition
                if self._disposition is not None
                else '{"disposition": "accepted", "reply": "(ai draft) reasonable finding; accepting."}'
            )
        if task == "triage":
            return self._triage if self._triage is not None else "[]"
        return ""


def _mock_review(baseline: str) -> str:
    block = "{COMM|type=editorial: (ai) consider clarifying this section}"
    sep = "" if baseline.endswith("\n") else "\n"
    return f"{baseline}{sep}{block}\n"


class AnthropicEngine:
    """Live engine calling the Anthropic API. Opt-in; needs the optional ``anthropic`` package."""

    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 4096) -> None:
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, *, system: str, user: str, task: str) -> str:
        try:
            import anthropic
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "the live AI engine needs the optional 'anthropic' package: pip install 'malus[ai]'"
            ) from exc
        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY resolved from the environment
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


def get_engine(name: str) -> Engine:
    if name == "mock":
        return MockEngine()
    if name == "anthropic":
        return AnthropicEngine()
    raise ValueError(f"unknown engine {name!r} (use 'mock' or 'anthropic')")


# --------------------------------------------------------------------------- #
# guardrailed role operations
# --------------------------------------------------------------------------- #


def ai_review(engine: Engine, baseline: str) -> str:
    """Return an AI-authored reviewer copy, validated by the Step-2 parser.

    Raises ``ValueError`` if the output edits baseline text, contains a malformed
    block, or contains no comment blocks — invalid output is never accepted.
    """
    copy = engine.complete(system=load_prompt("reviewer"), user=baseline, task="review")
    try:
        blocks = validate_insertion_only(baseline, copy)
    except (ParseError, FreezeViolation) as exc:
        raise ValueError(f"AI review rejected: {exc}") from exc
    if not blocks:
        raise ValueError("AI review rejected: no comment blocks produced")
    return copy


def _finding_text(rid: RID) -> str:
    parts = [f"RID {rid.rid} (kind {rid.kind.value}"]
    if rid.type:
        parts.append(f", type {rid.type.value}")
    if rid.severity:
        parts.append(f", severity {rid.severity.value}")
    parts.append(")")
    return "".join(parts) + f"\nsection: {rid.anchor.section}\ncomment: {rid.comment or ''}"


def ai_disposition(engine: Engine, rtd: RTD) -> int:
    """Draft a reply + disposition for each OPEN RID and mark ``ai_drafted``.

    Never advances status or verifies — a human confirms. Only the typed
    disposition (validated against the enum) and the reply text are written.
    Returns the number of RIDs drafted.
    """
    valid = {d.value for d in Disposition}
    drafted = 0
    for rid in rtd.rids:
        if rid.status is not Status.OPEN:
            continue
        raw = engine.complete(system=load_prompt("owner"), user=_finding_text(rid), task="disposition")
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or data.get("disposition") not in valid:
            continue
        rid.disposition = Disposition(data["disposition"])
        if data.get("reply"):
            rid.reply = str(data["reply"])
        rid.ai_drafted = True
        drafted += 1
    return drafted


def _findings_summary(rtd: RTD) -> str:
    return "\n".join(
        f"{r.rid} [§{r.anchor.section}] {r.comment or ''}"
        for r in rtd.rids
        if r.kind is Kind.COMM and r.status is not Status.WITHDRAWN
    )


def ai_triage(engine: Engine, rtd: RTD) -> list[ClusterProposal]:
    """Propose semantic duplicate clusters (COMM RIDs) in the Step-3 proposal shape."""
    raw = engine.complete(system=load_prompt("moderator"), user=_findings_summary(rtd), task="triage")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    ids = {r.rid for r in rtd.rids}
    proposals: list[ClusterProposal] = []
    for item in data:
        if not isinstance(item, dict) or item.get("master") not in ids:
            continue
        master = item["master"]
        links = [
            DuplicateLink(d, 1.0)
            for d in item.get("duplicates", [])
            if d in ids and d != master
        ]
        if links:
            proposals.append(ClusterProposal(master, links))
    return proposals
