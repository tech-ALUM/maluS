#!/usr/bin/env bash
# maluS one-shot repo setup. Run from the repo root after creating the
# empty public repo "maluS" on the albertoboffi-ALUM GitHub account.
set -euo pipefail
git add -A
git diff --cached --quiet || git commit -m "chore: bootstrap maluS — development plan, project memory, repo skeleton"
git remote get-url origin >/dev/null 2>&1 || git remote add origin git@github.com-alum:albertoboffi-ALUM/maluS.git
git push -u origin main
echo "maluS pushed to https://github.com/albertoboffi-ALUM/maluS"
