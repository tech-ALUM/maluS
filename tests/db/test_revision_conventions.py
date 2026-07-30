"""Every new Alembic revision must be idempotent (v3.1 step 05).

Databases in the wild were built by two authorities before this step; a
revision that assumes an object is absent takes the container down on the next
deploy, because `set -e` in docker-entrypoint.sh aborts the boot (2026-07-30).
On SQLite, DDL is additionally non-transactional, so a revision that fails
halfway leaves its earlier objects behind — the next attempt hits the same
wall. Inspect before you create.

The four pre-incident revisions are grandfathered by explicit id: they are
applied everywhere and rewriting applied history is a worse risk than the
debt. Every revision written from now on is checked.
"""

from __future__ import annotations

from pathlib import Path

from alembic.script import ScriptDirectory

from malus.db.migrations import alembic_config

GRANDFATHERED = {
    "01135281e9f4",  # initial schema
    "8208e7694462",  # user auth columns
    "f1a2b3c4d5e6",  # reviewer private notes
    "a7c31e90d412",  # member colors
}


def _upgrade_body(path: str) -> str:
    source = Path(path).read_text(encoding="utf-8")
    return source.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]


def test_every_new_revision_guards_its_ddl():
    for script in ScriptDirectory.from_config(alembic_config()).walk_revisions():
        if script.revision in GRANDFATHERED:
            continue
        body = _upgrade_body(script.path)
        if "op.create_table(" in body or "op.add_column(" in body:
            assert "inspect(" in body, (
                f"revision {script.revision} ({Path(script.path).name}) creates a "
                "schema object without an existence guard — see CLAUDE.md "
                "§Conventions and docs/ops/runbook.md §Schema authority"
            )
