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
├── rules/                Ambient agent rule (valor-agent.md)
├── src/                  Shared source (evidence CLI, career framework, coaching ref)
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
version control. Upgrades overwrite the installer-managed runtime files
(`evidence_cli.py`, `verify.py`, `plan.py`, `focus.py`, `collect_transcripts.py`,
`utilities.md`, `coaching-ref.md`) but never touch user content like
`career_framework.md`, `state.json`, or the evidence database.


| File / Dir            | Purpose                                       | Managed by           |
| --------------------- | --------------------------------------------- | -------------------- |
| `state.json`          | User config, rolling state, integration flags | `install.sh`, agents |
| `evidence.sqlite`     | Structured career evidence + verification cache | `evidence_cli.py`  |
| `evidence_cli.py`     | CLI for the evidence store + state             | `install.sh`         |
| `verify.py`           | Artifact-verification gate (anti-phantom)      | `install.sh`         |
| `plan.py`             | Day-planning gap-fit scheduler                 | `install.sh`         |
| `focus.py`            | Project-focus resolver + drift detection       | `install.sh`         |
| `career_framework.md` | User's career ladder (not overwritten)        | User                 |
| `utilities.md`        | Tool discovery reference for agents           | `install.sh`         |
| `coaching-ref.md`     | Coaching specs loaded on-demand (see below)   | `install.sh`         |
| `carry-forward/`      | Wrap-up notes for cross-day continuity        | `wrapup` agent       |
| `backups/`            | Auto-rotated SQLite backups (max 10)          | `evidence_cli.py`    |
| `repo/`               | Git clone of the Valor source repo            | `install.sh --clone` |


### state.json schema

The `installed_version` and `installed_at` fields track when the last install
happened. The `state_schema_version` field enables forward-only migrations
when the installer adds new fields (currently at version 17). Migrations
add missing keys with safe defaults and prune keys removed in later schema
versions (e.g. the v16 sync-rescan throttle), never overwriting existing user
values; they run in `_migrate_state_in_memory` (src/evidence_cli.py). The
installer delegates to this same migrator via `evidence_cli.py state-migrate`.

Key fields:

- `current_level`, `target_level`, `ceiling_level` -- career level config
- `coaching_mode` -- `"ambient"` (default), `"quiet"`, or `"off"`
- `integrations` -- boolean flags for github, jira, calendar, news
- `verification` -- gate config: `enabled`, `escalation_threshold`, `ttl_overrides` (v5)
- `planning` -- day-plan config: `calendar_auto_write`, `workday_start`/`workday_end`, `deep_min_hours`, `post_meeting_break_minutes`, `block_granularity_minutes`, `morning_buffer_minutes`, `pre_meeting_prep_minutes` (v6, v9, v12, v13, v15)
- `one_on_one` -- 1:1 doc reference + `format_notes` for `/valor-prep` (v7; local only)
- `project_focus` -- opt-in project rotation: `enabled`, `mode`, `syncs`, `meeting_catalog` (categorized recurring meetings), `auto_sync_prep`, `parked_projects` (v8–v16; local only). Catalog drift-checked daily — no throttle.
- `prioritization` -- weekly goal ranking: `week_goals` (this week's ordered goals, extracted silently from the 1:1 doc), `week_start`, `goals_source`; used by the briefing to rank todos before the day plan (v17; local only)
- `standing_rules` -- durable sequencing/priority corrections, kept separate from `prioritization` so the weekly goal-refresh never drops them (v17; local only)
- `escalate_in_one_on_one` -- chronic items flagged for the next 1:1 (v5)
- `state_schema_version` -- integer for installer migrations
- `installed_version`, `installed_at` -- install tracking
- `last_update_check`, `update_check_interval_hours` -- remote version checks

### evidence.sqlite schema

Current schema version: **3**

Tables:

- `evidence` -- career evidence entries (activity, competency, statement)
- `feedback` -- agent feedback tracking
- `weekly_summary` -- weekly reflection summaries
- `claim_verifications` -- artifact-verification cache backing `verify.py`
  (claim_hash, verdict, day_count, miss_count, frozen, TTL) (v3)
- `schema_version` -- migration tracking

Migrations are applied forward-only in `evidence_cli.py`. The `MIGRATIONS`
dict maps version numbers to SQL statements.

## Agent Architecture

Valor has 8 discrete agents (invoked via slash commands) plus an ambient
coaching layer:


| Agent      | Command (CC)        | Needs External               | Core Function                    |
| ---------- | ------------------- | ---------------------------- | -------------------------------- |
| Briefing   | `/valor-briefing`   | GitHub, Jira, Calendar, News | Morning planning                 |
| PR Review  | `/valor-pr-review`  | GitHub                       | Coached code review              |
| Design Doc | `/valor-design-doc` | None                         | Design document coaching         |
| Weekly     | `/valor-weekly`     | GitHub, Jira                 | Weekly reflection                |
| Wrap-up    | `/valor-wrapup`     | Calendar (optional)          | End-of-day summary               |
| 1:1 Prep   | `/valor-prep`       | GitHub, Jira (optional)      | Manager 1:1 preparation          |
| Sync Prep  | `/valor-sync-prep`  | GitHub, Jira (optional)      | Project sync talk points         |
| Setup      | `/valor-setup`      | None                         | First-run framework + integration config |
| *Ambient*  | Always-on rule      | None                         | Coaching annotations after tasks |


All agents read `integrations` from `state.json` and silently skip sections
for disabled integrations.

### Verification, planning, focus, and escalation (behaviors, not new agents)

Cross-cutting behaviors run inside the existing agents — no new commands:

- **Verification gate** (`verify.py`): before wrap-up writes a carry-forward
  claim or the briefing re-asserts one, the claim is verified against its source
  (GitHub PRs via `gh`; Confluence/Slack/Drive/Jira via the agent's MCP tools).
  Unverifiable claims are demoted to "confirm or drop?" with their day-counter
  frozen, so a guess never propagates as fact. Verdicts cache in
  `claim_verifications` with per-type TTLs.
- **Goal-driven prioritization** (briefing): before the day plan, the briefing
  ranks the day's todos against this week's goals — extracted silently from the
  1:1 doc into `prioritization.week_goals` (refreshed weekly) — and durable
  dependency `standing_rules`, ordering dependencies-first then goal-fit then
  closeness/staleness and showing the "why" per priority. When the day is light
  it surfaces spare-capacity backlog pickups — the former standalone
  task-finding capability, now folded in: unassigned/stale/High-priority Jira
  work and open PRs in your domain, skipping anything already in the PR section.
- **Day-planning pass** (`plan.py`): after the briefing's Suggested Priorities,
  it fits them to the day's real calendar gaps (deep vs fragmented; focus-time is
  deep-work, out-of-office blocks), sizing each task by an agent-provided
  `est_minutes` and reserving a `post_meeting_break_minutes` breather after real
  meetings. If `planning.calendar_auto_write`, it writes the blocks back as
  **private** calendar items — each snapped to clean clock boundaries and
  carrying the task's description (with a clickable link) so it's readable at
  do-time — idempotent and removed when the task verifies done.
- **Project focus** (`focus.py`, opt-in): when the user rotates projects, the
  briefing derives the current project from a recurring per-project sync meeting
  (or a manual setting) and plans around it, hiding off-focus work. Every briefing
  drift-checks the recurring meetings (over a ~3–4 week window) against the
  categorized catalog: known meetings stay silent, an unknown one is categorized
  and added (asked about once), and an unmapped, non-parked project_sync surfaces
  a "new project?" alert. When `auto_sync_prep` is on, it also schedules a
  `/valor-sync-prep` run before each project_sync.
- **Chronic escalation**: items verified-unresolved past
  `verification.escalation_threshold` surface in `/valor-prep`, which also drafts
  the entry in the user's own 1:1-doc format when `one_on_one.doc` is set.
- **Meeting-notes capture** (wrap-up): the evening wrap-up detects a notes
  attachment on the day's calendar events (e.g. a Gemini "Notes by Gemini" Doc —
  not the event agenda/description), summarizes its decisions/outcomes/action
  items, and records a `meeting_notes` evidence entry with a link, so
  `/valor-prep` and `/valor-weekly` can reuse what happened in meetings. Short
  recurring standups are skipped; gated on `integrations.calendar`.

## Context Loading Strategy

The agent rule (`valor-agent.md`) is injected into **every conversation** as
part of the system prompt. Every token in this file is consumed whether or not
Valor coaching is relevant to the conversation. This makes the rule's size a
direct cost on all interactions.

To minimize this cost, Valor splits its instructions into two tiers:

**Always-loaded (the rule, ~105 lines):**
- Session start protocol (context command, auto-triggers)
- Agent routing table (trigger keywords → commands)
- Coaching trigger condition ("after meaningful tasks, add coaching")
- Footer template (the visual format)
- Evidence recording command (the CLI invocation)
- Quiet mode, behavior rules

**On-demand (`~/.valor/coaching-ref.md`, ~75 lines):**
- Activity classification table (which activity maps to which competency)
- Coaching format detailed instructions and examples
- Evidence statement quality rules with good/bad examples
- Ceiling level rule

The rule tells the agent: "for detailed coaching specs, read
`~/.valor/coaching-ref.md`." The agent reads this file only when it's about to
produce a coaching annotation, which happens 1-3 times per conversation at most.

```
Every conversation:          [rule: ~105 lines always loaded]
                                      │
Coaching triggered? ─── no ───> done (saved ~75 lines)
         │
        yes
         │
         ▼
Read coaching-ref.md ──> [+75 lines loaded once]
         │
         ▼
Produce footer + record evidence
```

**Why this matters:** In the common case (exploration, Q&A, debugging with no
coaching), the on-demand file is never loaded. Even when coaching IS triggered,
total context (105 + 75 = 180 lines) is less than the previous monolithic rule
(335 lines) because the on-demand file loads once per conversation, not per
message.

**Do not merge these files back together.** The split is intentional. If you
need to add coaching instructions, add them to `src/coaching-ref.md` (on-demand)
unless they affect when or whether coaching fires (put those in the rule).

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