# Integrations

Valor commands pull data from external tools when available. Every command
works without any external integrations -- the local evidence store and git
history are always available.

## Configuration

Integrations are controlled by the `integrations` object in
`~/.valor/state.json`:

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

Set an integration to `false` to disable it. Disabled integrations are
skipped silently -- no probing, no "unavailable" messages.

The installer auto-detects `gh` CLI availability. Other integrations
default to `true` and should be set to `false` if you don't have the
corresponding tool.

## Integration Matrix

Which integrations each command uses:

| Command | GitHub | Jira | Calendar | News | Evidence (local) |
|---------|--------|------|----------|------|------------------|
| Morning Briefing | PRs to review, your open PRs, Monday catch-up | Active tickets, watched tickets | Today's events, RSVP status | AI/ML, tech, world headlines | Competency stats, coaching tone |
| PR Review Coach | **Required** -- fetches PR diff and metadata | -- | -- | -- | Records review evidence |
| Design Doc Coach | -- | Ticket lookup for context | -- | -- | Records design doc evidence |
| Weekly Reflection | Merged PRs, reviewed PRs | Tickets completed this week | -- | -- | Competency breakdown, trends |
| Task Identifier | Open issues, PRs to review | Unassigned, stale, high-priority tickets | -- | -- | Competency gaps for ranking |
| Evening Wrap-up | -- | -- | -- | -- | Today's entries, carry-forward |
| 1:1 Prep | Merged/reviewed PRs (optional) | Completed tickets (optional) | -- | -- | Primary source: evidence + weekly summaries |

**Legend:** "Required" means the command cannot function without it. "--"
means the command does not use that integration. All other entries are
optional enrichment.

## Setup per Integration

### GitHub (`integrations.github`)

**Tool:** `gh` CLI

**Setup:**
```bash
gh auth login
```

**Used for:** PR metadata, PR diffs, issue lists, merged PR history.

**Auto-detected:** Yes -- the installer checks `gh auth status`.

### Jira (`integrations.jira`)

**Tool:** Atlassian MCP plugin or Jira-related slash commands

**Setup:** Install an Atlassian/Jira MCP plugin in your coding agent. Set
`jira_projects` in `~/.valor/state.json` to your project keys
(e.g. `["PROJ", "TEAM"]`).

**Used for:** Ticket lookup, JQL searches for active/stale/unassigned work.

**Auto-detected:** No -- defaults to `true`. Set to `false` if you don't
use Jira.

### Calendar (`integrations.calendar`)

**Tool:** Google Calendar MCP plugin or calendar-related slash commands

**Setup:** Install a Google Calendar plugin in your coding agent.

**Used for:** Today's meetings, RSVP status, prep suggestions.

**Auto-detected:** No -- defaults to `true`. Set to `false` if you don't
use Google Calendar.

### News (`integrations.news`)

**Tool:** WebSearch (built into most coding agents)

**Setup:** No setup required if your coding agent supports web search.

**Used for:** Morning briefing news section (AI/ML, tech, world headlines).

**Auto-detected:** No -- defaults to `true`. Set to `false` if you don't
want news in briefings or your agent doesn't support web search.

## Local-Only Mode

If all integrations are set to `false`, Valor still works:

- **Morning Briefing:** Career coaching from evidence store, suggested
  priorities based on recent activity.
- **Evening Wrap-up:** Git log, evidence entries, carry-forward items.
- **Weekly Reflection:** Evidence-based competency breakdown and trends.
- **Task Identifier:** Competency gap analysis with suggestions.
- **Design Doc Coach:** Fully functional -- asks user for context directly.
- **1:1 Prep:** Fully functional from evidence store and weekly summaries.
- **PR Review Coach:** Requires GitHub (cannot function without it).

This is a valid workflow for users who want career coaching without
connecting external services.
