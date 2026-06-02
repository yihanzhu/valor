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
| `get --type T --id ID` | Show a claim's cached verification state |
| `list [--frozen] [--status S] [--type T]` | List cached claims (used by the carry-forward audit) |
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

**Kill switch:** if `context.verification.enabled` is `false`, skip the gate
entirely and behave as before.

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

**Identifier conventions** (keep them stable so one claim keeps one counter):

- `github_pr`: `owner/repo#123`, `repo#123` (owner from `github_owner`), or `#123`
- `jira`: the issue key, e.g. `PROJ-42`
- `confluence`: the Jira key or page title, e.g. `PROJ-42`
- `slack`: a short stable description, e.g. `Sam spec-review follow-up`
- `drive`: the doc name

The gate normalizes case/whitespace, but different wording forks a new counter.
Reuse the same identifier every run for the same claim.

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
| `installed_version` | Installer | Valor version at last install (semver) |
| `installed_at` | Installer | ISO 8601 timestamp of last install |
