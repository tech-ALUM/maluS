---
title: Tech Stack
type: note
permalink: malus/knowledge/tech-stack
world: ALUM
source: chat
status: active
tags:
- malus
- stack
---

# Tech Stack

## Observations
- [stack] Python 3.12+, PyYAML, Typer CLI (entry point malus), pytest; git via subprocess; packaging pipx-installable, version 0.1.0 at step 7 #python
- [stack] GUI: gui/rtd.html single file, vanilla HTML/CSS/JS, YAML library vendored inline, File System Access API with download fallback, works from file:// with zero network #gui
- [constraint] No third-party runtime dependencies beyond PyYAML and Typer without a recorded decision; no build step for the GUI; no CDN at runtime #dependencies
- [constraint] GUI saves must produce minimal git diffs (no reordering/rewriting of untouched YAML) #git-friendliness
- [tooling] Repo public on tech-ALUM GitHub, SSH alias github.com-alum; local path ~/Documents/ALUM/maluS; git identity albertoboffi-ALUM <alberto.boffi@alum-lab.com> already configured locally #repo
- [tooling] Development executed by Claude Code, plan-driven (docs/plan), one step at a time; kickoff prompt in docs/plan/90-claude-code-kickoff.md #claude-code

## Relations
- part_of [[maluS — Index]]

## Sources
- Claude chat design session, 2026-07-03; local environment inspection 2026-07-03 (git config, SSH auth test)
