# Roadmap

This roadmap reflects the current public direction of Valor as a local-first,
developer-focused project.

## Guiding Constraints

- local-first by default
- inspectable behavior
- privacy-first trust model
- stdlib-only runtime where practical
- optional, explicit integrations instead of mandatory cloud services

## Phase 1: Local Core

**Status:** Complete

What shipped:

- local evidence store and CLI
- configurable career framework template
- six assistant workflows (expanded over later phases to the current eight)
- ambient coaching rules
- install flow for Claude Code, with Cursor kept as a legacy target

## Phase 2: Open-Source Hardening

**Status:** Complete

What shipped:

- integration portability model (state.json flags, auto-detection, graceful skip)
- contributor workflow (PR/issue templates, Ruff linter in CI)
- getting-started guide and integrations documentation
- expanded test coverage

## Phase 3: Better Local Packaging

**Status:** Complete

What shipped:

- VERSION file and `--version` flag for traceability
- `--upgrade` flag (git pull + re-install) and version tracking in state.json
- Claude Code plugin packaging (plugin.json, marketplace.json, bin/, setup skill)
- command files named for plugin namespace (`/valor-briefing` etc.)
- evidence CLI enhancements: `search`, `export`, `status` subcommands
- improved `list` filtering: `--from`, `--to`, `--activity` date/type filters
- state_schema_version for forward-only state.json migrations
- architecture documentation (docs/architecture.md)
- `--clone` flag and curl one-liner for quick install

## Phase 4: Agent-Native Extensions

**Status:** Complete

What shipped:

- Codex CLI support (`--target codex`) with AGENTS.md rule and skills adapter
- `.codex-plugin/plugin.json` for Codex plugin system
- three install targets: Claude Code, Codex CLI, Cursor
- docs updated across README, architecture, and getting-started

## Phase 5: Evidence Outputs + Agent Quality

**Status:** Complete

What shipped:

- `export` subcommand filtering: `--days`, `--from/--to`, `--competency`
- weekly-summary CLI: `weekly-summary-save`, `weekly-summary-list`, `weekly-summary-get`
- feedback CLI: `feedback-add`, `feedback-stats`
- weekly reflection now persists structured output to weekly_summary table
- new `/valor-prep` command for 1:1 manager prep (7th agent command)
- standardized integration preamble across all commands
- wrap-up now records evidence (wrapup_completed entry)
- version bump to 0.3.0

## Phase 6: Trust, Planning, and Hygiene

**Status:** Complete

What shipped:

- **Verification gate** (`verify.py`): artifacts are verified before any agent
  re-asserts a carried-forward claim; per-type TTL cache (`claim_verifications`
  table); unverifiable claims are demoted ("confirm or drop?") with a frozen
  day-counter — stops phantom propagation across wrap-up → briefing → prep.
- **Day-planning pass** (`plan.py`): fits priorities to the day's calendar gaps
  (deep vs fragmented, focus-time treated as deep-work, OOO blocks), with
  optional **private** calendar write (idempotent; removed when verified done).
- **Chronic escalation**: items stuck past a threshold surface in `/valor-prep`.
- **Format-aware 1:1 prep**: `/valor-prep` reads the user's running 1:1 doc and
  drafts this week's entry in that doc's own format.
- **Working-hours-driven routines**: briefing/wrap-up/weekly times derive from
  the configured working hours.
- **Company-info hygiene guard**: a scanner (`scripts/check_hygiene.py`) wired
  into local git hooks and CI (`hygiene`, `hygiene-pr`) plus branch protection,
  keeping employer/colleague/ticket-key terms out of the public repo.
- state schema v4 → v7 (`verification`, `planning`, `one_on_one`,
  `escalate_in_one_on_one`); evidence DB schema v2 → v3.
- version bump to 0.5.0

## Phase 7: Focus, Estimation, and Proactive Detection

**Status:** Complete

What shipped:

- **Opt-in project focus** (`focus.py`): for users who rotate projects, the
  briefing derives the current project from a recurring per-project sync meeting
  (or a manual setting), plans around it, and hides off-focus work. Off by
  default; ticket→project classification is by reading the ticket, not a prefix.
- **Proactive drift detection**: a throttled baseline-diff of recurring meetings,
  enriched by reading a new meeting's attached docs, flags a likely new/dropped
  project as a top-of-briefing alert — no routine prompt.
- **Per-task duration estimates + post-meeting breaks** in the day plan: tasks
  are sized by an agent estimate (not a flat default), with a configurable
  breather reserved after real meetings.
- **Calendar-first task surface**: day-plan blocks carry the task's description
  (next action + clickable link) and snap to clean clock boundaries
  (`block_granularity_minutes`) like meetings, readable at do-time.
- **Anti-phantom hardening**: no "publish/document X" task before its upstream
  work exists; claims recorded by stable id to stop counter fragmentation.
- state schema v7 → v12 (`planning.post_meeting_break_minutes` +
  `block_granularity_minutes`, `project_focus` + `meeting_baseline`).
- version bump to 0.6.1

## Phase 8: Calendar Intelligence & Grounded Coaching

**Status:** Complete

What shipped:

- **Day-plan that fits how you work**: a morning-ritual buffer
  (`morning_buffer_minutes` — no tasks before workday_start + buffer), deep work
  prefers focus-time blocks, and tentative / optional-attendee events are
  schedulable-over (not treated as busy).
- **Grounded coaching**: a low competency count is a signal to look, not a to-do;
  a publish/write-up nudge must cite precedent (Confluence) or a framework reason,
  else it isn't surfaced.
- **Meeting intelligence**: a categorized `meeting_catalog` (project_sync / 1:1 /
  standup / social / …) replaces the flat baseline; new meetings are
  deep-researched (attached docs → Confluence → Slack), and an unmapped
  project-sync is surfaced as a "new project?" prompt instead of ignored.
- **Version-sync guard** (`scripts/check_version_sync.py`): CI asserts every
  version string (manifests, website, OG) and the architecture schema number
  match the source of truth.
- state schema v12 → v14 (`planning.morning_buffer_minutes`;
  `project_focus.meeting_catalog`).
- version bump to 0.7.0

## Phase 9: Meeting Prep Blocks

**Status:** Complete

What shipped:

- **Pre-meeting prep blocks** (`plan.py`): for meetings the briefing categorizes
  `project_sync` or `external` (the ones you present/decide at), the day plan
  auto-reserves a prep block (default 30 min, `pre_meeting_prep_minutes`)
  immediately before the meeting to gather docs and frame talking points — falling
  back to the nearest earlier gap that day, or flagging `prep_unassigned` when
  there's no room. Meetings you only attend (standups, demos, planning) get none.
  It's the mirror of the post-meeting break.
- state schema v14 → v15 (`planning.pre_meeting_prep_minutes`).
- version bump to 0.8.0

## Phase 10: Project Sync Prep

**Status:** Complete

What shipped:

- **`/valor-sync-prep` command**: generates team-facing talk points for an
  upcoming `project_sync` — progress since the last sync, decisions to land, open
  questions — scoped to the current project (distinct from the portfolio-wide,
  manager-facing `/valor-prep`). Generate-only: the user reviews and pastes into
  the project's shared notes. Pairs with the Phase 9 prep block — the block
  reserves the 30 min, this fills it.
- version bump to 0.9.0

## Phase 11: Daily Meeting Intelligence + Auto Sync-Prep

**Status:** Complete

What shipped:

- **Daily drift-check**: the 14-day catalog re-scan throttle is gone — the
  briefing now reconciles recurring meetings against the categorized catalog
  **every day**. A known meeting stays silent; an unknown recurring meeting is
  categorized and added (asked about once); an unmapped `project_sync` whose
  project is new surfaces a "new project?" alert the day it appears.
- **Parked-project memory** (`project_focus.parked_projects`): a new project the
  user declines to add is remembered, so daily detection never re-prompts it.
- **Auto sync-prep** (`project_focus.auto_sync_prep`, default true): each briefing
  auto-schedules a one-off `/valor-sync-prep` run before each same-day
  `project_sync`, at `pre_meeting_prep_minutes` before it (idempotent; the command
  keeps a no-op safeguard).
- state schema v15 → v16 (drop `sync_scan_interval_days` + `last_sync_scan`; add
  `auto_sync_prep` + `parked_projects`).
- version bump to 0.10.0

## Phase 12: Goal-Driven Prioritization & Meeting Capture

**Status:** Complete

What shipped:

- **Goal-driven briefing prioritization**: the briefing now ranks the day's
  todos against this week's goals — silently extracted from the 1:1 doc into a
  new `prioritization.week_goals` block (refreshed weekly) — plus durable
  dependency `standing_rules`, applying both *before* planning the day, showing
  the "why" on each priority, and surfacing spare-capacity backlog pickups when
  the day is light. Backlog discovery (the former standalone `/valor-tasks`
  workflow) is now a briefing capability rather than a separate command.
- **Wrap-up meeting-notes capture**: the evening wrap-up reads a notes
  attachment on the day's calendar events (e.g. a Gemini "Notes by Gemini" Doc,
  not the event agenda) and records it as a `meeting_notes` evidence entry, so
  `/valor-prep` and `/valor-weekly` can draw on what happened in meetings. Short
  recurring standups are skipped.
- **Plain-text paste-ready prep output**: `/valor-prep` and `/valor-sync-prep`
  emit plain text with no markdown asterisks, so the output pastes cleanly into
  docs that render markdown literally.
- **`/valor-tasks` retired**: the standalone task-finding command was removed and
  its backlog discovery folded into the briefing's spare-capacity pickups; the
  installer prunes the orphaned command/skill artifacts on upgrade.
- state schema v16 → v17 (`prioritization`, `standing_rules`).
- version bump to 0.11.0

## Future Considerations

These are not committed but worth exploring:

- **Slack as a primary project-detection signal** (today it enriches a
  calendar-detected meeting; spotting a new project from Slack activity alone is future)
- local model support for privacy-sensitive environments
- self-hosted or encrypted sync across machines
- cross-agent evidence federation (e.g., Cursor + Claude Code on same machine)
- **Day-plan overlap verification** — the planner avoids the busy events it is
  *given*, and a stderr tripwire flags the empty-calendar case (a caller passing
  no events). A fuller, deliberately-deferred check would re-fetch the calendar
  after writing blocks and verify none overlaps a real event — catching mis-plans
  the current narrow guard can't (e.g. some events passed but an accepted one
  dropped). The empty-calendar tripwire was chosen as the high-precision 80%;
  this is the rest.
- ~~**Verification-gate completeness**~~ — **shipped** (claims lifecycle): the
  deferred mechanical backstop became `verify.py register / reconcile /
  carry-write` plus the session-start `context.claims` worklist, after a real
  incident proved the gap (a "not sent" Slack claim carried 6 days after the
  message was sent — the gate never saw a slack-type claim because nothing
  forced submission). What remains genuinely future: verifying a claim the
  agent never *notices* as a claim (the carry-write suspect regex and the
  context tripwire net the claim-shaped ones).
