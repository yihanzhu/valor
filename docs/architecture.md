# Valor Architecture

## Overview

Valor is a local-first ambient career coach for developers. It runs entirely
inside AI coding assistants (Claude Code, Codex CLI, Cursor) as a set of prompts and a
lightweight Python evidence store. Valor is not standalone software -- it has
no daemon, no background process, and no runtime outside of agent sessions.
All data stays on the user's machine.

## Distribution Model

```
valor repo (github.com/yihanzhu/valor)
├── .claude-plugin/       Plugin manifest (Claude Code plugin system)
├── commands/             Prompt files (one per Valor agent)
├── src/                  Shared source (evidence CLI, career framework, utilities)
├── bin/                  Executable wrappers (valor-evidence)
├── skills/               Plugin skills (setup)
├── .codex-plugin/        Plugin manifest (Codex CLI plugin system)
├── install.sh            Standalone installer (Claude Code + Codex + Cursor)
├── marketplace.json      Plugin catalog
└── VERSION               Single source of truth for version
```

### Install paths


| Target         | Rule                         | Commands / Skills     | Evidence CLI |
| -------------- | ---------------------------- | --------------------- | ------------ |
| Claude Code    | `~/.claude/CLAUDE.md`        | `~/.claude/commands/` | `~/.valor/`  |
| Codex CLI      | `~/.codex/AGENTS.md`         | `~/.codex/skills/`    | `~/.valor/`  |
| Cursor         | `~/.cursor/rules/`           | `~/.cursor/skills/`   | `~/.valor/`  |

Plugin manifests (`.claude-plugin/`, `.codex-plugin/`) exist for marketplace
discovery but provide commands only -- no ambient rule or hooks. Use
`install.sh` for the full experience.


## Local State (`~/.valor/`)

All user data lives under `~/.valor/`. This directory is never checked into
version control and is not overwritten by upgrades (except `evidence_cli.py`
and `utilities.md`).


| File / Dir            | Purpose                                       | Managed by           |
| --------------------- | --------------------------------------------- | -------------------- |
| `state.json`          | User config, rolling state, integration flags | `install.sh`, agents |
| `evidence.sqlite`     | Structured career evidence (SQLite)           | `evidence_cli.py`    |
| `evidence_cli.py`     | CLI for the evidence store                    | `install.sh`         |
| `career_framework.md` | User's career ladder (not overwritten)        | User                 |
| `utilities.md`        | Tool discovery reference for agents           | `install.sh`         |
| `carry-forward/`      | Wrap-up notes for cross-day continuity        | `wrapup` agent       |
| `backups/`            | Auto-rotated SQLite backups (max 10)          | `evidence_cli.py`    |
| `repo/`               | Git clone of the Valor source repo            | `install.sh --clone` |


### state.json schema

The `installed_version` and `installed_at` fields track when the last install
happened. The `state_schema_version` field enables forward-only migrations
when the installer adds new fields (currently at version 3).

Key fields:

- `current_level`, `target_level`, `ceiling_level` -- career level config
- `coaching_mode` -- `"ambient"` (default), `"quiet"`, or `"off"`
- `integrations` -- boolean flags for github, jira, calendar, news
- `state_schema_version` -- integer for installer migrations
- `installed_version`, `installed_at` -- install tracking
- `last_update_check` -- ISO timestamp of last remote version check
- `update_check_interval_hours` -- how often to check (default 24)

### evidence.sqlite schema

Current schema version: **2**

Tables:

- `evidence` -- career evidence entries (activity, competency, statement)
- `feedback` -- agent feedback tracking
- `weekly_summary` -- weekly reflection summaries
- `schema_version` -- migration tracking

Migrations are applied forward-only in `evidence_cli.py`. The `MIGRATIONS`
dict maps version numbers to SQL statements.

## Agent Architecture

Valor has 7 discrete agents (invoked via slash commands) plus an ambient
coaching layer:


| Agent      | Command (CC)        | Needs External               | Core Function                    |
| ---------- | ------------------- | ---------------------------- | -------------------------------- |
| Briefing   | `/valor-briefing`   | GitHub, Jira, Calendar, News | Morning planning                 |
| PR Review  | `/valor-pr-review`  | GitHub                       | Coached code review              |
| Design Doc | `/valor-design-doc` | None                         | Design document coaching         |
| Weekly     | `/valor-weekly`     | GitHub, Jira                 | Weekly reflection                |
| Tasks      | `/valor-tasks`      | GitHub, Jira                 | Task identification              |
| Wrap-up    | `/valor-wrapup`     | None                         | End-of-day summary               |
| 1:1 Prep   | `/valor-prep`       | GitHub, Jira (optional)      | Manager 1:1 preparation          |
| *Ambient*  | Always-on rule      | None                         | Coaching annotations after tasks |


All agents read `integrations` from `state.json` and silently skip sections
for disabled integrations.

## Evidence Flow

```
User completes a task
  └─> Agent annotates response with coaching
        └─> evidence_cli.py add --activity ... --competency ... --statement ...
              └─> evidence.sqlite (local)
                    ├─> evidence_cli.py stats / search / export (introspection)
                    ├─> evidence_cli.py weekly-summary-save (weekly reflection persistence)
                    ├─> evidence_cli.py feedback-add (feedback tracking)
                    └─> /valor-prep reads evidence + weekly summaries for 1:1 prep
```

Evidence is append-only. Deduplication prevents duplicate entries (same date +
activity + agent + statement).

## Auto-Update

At session start, the ambient rule checks `last_update_check` in state.json.
If more than `update_check_interval_hours` (default 24) have passed, the agent
curls the remote `VERSION` file and compares with `installed_version`:

- **Same version:** updates `last_update_check`, no action
- **Minor/patch bump:** runs `install.sh --auto-update` silently (git pull +
  quiet reinstall in `~/.valor/repo/`)
- **Major bump:** prompts the user before updating
- **Offline/failure:** skips silently

The `--auto-update` flag performs a `git pull --ff-only` in `~/.valor/repo/`,
re-runs `install.sh --target all` with suppressed output, and prints a
one-line summary of the version change.