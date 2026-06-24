# Valor Utilities Reference

Reference file for Valor agents. Read on demand when running agent skills --
do NOT load into every conversation.

## Integrations

Integration availability is included in the session-start context
(`context.integrations`). If an integration is `false`, skip that section
entirely -- do not probe for the tool and do not print a "not available"
message.

If an integration is `true`, attempt to use it with the discovery steps
below. If it fails at runtime (e.g. `gh` not authenticated), note it once
and suggest the user set it to `false` via:

```
python3 ~/.valor/evidence_cli.py state-set integrations '{"github":false,"jira":true,"calendar":true,"news":true}'
```

The installer auto-detects `gh` CLI availability. Other integrations
(Jira, Calendar, News) default to `true` and should be set to `false`
by the user if unavailable.

## Tool Discovery

When an integration is enabled (`true`), discover the specific tool to use:

**GitHub** (`integrations.github`):
1. Use `gh` CLI (most common)
2. Check MCP tools for GitHub integration

**Jira** (`integrations.jira`):
1. Check for Atlassian/Jira MCP tools (e.g. `jira_search_issues`)
2. Check available slash commands for any Jira-related command
3. Fall back to asking the user to provide ticket details

**Calendar** (`integrations.calendar`):
1. Check MCP tools for Google Calendar integration
2. Check available slash commands for calendar-related commands

**News** (`integrations.news`):
1. Use WebSearch tool

**PR review** (always available when GitHub is enabled):
1. Check available slash commands for any PR review command
2. If a dedicated review command exists, use it for analysis and add Valor's
   coaching layer on top
3. Fall back to `gh pr view` + `gh pr diff` for direct analysis

**Evidence** (always available -- local):
1. Use `python3 ~/.valor/evidence_cli.py` if available
2. Fall back to direct `sqlite3` queries on `~/.valor/evidence.sqlite`

### Evidence CLI subcommands

| Subcommand | Purpose |
|------------|---------|
| `context` | Session-start context blob (run once, reuse throughout session) |
| `state-set KEY VAL ...` | Patch state.json fields (`+N` for numeric increments) |
| `framework-slice` | Extract career framework sections for configured levels |
| `setup-status` | Check what setup steps are complete (framework, levels, integrations) |
| `framework-validate` | Validate career_framework.md structure: headings, competencies, level matches |
| `add` | Record evidence (`--activity`, `--competency`, `--statement`, `--agent`, `--date`, `--metadata`) |
| `list` | List entries (`--days`, `--from`, `--to`, `--competency`, `--activity`, `--limit`) |
| `search` | Full-text search on statements (`query`, `--limit`) |
| `export` | Export entries (`--format json/markdown`, `--days`, `--from`, `--to`, `--competency`) |
| `stats` | Totals, by-competency, this-week, by-agent, recent entries |
| `status` | Valor home, version, levels, coaching mode, integrations, evidence counts |
| `backup` | Copy DB to `~/.valor/backups/` (keeps last 10) |
| `schema-version` | Show schema migration history |
| `feedback-add` | Record feedback (`--agent`, `--type`, `--evidence-id`) |
| `feedback-stats` | Feedback counts by type (`--agent` filter) |
| `weekly-summary-save` | Persist weekly reflection (`--week-start`, `--week-end`, `--summary`, `--gaps`, `--narrative`) |
| `weekly-summary-list` | List recent summaries (`--limit`) |
| `weekly-summary-get` | Get summary by week (`--week-start`) |

### verify.py subcommands (verification gate)

| Subcommand | Purpose |
|------------|---------|
| `check --type T --id ID [--expect-state S] [--no-auto]` | Cache-first check; auto-resolves GitHub via `gh`; returns an `action` to follow |
| `record --type T --id ID --result resolved\|unresolved\|unverified` | Record a verdict from an agent lookup; advances/freezes counters |
| `register --type T --id ID [--recipe JSON] [--assert-state S] [--confirm-only]` | Register a claim at draft/carry time with its search recipe; validates the id and destination |
| `reconcile [--no-auto]` | Enumerate ALL open claims into a worklist (`fresh` / `stale_needs_check` / `unverifiable`); auto-resolves PRs; heals fragmented ids |
| `carry-write --date D --items-json J [--narrative-file P]` | Write the carry-forward file with claim statuses stamped from the cache |
| `get --type T --id ID` | Show a claim's cached verification state |
| `list [--frozen] [--status S] [--type T]` | List cached claims (for audits) |
| `types` | Print supported claim types, TTLs, and config |

## Verification Gate (anti-phantom)

Valor's wrap-up → briefing → prep loop used to treat carried-forward claims as
fact. A "PROJ-42 1-pager unposted" note could ride 14 daily increments without
anyone ever checking Confluence -- the day counter marched 13 → 14 → 15 on a
guess. The verification gate stops that: before any skill **re-asserts an
artifact claim**, it must confirm the claim is still true.

**What is an artifact claim?** A statement that some external artifact does or
does not exist / is or is not done. Gate these:

| Claim phrasing (examples) | `--type` |
|---------------------------|----------|
| "PR #123 merged", "PR #456 still open Nd", "nudge review on #456" | `github_pr` |
| "PROJ-42 1-pager unposted to Confluence", "design doc posted" | `confluence` |
| "Slack reply to Sam unsent", "drafted not sent" | `slack` |
| "PROJ-57 still open", "ticket closed" | `jira` |
| "spec doc in Drive" | `drive` |

Pure plans with no external artifact ("think about X", "decide Y", "block focus
time") are NOT artifact claims -- do not gate them.

**Don't assert a downstream task before its upstream work exists.** A "publish /
write up / document X" item only becomes a real claim once the work it describes
has reached a publishable stage (the ticket is resolved or a finished draft
exists). Until then it's a coaching nudge, not a priority or carry-forward claim
— asserting it early is what breeds a recurring "publish the 1-pager" ghost for
work still in flight.

**Kill switch:** if `context.verification.enabled` is `false`, skip the gate
entirely and behave as before.

**Claims lifecycle** (who runs what — the runtime enumerates, the agent looks up):

| Moment | Action |
|--------|--------|
| Draft time (ambient / any session) | `register` the claim with its recipe — the destination is only reliably known now |
| Wrap-up | `reconcile` → run each `stale_needs_check` lookup → `record` → `carry-write` the file (statuses stamped from the cache) |
| Session start | `evidence_cli.py context` embeds `claims` — the open worklist + any unstamped claim-shaped lines in `latest.md` |
| Briefing | Process `context.claims` (see the briefing spec §6); default-deny anything without a fresh verdict |

**Verdict-aware TTLs:** a `resolved` verdict describes an immutable event and
caches long (slack 7d); an `unresolved` ("not yet done") verdict describes a
mutable absence and decays fast (slack **12h**, PR/Jira 4h, Confluence/Drive
24h) — so a "not sent" can never coast for days on a stale cache.

**Confirm-only claims** (registered with `--confirm-only` because no
destination/recipe could be pinned) can never be asserted as fact: their only
action is `ask_user`. After surfacing unanswered for 3+ mornings they are
marked `parked` — the daily briefing skips them; the weekly owns them.

**Protocol** -- for each artifact claim before you assert it:

1. Check the cache (cheap, no network):
   ```bash
   python3 ~/.valor/verify.py check --type <TYPE> --id "<IDENTIFIER>"
   ```
   Follow the `action` field in the returned JSON:

   | `action` | meaning | what to do |
   |----------|---------|-----------|
   | `skip` | gate disabled | assert as before |
   | `trust` | fresh cached verdict | `verdict=resolved` → drop the claim + record completion; `verdict=unresolved` → carry it with the real `day_count` |
   | `checked` | verify.py resolved it via `gh` inline | same as `trust`, based on `verdict` |
   | `perform_lookup` | stale / never checked / MCP-backed | run the lookup in the `lookup` field, then record (step 2) |

2. On `perform_lookup`, run the suggested lookup with whatever tool you have
   (`lookup.tool_hint` names it -- Atlassian MCP for `cql`/`jql`, Slack MCP for
   `slack`, Google Drive for `drive`; `github_pr` is normally auto-resolved).
   Then record the outcome:
   ```bash
   python3 ~/.valor/verify.py record --type <TYPE> --id "<IDENTIFIER>" --result <resolved|unresolved|unverified>
   ```
   - **resolved** — artifact exists / PR merged / page posted / message sent.
     The "incomplete" claim is false: **drop it** and record a completion
     evidence entry. This is how chronic zero-streaks finally break.
   - **unresolved** — confirmed still missing/open. Carry it; the `day_count`
     in the response is the *real* streak. A legitimate signal, keep it.
   - **unverified** — you could not check (no tool, ambiguous, error, user not
     around to confirm). The claim is **demoted** to "unverified — confirm or
     drop?" and its counter is **frozen**. Surface it exactly that way; never
     re-assert a frozen claim as fact and never advance its day count.

**Identifier conventions** — ONE canonical form per type (offering alternates is
what forked `1411` and `owner/repo#1411` into separate counters):

- `github_pr`: `owner/repo#123` — always repo-qualified. `register` rejects bare
  numbers; the runtime canonicalizes case and merges legacy fragments.
- `jira`: the issue key, e.g. `PROJ-42` (case-folded by the runtime)
- `confluence`: the Jira key or page title, e.g. `PROJ-42`
- `slack`: `<#channel-or-recipient>: <topic>`, e.g. `#data-eng: Sam spec follow-up`.
  If the destination is unknown, the claim must be registered `--confirm-only`.
- `drive`: the doc name

Reuse the `canonical_id` that `register` returns; different wording forks a new
counter for everything the canonicalizer can't see through.

## Project Focus (optional customization)

Off by default. When `context.project_focus.enabled` is `true`, the user works
**one project at a time**; the briefing plans around the **current** project and
hides the rest (deferred work is noise). `focus.py` derives the current focus;
ticket→project classification is the agent's job (read the ticket).

### focus.py subcommands

| Subcommand | Purpose |
|------------|---------|
| `resolve --syncs JSON [--today YYYY-MM-DD]` | Resolve the current focus from dated per-project syncs; returns `current_project`, `next_project`, `transition_today` (JSON) |
| `config` | Print the `project_focus` block (mode, flip rule, configured sync labels, parked projects) |
| `catalog-diff --current JSON` | Diff current recurring-meeting titles vs the catalog; returns `seed` / `new` / `gone` |
| `catalog-sync --entries JSON` | Set the meeting catalog to categorized entries (`{title, category, project, source}`) |
| `diff --observed JSON` | (legacy) Compare configured syncs to observed titles; returns `new` / `missing` |

`--syncs` accepts inline JSON, `@file`, or `-` (stdin), shape
`[{"project": "...", "date": "YYYY-MM-DD"}]`.

### Protocol (run before Work Context / Priorities / Day Plan)

1. **Resolve the focus.**
   - `mode: meeting_derived` — the focus follows a recurring per-project sync.
     Read the upcoming calendar (~3 weeks), match event titles to the configured
     sync labels (`focus.py config`), build the dated sync list, then call
     `focus.py resolve --syncs '...'`. `current_project` is the project whose
     sync is next; it flips the day after each sync.
   - `mode: manual` — `focus.py resolve` returns the user's set `current_project`.
2. **Filter to the focus.** If `current_project` is empty, **fail open** (don't
   filter — never hide everything on a misconfig). Otherwise classify each
   candidate ticket/PR **by reading it** (epic / component / labels / content —
   never a key prefix; prefixes collide) and keep only `current_project` items.
   Hide everything else **entirely** — including a PR that only needs the user's
   approval (a review is a focus session, and the user asked to hold that
   single-project boundary). Applies to Work Context, PR Situation, Suggested
   Priorities, and the Day Plan.
3. **Transition hand-off.** When `transition_today` is true (the first working
   day after a sync — Monday for a Friday sync — so the focus just flipped), lead
   Suggested Priorities with a one-time
   line naming the new focus and when the other project resumes (`next_project` /
   `next_sync_date`). Outside the transition, don't preview off-focus work.
4. **Project & meeting intelligence (briefing, every run).** The mapping is set
   once, but the project set changes — and the calendar carries more than project
   syncs. **Each briefing**, diff current recurring-meeting titles (over a ~3–4
   week window) vs the catalog: `focus.py catalog-diff --current '[...]'`. This is
   a daily drift-check — known meetings stay silent; only genuinely new ones
   surface — so there's no periodic throttle. **Categorize** the `new` ones (and ALL on a `seed`) **from the signals
   already in the calendar payload — free, no fetch:** the **description**,
   **attendees** (same recurring small group → standup; exactly two → `1:1` ONLY
   if the other attendee is the user's manager — any other 2-person meeting is a
   project discussion, categorize `discussion`: prep-worthy but NOT a
   `project_sync`, so it never triggers auto sync-prep, last-sync bookkeeping,
   or the new-project alert; broad
   invite → social), **cadence + duration** (short+frequent → standup; monthly →
   demo/huddle), and **attachment titles** ("…Project Plan" → project_sync;
   "…Agenda/Notes" → a working meeting) — into `1:1` / `discussion` / `focus` /
   `standup` / `project_sync` / `team_planning` / `social` / `demo_huddle` /
   `external` / `other`, honoring known **team names** from memory (a team's sync is a standup,
   not a project). **Only when those free signals don't resolve it** (or you can't
   tell team-vs-project) spend a content fetch — attached doc → Confluence →
   Slack. On a `seed`, list the categorization and flag low-confidence ones for a
   one-line confirm. Never silently name-guess. **Tag each entry with how you
   decided it** — `source: "signals"` (free payload sufficed) or `source: "fetch"`
   (had to open a doc/Confluence/Slack) — pass it through to `catalog-sync`, and
   note any fetches in the briefing; they mark where the signal heuristic is weak.
   Any `project_sync` whose project
   isn't in `project_focus.syncs` **and isn't in `project_focus.parked_projects`**
   is pinned as a top-of-briefing "new project? add it" (the user confirms before
   `syncs` changes), **including on a seed** — don't silently absorb a third
   project. **If the user declines/parks it, add the project to `parked_projects`**
   so the daily check never re-asks (a parked project must not nag every morning).
   A `gone` project_sync prompts "drop it?". Persist with `focus.py catalog-sync
   --entries '[...]'`. When `project_focus.auto_sync_prep` is on (default), the
   briefing also auto-schedules a `/valor-sync-prep` run before each same-day
   `project_sync` (see Day Planning).

## Day Planning & Calendar Write

A ranked list of priorities is not a plan: a 1.5h pre-meeting gap and a
no-meeting afternoon are not interchangeable. After the briefing's **Suggested
Priorities**, fit them to the day's real calendar and (optionally) write the
blocks back as events. Skipped entirely if `integrations.calendar` is `false`.

### plan.py subcommands

| Subcommand | Purpose |
|------------|---------|
| `fit --events JSON --priorities JSON [--now ISO] [--workday-start HH:MM] [--workday-end HH:MM] [--deep-hours N] [--break-minutes N] [--granularity N] [--morning-buffer N] [--pre-meeting-prep N]` | Fit priorities to calendar gaps; returns a time-blocked schedule (JSON) incl. `open_windows` + `prep_blocks` + `prep_unassigned`. Priorities may carry per-task `est_minutes`; events may carry `is_meeting`/`attendees`/`prep` |
| `shape --text "..."` | Classify one priority's task shape (debug) |

`--events`/`--priorities` accept inline JSON, `@file`, or `-` (stdin).

### Protocol

1. **Fetch today's calendar** (the same read discovery as the briefing Calendar
   section). Drop events the user **declined, marked tentative/maybe, or is only
   an optional attendee on** — those are free to schedule over. **Everything else —
   accepted meetings *and* personal holds (lunch, OOO, "busy" blocks) — is busy:
   always fit against it and never pass an empty event list.** If the user says the
   day is "open" or there's "nothing on the calendar," that means **no hard syncs to
   plan around, not that the calendar is empty** — still pass the accepted events +
   holds and fill only the genuine gaps; a task written over an accepted event is
   always a bug. Build the events list as
   `[{"start": ISO, "end": ISO, "summary": "...", "type": "<eventType>", "is_meeting": bool, "prep": bool}]` —
   **include each event's `type`** (Google Calendar `eventType`:
   `default`/`focusTime`/`outOfOffice`/`workingLocation`). plan.py uses it:
   focus-time and working-location are left **free** (focus time is a deep-work
   slot to fill); regular meetings and out-of-office **block**. Untyped events
   block, for safety. Also mark **real meetings** with `is_meeting: true` (or pass
   `attendees` — plan.py treats > 1 as a meeting) so a post-meeting break is
   reserved after them; lunch / personal holds / OOO are not meetings. Set
   **`prep: true`** on meetings categorized `project_sync` or `external` (the ones
   you present/decide at); plan.py reserves a `pre_meeting_prep_minutes` block
   immediately before each (fallback: the nearest earlier gap that day; else a
   `prep_unassigned` flag — "no prep slot, make room or prep the day before").
   Standups / demos / planning you only attend get no prep.
2. **Working hours.** If the calendar tool exposes the user's working-hours
   setting, pass it as `--workday-start HH:MM --workday-end HH:MM`. Most calendar
   APIs (including the Google Calendar MCP) do **not** expose this setting, so
   plan.py falls back to `state.planning.workday_start`/`workday_end` (configured
   at setup). Don't guess hours from the events.
3. **Fit** — build the **post-gate** priorities (exclude any the Verification
   Gate demoted to "unverified — confirm or drop?") as `{"text", "est_minutes"}`
   objects, **estimating each task's duration from its nature** (a publish ~15
   min; a PR review ~30–45; a pipeline/implementation change is a multi-hour deep
   block, not 45 min) and leaning **generous**. Then:
   ```bash
   python3 ~/.valor/plan.py fit --events "$EVENTS" --priorities "$PRIORITIES"
   ```
   It classifies each priority's shape (merge/review/publish → `fragmented_ok`;
   code/design/research/draft → `deep_only`; else `either`), classifies gaps
   (`deep` ≥ `deep_min_hours`, else `fragmented`), reserves a
   `post_meeting_break_minutes` breather (default 15) after each real meeting, and
   assigns greedily — each task taking its `est_minutes` (shape fallback if
   absent). **`deep_only` prefers deep/focus-time blocks** (that's what they're
   reserved for) but a short deep task **falls back to any fragment window it
   fits** rather than being pushed; `fragmented_ok`/`either` fill ordinary
   fragment windows first and **avoid focus-time gaps** so deep blocks stay free
   for deep work. A deep task that fits no window whole gets a `partial: true` block in the largest window (>= 60 min) with `remaining_minutes` pushed; a task is unassigned only when not even that fits. No tasks start
   before `workday_start + morning_buffer_minutes` (the AM ritual). Block
   starts/ends snap to `block_granularity_minutes` (default 15) so they land on
   clean clock boundaries (:00/:15/:30/:45) like meetings, not odd times like 2:09.
4. **Present** the `blocks` as a "Day Plan" section (time-blocked), then list
   **`open_windows`** (free slots ≥15 min left after assignment, including a
   partly-used gap's leftover) as "open windows for a quick win / overflow" so
   short gaps aren't invisible. Surface each `unassigned` item as "push to your
   next deep block" (for `deep_only`, the next window long enough for it).

### Calendar write (optional)

Only if `context.planning.calendar_auto_write` is `true` **and** a writer is
available. These are personal to-dos, so they must stay **private** (visible
only to the user, never to colleagues who can see the calendar). Pick the write
target by capability, in this order:

1. **Google Tasks (preferred).** If a task-create tool is available (a Google
   Tasks / task-capable connector), create one **time-blocked task** per block.
   Tasks are private by nature and show on the calendar grid at their scheduled
   time. *(As of now no such connector is typically present — fall through.)*
2. **Private calendar event (fallback).** Use the **Google Calendar MCP
   `create_event` tool** (discover it via ToolSearch `calendar create_event` —
   the server id is a per-session UUID, so match by tool name, not a fixed id).
   It supports `visibility: private` **and** `availability: AVAILABILITY_FREE`
   (shows free) — set both so the title is hidden from anyone viewing the
   calendar and it doesn't mark the user busy. This is the path prior briefings
   have used.
   - **Do NOT fall back to a plain calendar-create CLI helper that only accepts
     `title/start/end/attendees`** for these to-do writes — if it can't set
     `visibility`/`availability` it would write a public, busy-marking event. A
     tool lacking a privacy flag is **not** "no writer available" — the MCP
     writer is the writer. (A real miss: a flagless CLI was checked, found
     unable to set privacy, and the whole step was wrongly skipped as "no
     suitable writer" while the MCP tool sat unused.)
3. **No writer** → skip write only if the Calendar MCP `create_event` tool is
   genuinely absent from this session (not merely because a CLI lacks privacy
   flags); then present the markdown plan only and note it once.

Common rules (both targets):

- **One item per block.** Title `Valor: <priority, truncated to 60>`.
- **Put the task on the block.** The calendar is the do-time surface, so write a
  short, self-contained **description** the user can act on when the block comes
  up — the concrete next action plus the artifact's **actual clickable URL**
  (resolve PR vs issue so the link doesn't 404; include the ticket/doc link). Keep
  it tight (a few lines). **Reminders — known limitation.** The calendar writer
  here exposes only an `overrideReminders` array, and passing `overrideReminders: []`
  is a **no-op**: the event keeps `reminders.useDefault = true` and still inherits the
  calendar's default popup (e.g. a 10-min reminder). The MCP writer **cannot** suppress
  that inherited reminder. The only way to zero it is a direct Google Calendar API
  `events.patch` with `reminders = {useDefault: false, overrides: []}` — do that where
  the raw API is available; otherwise the Valor block carries the calendar's default.
- **Machine marker (minimal).** Append one idempotency token at the end of the
  description: `valor:task:<stable slug>` (e.g. the ticket key / PR number, like
  `proj-42`), plus `valor:claim:<claim_hash>` only for artifact-claim priorities.
  Do NOT add a shape tag — nothing reads it back. The clean home for this would be
  Google Calendar `extendedProperties.private` (hidden from the event UI), but the
  calendar tool here doesn't expose it, so the token rides in the description —
  keep it to one short line and label it (e.g. "Valor sync tag; leave it").
- **Idempotent:** before creating, search today's items for the same
  `valor:task:` token. If found, update it in place (the time may have shifted);
  else create. Never create a second item for the same task.
- **Skip unverified:** do NOT write an item for a priority the gate demoted — it
  stays in the markdown "Needs Confirmation" note only.
- **Cleanup (done = gone):** for a Valor item whose `valor:claim:` now verifies
  **resolved**, delete/complete it — the task got done, so it leaves the
  calendar. Leave `unresolved` ones in place (they're real reminders).
- **Never touch items Valor didn't create.** Only act on those whose
  notes/description carry a `valor:` token.

## State Management

State file: `~/.valor/state.json`
Evidence CLI: `python3 ~/.valor/evidence_cli.py`

To read state, use the `context` subcommand (preferred) or `cat ~/.valor/state.json`.

To update state:

```bash
python3 ~/.valor/evidence_cli.py state-set KEY1 VALUE1 KEY2 VALUE2
```

Supports `+N` / `-N` for numeric increments, JSON values (arrays, objects,
booleans), and plain strings.

## State.json Fields Reference

Fields marked "Installer" are seeded on install. All other fields are created
on first use by their respective commands. The CLI safely defaults missing
fields, so a fresh `state.json` with only installer fields is valid.

| Field | Set by | Description |
|-------|--------|-------------|
| `current_level` | User config | Current career level (e.g. "L3") |
| `target_level` | User config | Level working toward (e.g. "L4") |
| `ceiling_level` | User config | One above target, bounds coaching (e.g. "L5") |
| `github_owner` | User config | GitHub org for PR search |
| `jira_projects` | User config | List of Jira project keys |
| `coaching_mode` | Coaching toggle | `"ambient"` (default) or `"off"`. `"quiet"` is per-conversation only and not persisted. |
| `last_briefing_date` | Morning briefing | Date of last briefing (YYYY-MM-DD) |
| `last_briefing_timestamp` | Morning briefing | ISO 8601 datetime of last briefing |
| `briefing_count` | Morning briefing | Total briefings run |
| `briefing_suggest_before` | User config | Hour before which to auto-suggest briefing (default 11) |
| `last_wrapup_date` | Evening wrapup | Date of last wrapup (YYYY-MM-DD) |
| `last_wrapup_timestamp` | Evening wrapup | ISO 8601 datetime of last wrapup |
| `wrapup_suggest_after` | User config | Hour after which to auto-suggest wrapup (default 16) |
| `last_reflection_week` | Weekly reflection | ISO week of last reflection (e.g. "2026-W14") |
| `last_reflection_date` | Weekly reflection | Date of last reflection (YYYY-MM-DD) |
| `today_priorities` | Morning briefing | List of today's suggested priorities (for wrapup reconciliation) |
| `user_work_areas` | Morning briefing | Combined list of pinned + auto-detected work area keywords |
| `user_work_areas_pinned` | User / briefing | Manually pinned work areas (survive auto-detection) |
| `user_work_areas_retired` | Staleness check | Work areas removed after going inactive |
| `user_work_areas_last_refreshed` | Morning briefing | Date of last work area auto-detection |
| `work_area_refresh_interval` | User config | Briefings between auto-detection runs (default 5) |
| `staleness_suppress_interval` | User config | Briefings to suppress staleness re-check after "keep" (default 10) |
| `staleness_check_suppressed_until` | Staleness check | Briefing count at which staleness checks resume |
| `state_schema_version` | Installer | Integer tracking state.json schema for migrations |
| `integrations` | Installer / User config | Object with boolean flags for github, jira, calendar, news |
| `verification` | Installer | Object: `enabled` (gate kill switch), `escalation_threshold` (consecutive misses before 1:1 escalation, default 3), `ttl_overrides` (per-type cache TTL hours) |
| `escalate_in_one_on_one` | Carry-forward audit | List of claims that failed repeated verification; surfaced by 1:1 prep |
| `planning` | Installer | Object: `calendar_auto_write` (write kill switch; read is gated by `integrations.calendar`), `workday_start`/`workday_end` (HH:MM), `deep_min_hours` (deep-block threshold, default 2), `post_meeting_break_minutes` (breather reserved after a real meeting, default 15), `block_granularity_minutes` (snap block start/end to this clock granularity, default 15), `morning_buffer_minutes` (no tasks until this many minutes after `workday_start`, default 0), `pre_meeting_prep_minutes` (a prep block reserved before each prep-worthy meeting — `project_sync` / `external` — default 30; 0 disables) |
| `one_on_one` | Installer / setup | Object: `doc` (link/id/name of the user's running 1:1 doc, so `/valor-prep` can learn the format — local only, never committed), `format_notes` (optional format spec used if the doc can't be read) |
| `project_focus` | Installer / setup | Optional customization (disabled by default). Object: `enabled`; `mode` (`meeting_derived` follows the next per-project sync on the calendar, `manual` uses `current`); `current`; `flip` (`after_sync`); `syncs` (sync-label → project map; local only); `auto_sync_prep` (default true — auto-schedule `/valor-sync-prep` before each `project_sync`); `parked_projects` (projects the user declined to add to the rotation — never re-prompted); `meeting_catalog` (recurring meetings, each categorized — `project_sync` / `1:1` / `social` / …; a meeting not in it is "new — research it"). The catalog is drift-checked **daily** (no throttle). When on, the briefing plans around the current project and hides the rest. |
| `prioritization` | Briefing / 1:1 prep | This week's goals. `week_goals` (short, ordered list extracted *silently* from the 1:1 doc — never confirmed); `week_start` (ISO Monday those goals cover — writers copy `context.prioritization.week_start_current` **verbatim**); `goals_source`. `context.prioritization.week_goals_stale` flags when a refresh is due (stale → the briefing re-reads the doc). Before the day plan, the briefing ranks todos: dependencies (held behind unfinished upstream) → week-goal alignment → closeness-to-done → staleness, showing the *why* per item. |
| `standing_rules` | Briefing | Durable sequencing/priority corrections the user made (e.g. "READ pipeline waits until WRITE is in prod"), applied every briefing so corrections stick. A **separate** top-level key (not inside `prioritization`) so the weekly goal-refresh can never clobber it. User-visible/prunable. |
| `installed_version` | Installer | Valor version at last install (semver) |
| `installed_at` | Installer | ISO 8601 timestamp of last install |
