# Valor Utilities Reference

Reference file for Valor agents. Read on demand when running agent skills --
do NOT load into every conversation.

## Integrations

Valor uses external tools for data gathering. Which integrations are available
is tracked in `~/.valor/state.json` under the `integrations` key:

```json
{
  "integrations": {
    "github": true,
    "jira": true,
    "calendar": true,
    "news": true
  }
}
```

**Before gathering data, read `integrations` from state.json.** If an
integration is `false`, skip that section entirely -- do not probe for the
tool and do not print a "not available" message. The user has already
indicated they don't have that integration.

If an integration is `true`, attempt to use it with the discovery steps
below. If it fails at runtime (e.g. `gh` not authenticated), note it once
and suggest the user set it to `false` in state.json if they don't plan
to configure it.

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

## State Management

State file: `~/.valor/state.json`
Evidence CLI: `python3 ~/.valor/evidence_cli.py`

To read state: `cat ~/.valor/state.json 2>/dev/null || echo '{}'`

To update state, run:
```
python3 -c "
import json
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
p.parent.mkdir(parents=True, exist_ok=True)
state = json.loads(p.read_text()) if p.exists() else {}
state['KEY'] = 'VALUE'
p.write_text(json.dumps(state, indent=2))
"
```

## State.json Fields Reference

| Field | Set by | Description |
|-------|--------|-------------|
| `current_level` | User config | Current career level (e.g. "L3") |
| `target_level` | User config | Level working toward (e.g. "L4") |
| `ceiling_level` | User config | One above target, bounds coaching (e.g. "L5") |
| `github_owner` | User config | GitHub org for PR search |
| `jira_projects` | User config | List of Jira project keys |
| `coaching_mode` | Quiet mode toggle | `"ambient"`, `"quiet"`, or `"off"` |
| `last_briefing_date` | Morning briefing | Date of last briefing (YYYY-MM-DD) |
| `last_briefing_timestamp` | Morning briefing | ISO 8601 datetime of last briefing |
| `briefing_count` | Morning briefing | Total briefings run |
| `briefing_suggest_before` | User config | Hour before which to auto-suggest briefing (default 11) |
| `last_wrapup_date` | Evening wrapup | Date of last wrapup (YYYY-MM-DD) |
| `last_wrapup_timestamp` | Evening wrapup | ISO 8601 datetime of last wrapup |
| `wrapup_suggest_after` | User config | Hour after which to auto-suggest wrapup (default 17) |
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
| `integrations` | Installer / User config | Object with boolean flags for github, jira, calendar, news |
