# v3.1 — Kickoff Prompt

Paste the block below as the first message of a fresh Claude Code session
started in the repo root. It is written for **step 01**; to run a later step,
swap the step file named in "Your task" and re-read the ordering rules in
`00-design.md` § Cross-step coordination first.

---

Read `CLAUDE.md` and `docs/plan/v3.1/00-design.md` in full before writing any
code, then `docs/plan/v3.1/01-closeout-in-document.md`, which is the step you
are implementing. `docs/adr/` and `docs/spec/` are the authoritative design
record; the v3 cycle that this one amends is in `docs/plan/v3/`.

Your task: implement **v3.1 Step 1 — Closeout moves into the document viewer**
exactly as specified in `docs/plan/v3.1/01-closeout-in-document.md`, nothing
more. It has seven tasks; do them in order.

Context you will not find by reading the code:

- "v3.1" is a **feedback wave, not a release**. The last tag is `v2.3.0` and
  3.0.0 was never cut, so these steps land before `docs/plan/v3/06-release.md`
  and ship inside the single 3.0.0 bump. Do not bump any version.
- The step exists because of Alberto Boffi's field test of the v3 closeout
  cycle: the owner had to work in two places at once (the `/closeout` page to
  edit, the document viewer to read comments), and the page split the width
  between textarea and preview so neither showed enough document.
- The side panel **stays on the right**. Alberto's feedback said "left"; that
  was considered and rejected, because `.workbench` is shared by every role and
  every phase and flipping it would restyle the review phase for no gain.
- In closeout the sheet shows the **latest version, unmarked**. Comment anchors
  are baseline character offsets and the latest version has moved past them —
  the per-comment `Changes` diff in the card is the anchor from there on. Do
  not try to re-anchor markers onto the edited text.

Constraints:

- Python 3.12+; **no new runtime dependencies** beyond PyYAML + Typer, and **no
  new vendored front-end library** (ADR 0003 — htmx, marked and DOMPurify are
  the only three, already vendored, no CDN at runtime, no build step).
- The closure-authority invariant is frozen: `accept disposition`, `verify` and
  `request changes` belong to the RID's reviewer — or a moderator / human
  global admin on their behalf — **never the owner, never an AI** (the `is_ai`
  guard is absolute). This step must not widen it.
- Traceability by construction is frozen: a closeout save still requires ≥1
  accepted RID and a real text change; `Mark implemented` still requires ≥1
  linked `RidChange`. The JS mirrors these gates for UX only — the server stays
  the authority.
- Conventional Commits, one per task, each leaving `python -m pytest -q` green.
  Use `python -m pytest -q; echo EXIT=$?` — piping pytest masks its exit code.
- The repo has **no JavaScript test harness**. Automated assertions are
  server-side (payload in `#viewer-data`, rendered template, route behaviour);
  the JS-only tasks carry a manual verification block instead. Do not introduce
  a JS test framework to satisfy a task.

Workflow:

1. Restate your implementation plan for the seven tasks in 10 lines max and
   wait for my OK.
2. Implement test-driven, exactly as each task lays out: failing test → watch
   it fail → minimal implementation → watch it pass → commit.
3. If a spec is ambiguous or a task's code does not fit the current source,
   STOP and ask before deviating. Record agreed deviations under a
   `## Deviations` heading in `01-closeout-in-document.md`.
4. Finish by running the Definition of Done checklist, reporting each item
   pass/fail, and ticking the checkboxes in the step file.

Do not start step 02.

---

## Where things stand (2026-07-30)

- `main` = `a5a0125`, pushed. Nothing under `src/` has changed since the v3
  cycle closed at `2df818c`; the only code commit since is the Alembic fix
  below.
- Steps 01–05 of this cycle are **written and unimplemented**.
- A production incident on 2026-07-30 took the server down: `create_all` and
  Alembic each believed they owned the schema, so `alembic upgrade head` died
  on `table review_artifacts already exists` and `set -e` in
  `docker-entrypoint.sh` kept the container from starting. Commit `a5a0125`
  stopped it by making revision `b9e4d5f6a701` skip objects that already exist,
  with a regression test in
  `tests/db/test_db_migration.py::test_upgrade_head_after_create_all_already_ran`.
  **Step 05 removes the double authority that made it possible** — it is the
  reason that step exists, and it is independent of the four UI steps.
- Still open from the v3 cycle, after this one: `docs/plan/v3/05-signing.md`
  [SHOULD] and `docs/plan/v3/06-release.md` (E2E, CHANGELOG, bump to 3.0.0,
  tag).

## Sources

- Alberto Boffi's v3.1 feedback (4 points) and 7 design answers, session of
  2026-07-30; design approved section by section and recorded in
  `docs/plan/v3.1/00-design.md`.
- The incident evidence: `docker compose logs app` from the ALUM server, the
  local reproduction (image built from `Dockerfile`, drifted SQLite volume) and
  the commit timeline `964362f` → `3ea2a56`, all analysed in
  `docs/plan/v3.1/05-one-schema-authority.md` § The incident this step exists
  for.
