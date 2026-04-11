# Valor Utilities Reference

Reference file for Valor agents. Read on demand when running agent skills --
do NOT load into every conversation.

## Tool Discovery

Before any Valor agent gathers data, discover what tools are available.
Do NOT hardcode specific tool names. Instead, check for capabilities:

**For Jira/ticket data:**
1. Check for Atlassian/Jira MCP tools (e.g. `jira_search_issues`)
2. Check available slash commands for any Jira-related command
3. Fall back to asking the user to provide ticket details

**For PR/code review:**
1. Check available slash commands for any PR review command (e.g. `/sa-ds-pr-review`)
2. If a dedicated review command exists, use it for analysis and add Valor's
   coaching layer on top
3. Fall back to `gh pr view` + `gh pr diff` for direct analysis

**For GitHub data:**
1. Use `gh` CLI (most common)
2. Check MCP tools for GitHub integration

**For calendar:**
1. Check MCP tools for Google Calendar integration
2. Check available slash commands for calendar-related commands
3. Skip if unavailable

**For news:**
1. Use WebSearch tool

**For evidence:**
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
