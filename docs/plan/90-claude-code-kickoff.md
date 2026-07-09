# Claude Code — Kickoff Prompt

Paste the block below as the first message in a Claude Code session started
in the repo root.

---

Read `CLAUDE.md`, `docs/plan/00-general-plan.md` and
`docs/plan/01-foundations.md` in full before writing any code. Also read the
notes under `memory/decisions/` and `memory/specs/` — they are the
authoritative design record.

Your task: implement **Step 1 — Foundations** exactly as specified in
`docs/plan/01-foundations.md`, nothing more.

Constraints:
- Python 3.12; runtime dependencies limited to `typer` and `pyyaml`.
  Full type hints.
- The comment syntax, RID schema and status lifecycle in
  `01-foundations.md` are frozen contracts — implement them verbatim.
  Two open questions are flagged in `memory/specs/comment-syntax.md`
  (fourth COMM type: `process` vs `question`; optional SUGG rationale):
  settle them with me before coding parser-facing constants. If anything
  else looks wrong or ambiguous, STOP and ask before deviating; record
  agreed deviations under `## Deviations` in `01-foundations.md`.
- Closure authority (only a RID's reviewer may set `verified`, never the
  owner) must be enforced in the transition logic — write the test that
  proves the owner cannot bypass it BEFORE writing the feature.
- Every checkbox in the Definition of Done must pass. Conventional
  Commits, small and scoped (scaffold / specs / models / lifecycle / cli),
  each leaving `python -m pytest -q` green.

Workflow:
1. Restate your implementation plan for Step 1 in 10 lines max and wait
   for my OK.
2. Implement test-driven where practical, running pytest as you go.
3. Finish by: running the full DoD checklist and reporting each item
   pass/fail, ticking the checkboxes in `01-foundations.md`, and listing
   any spec ambiguities you found as candidate notes for
   `memory/decisions/`.

Do not start Step 2.

---
