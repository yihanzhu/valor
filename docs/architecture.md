# Valor Architecture

## Overview

Valor is a local-first ambient career coach for developers. It runs as a set
of prompts and a lightweight Python evidence store inside AI coding assistants
(Claude Code, Cursor). All data stays on the user's machine.

## Distribution Model

```
valor repo (github.com/yihanzhu/valor)
├── .claude-plugin/       Plugin manifest (Claude Code plugin system)
├── commands/             Prompt files (one per Valor agent)
├── src/                  Shared source (evidence CLI, Python library, rule, framework)
├── bin/                  Executable wrappers (valor-evidence)
├── skills/               Plugin skills (setup)
├── install.sh            Standalone installer (Claude Code + Cursor)
├── marketplace.json      Plugin catalog
└── VERSION               Single source of truth for version
```

### Install paths

| Target          | Rule                         | Commands / Skills          | Evidence CLI         |
|-----------------|------------------------------|----------------------------|----------------------|
| Claude Code     | `~/.claude/CLAUDE.md`        | `~/.claude/commands/`      | `~/.valor/`          |
| Cursor          | `~/.cursor/rules/`           | `~/.cursor/skills/`        | `~/.valor/`          |
| Plugin (CC)     | Not supported (ambient only) | Plugin `commands/`         | `~/.valor/`          |

## Local State (`~/.valor/`)

All user data lives under `~/.valor/`. This directory is never checked into
version control and is not overwritten by upgrades (except `evidence_cli.py`
and `utilities.md`).

| File / Dir               | Purpose                                      | Managed by            |
|--------------------------|----------------------------------------------|-----------------------|
| `state.json`             | User config, rolling state, integration flags | `install.sh`, agents  |
| `evidence.sqlite`        | Structured career evidence (SQLite)           | `evidence_cli.py`     |
| `evidence_cli.py`        | CLI for the evidence store                    | `install.sh`          |
| `career_framework.md`    | User's career ladder (not overwritten)        | User                  |
| `utilities.md`           | Tool discovery reference for agents           | `install.sh`          |
| `carry-forward/`         | Wrap-up notes for cross-day continuity        | `wrapup` agent        |
| `backups/`               | Auto-rotated SQLite backups (max 10)          | `evidence_cli.py`     |

### state.json schema

The `installed_version` and `installed_at` fields track when the last install
happened. A future `state_schema_version` field will allow state.json
migrations similar to how `evidence.sqlite` handles schema versions.

Key fields:
- `current_level`, `target_level`, `ceiling_level` -- career level config
- `coaching_mode` -- `"ambient"` (default), `"quiet"`, or `"off"`
- `integrations` -- boolean flags for github, jira, calendar, news
- `installed_version`, `installed_at` -- install tracking

### evidence.sqlite schema

Current schema version: **1**

Tables:
- `evidence` -- career evidence entries (activity, competency, statement)
- `feedback` -- agent feedback tracking
- `weekly_summary` -- weekly reflection summaries
- `schema_version` -- migration tracking

Migrations are applied forward-only in `evidence_cli.py`. The `MIGRATIONS`
dict maps version numbers to SQL statements.

## Agent Architecture

Valor has 6 discrete agents (invoked via slash commands) plus an ambient
coaching layer:

| Agent       | Command (CC)     | Needs External | Core Function                    |
|-------------|------------------|----------------|----------------------------------|
| Briefing    | `/valor-briefing`| GitHub, Jira, Calendar, News | Morning planning       |
| PR Review   | `/valor-pr-review`| GitHub        | Coached code review             |
| Design Doc  | `/valor-design-doc`| None         | Design document coaching        |
| Weekly      | `/valor-weekly`  | GitHub, Jira   | Weekly reflection               |
| Tasks       | `/valor-tasks`   | GitHub, Jira   | Task identification             |
| Wrap-up     | `/valor-wrapup`  | None           | End-of-day summary              |
| *Ambient*   | Always-on rule   | None           | Coaching annotations after tasks|

All agents read `integrations` from `state.json` and silently skip sections
for disabled integrations.

## Evidence Flow

```
User completes a task
  └─> Agent annotates response with coaching
        └─> evidence_cli.py add --activity ... --competency ... --statement ...
              └─> evidence.sqlite (local)
                    └─> evidence_cli.py stats / search / export (introspection)
```

Evidence is append-only. Deduplication prevents duplicate entries (same date +
activity + agent + statement).
