# v2.1 Step 4 — Release v2.1.0

## Deliverables

- [ ] CHANGELOG v2.1.0 (the five requests, migration note for colors).
- [ ] Version bump `pyproject.toml` + `src/malus/__init__.py` → 2.1.0
      (asset URLs re-bust automatically via `?v=`).
- [ ] Full suite green; commit `chore(release): v2.1.0`; tag `v2.1.0`;
      push main + tag.

## Definition of Done

Tagged v2.1.0 pushed; Alberto redeploys (`alembic upgrade head` runs the
color migration — the docker entrypoint already migrates on start).
