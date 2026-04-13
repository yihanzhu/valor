
# Valor Morning Briefing

Generate a comprehensive morning briefing that cross-references the user's work
items, surfaces opportunities for career growth, and provides relevant news.

## Integration Check

Before gathering data, read `integrations` from `~/.valor/state.json`:

```bash
python3 -c "import json; print(json.dumps(json.loads(open('$HOME/.valor/state.json').read()).get('integrations', {})))"
```

For any integration set to `false`, skip all sections that depend on it
entirely -- do not probe for the tool and do not print a skip message.

| Integration | Sections skipped when `false` |
|-------------|-------------------------------|
| `jira`      | Jira Tickets (1) |
| `github`    | GitHub PRs (2), Monday catch-up PR queries |
| `calendar`  | Calendar (3) |
| `news`      | News (4) |

Career Coaching (5) and Evidence are always available (local).

## Data Gathering

Gather data from all enabled sources in parallel. If an enabled source fails
at runtime (e.g. `gh` not authenticated), note it once and suggest the user
either fix the tool or set the integration to `false` in state.json.

### 1. Jira Tickets

**Preferred: Atlassian MCP**

Check if Atlassian MCP tools are available by looking in the MCP tools directory.
If `jira_search_issues` (or similar) exists, use it with these JQL queries:

- Assigned to current user, status in (In Progress, To Do, Blocked, In Review):
  `assignee = currentUser() AND status IN ("In Progress", "To Do", "Blocked", "In Review") ORDER BY status, updated DESC`
- Recently updated tickets the user is watching:
  `watcher = currentUser() AND updated >= -2d ORDER BY updated DESC`

**Fallback: Jira slash commands**

If Atlassian MCP is not available, check for any
Jira-related slash command (look for commands matching `*jira*`). If found,
read and use it to search for tickets.

**If nothing is available:** Skip the Jira section. If `integrations.jira` is
`true`, note: "Jira tools not found -- install an Atlassian/Jira plugin, or
set `integrations.jira` to `false` in `~/.valor/state.json`."

### 2. GitHub PRs

Use `gh` CLI via the Bash tool. Prefer `gh search prs` over `gh pr list`
because it works globally (no git repo context required):

```bash
# PRs requesting your review
gh search prs --review-requested=@me --state=open --json number,title,author,createdAt,url,repository --limit 20

# Your open PRs
gh search prs --author=@me --state=open --json number,title,createdAt,url,repository --limit 20
```

If `gh` is not authenticated, skip and note: "GitHub: `gh auth login` needed,
or set `integrations.github` to `false` in `~/.valor/state.json`."

For cross-team detection: if a PR's repository or author is outside the user's
typical scope (based on evidence store history), flag it as "cross-team."

### 3. Calendar

**Check for calendar slash commands:** Check for any Google
Calendar or calendar-related slash command (look for commands matching
`*google*` or `*calendar*`). If found, read and use it to fetch today's events.

**If not available:** Skip. If `integrations.calendar` is `true`, note:
"Calendar tools not found -- install a Google Calendar plugin, or set
`integrations.calendar` to `false` in `~/.valor/state.json`."

**RSVP status (mandatory):** After fetching the event list, retrieve full
details for each event (including attendee response statuses). For each event:

1. **Check the user's own RSVP** (`responseStatus` where `self: true`).
   Show status next to each event: *accepted*, *tentative*, *needsAction*
   (no RSVP), or *declined*.
2. **Filter out declined events.** If the user has declined, show it with
   strikethrough (~~event~~) rather than as an active commitment.
3. **Check other attendees for small meetings** (<=5 attendees). If a key
   attendee has declined, note it -- e.g., "Alice: declined". This prevents
   prepping for meetings that won't happen.
4. **Distinguish today vs. next-week preview.** Only today's accepted/tentative
   events affect priority suggestions. Next-week events are informational.

### 4. News

Use the WebSearch tool to search for **general** current news. Always
include the current date in search queries to anchor results.

**Coverage window:** The news section covers a continuous timeline from
the last briefing to now -- no gaps, no overlaps.

Read `last_briefing_timestamp` from `~/.valor/state.json` (ISO 8601
format). The coverage window is:

  `[last_briefing_timestamp, now)`

For example, if last briefing was Tuesday 10:00 AM and this briefing is
Wednesday 9:00 AM, cover news published between Tuesday 10 AM and
Wednesday 9 AM.

Translate the window into search terms:

- **Same-day re-run** (< 12 hours): `"[topic] news today [Month Day Year]"`
- **Next-day** (12-36 hours): `"[topic] news today [Month Day Year]"`
- **Weekend gap** (2-3 days): `"[topic] news this week [Month Year]"`
- **Extended absence** (4+ days): `"[topic] news past week [Month Year]"`
  and select more headlines (4-5 per category).

Always search for **broad, general topics** -- never narrow the search
query to the user's work areas:

- `"AI ML research news [window] [date]"` -- general AI/ML
- `"tech industry news [window] [date]"` -- general tech
- `"world news headlines [window] [date]"` -- general world

**Work area relevance annotations:** After collecting headlines, check if
any naturally overlap with the user's `user_work_areas` from state.json.
If a headline is relevant, add a brief inline note explaining the
connection. Do NOT force relevance -- only annotate when there is a genuine
match. Most headlines will have no annotation and that is fine.

**Recency filter (mandatory):** Only include articles published within
the coverage window. Discard anything published before
`last_briefing_timestamp`, even if highly relevant. If a result has no
clear publication date, use WebFetch to check the article page. If still
unclear, skip it.

Select 2-3 headlines per category. For AI/ML news, add a brief note on
relevance to the user's work if applicable.

**Source URLs:** Every news headline must be plain text, with the source URL on
an indented line below. Use the URLs returned by the WebSearch tool. If a
headline has no URL, omit it rather than showing an unsourced item.

### 5. Career Coaching

**Check if evidence store exists** at `~/.valor/evidence.sqlite`.

If it exists, query it using the evidence CLI:
```bash
python3 ~/.valor/evidence_cli.py stats
```

Use these counts to identify:
- Strongest competency area (highest count)
- Gap areas (lowest count or zero)
- Specific opportunities tied to today's work items

**If evidence store doesn't exist or is empty:** Skip the coaching section
entirely. Don't show empty placeholders. The section will appear naturally
after a few briefings accumulate evidence.

**Competency reference** (from `valor/src/competency.py`):
- Subject Matter (`subject_matter`): technical designs, clean code, ML concepts
- Industry Knowledge (`industry_knowledge`): awareness of tools, methods, algorithms
- Collaboration (`collaboration`): cross-team alignment, task identification
- Autonomy & Scope (`autonomy_scope`): independent execution, PR reviews beyond own scope, design docs
- Leadership (`leadership`): go-to expert, design decisions, identifying improvements

### Coaching Tone Evolution

Determine tone from `briefing_count` in `~/.valor/state.json`:

- **Beginner (0-10):** Explain what each competency means and why the suggested
  action matters. E.g., "Cross-team PR reviews build Leadership visibility --
  senior engineers are expected to review beyond their direct scope."
- **Intermediate (11-40):** Concise nudges with data. E.g., "Cross-team review
  ratio: 10% (target: 25%). Sarah's #892 is a good candidate."
- **Advanced (40+):** Data only. E.g., "Cross-team: 10/25%. #892 available."

## Briefing Format

Present the full briefing in this structure. Use markdown formatting.
Cross-reference items across sections (link tickets to meetings, PRs to tickets).

```
## Valor Morning Briefing -- [Day], [Date]

### Work Context
- [Ticket ID]: [Title] -- *[Status]* ([days in status])
  [Cross-reference if this ticket relates to a meeting, PR, or blocker resolution]
  [Career coaching annotation if applicable]
- ...

### PR Situation
**Awaiting your review:**
- #[num]: [title] (from [author], [age])
  [Flag if cross-team] [Coaching annotation if applicable]

**Your open PRs:**
- #[num]: [title] -- [approvals], [comments], [CI status]
  [Nudge if action needed, e.g. "2 unresolved comments from Mike"]

### Today's Calendar
- [time] -- [meeting] ([duration]) -- *[your RSVP status]*
  [Prep suggestion if related to a ticket or PR]
- ~~[time] -- [meeting]~~ *declined* [or: key attendee declined]

### News

**AI/ML**
- headline -- [1-sentence relevance note if applicable]
  url

**Tech Industry**
- headline
  url

**World**
- headline
  url

### Career Focus
[Only show if evidence store has data]
- Strongest area: [competency] ([count] entries)
- Gap: [competency] ([count] entries)
- Today's opportunities:
  1. [specific action tied to today's work]
  2. [specific action]

### Suggested Priorities
1. [action] -- [why first]
2. [action]
3. ...
```

## Monday / Return-from-Absence Mode

If today is Monday, OR if `last_briefing_timestamp` (or `last_briefing_date`
for backward compatibility) is more than 1 day ago, add a "Catch-Up"
section after Work Context:

```
### Weekend/Absence Catch-Up
- PRs merged while you were away: [list from gh pr list --state merged --search "updated:>YYYY-MM-DD"]
- New tickets assigned since [last_briefing_date]
- Status changes on your tickets
```

Run additional queries:
```bash
# PRs merged since last briefing
gh pr list --state merged --search "updated:>LAST_DATE" --author @me --json number,title,mergedAt --limit 10
gh pr list --state merged --search "updated:>LAST_DATE review-requested:@me" --json number,title,mergedAt --limit 10
```

## Evidence Recording

Do NOT record a generic "morning briefing completed" entry. Instead, record
what was actually prioritized and surfaced. Build the `--statement` dynamically
from the briefing content.

**Template:**
```bash
python3 ~/.valor/evidence_cli.py add \
    --activity morning_briefing_completed \
    --competency autonomy_scope \
    --statement "Prioritized: [top 2-3 items from Suggested Priorities]. Key items: [N] tickets, [M] PRs, [P] meetings." \
    --agent valor-morning-briefing
```

**Examples of GOOD statements:**
- "Prioritized: PROJ-123 data pipeline fix (blocked on data), PR #245 review. Key items: 3 tickets, 1 PR, 2 meetings."
- "Prioritized: unblock PROJ-200 cache migration, prep for 1:1. Key items: 2 tickets, 0 PRs, 1 meeting. Gap flagged: no cross-team reviews this week."

**Examples of BAD statements (never use these):**
- "Completed daily planning and prioritization via Valor briefing"
- "Morning briefing completed"

If the user acts on a coaching suggestion during the conversation (e.g.,
reviews a cross-team PR, starts a design doc), record additional evidence
with a specific statement describing what they did:

```bash
python3 ~/.valor/evidence_cli.py add \
    --activity pr_review_cross_team \
    --competency collaboration \
    --statement "Reviewed cross-team PR #892 from Sarah -- flagged missing error handling in retry logic" \
    --agent valor-morning-briefing
```

Available activities and competencies are defined in `valor/src/competency.py`.
Competencies: subject_matter, industry_knowledge, collaboration, autonomy_scope, leadership.

## State Update

After the briefing, update `~/.valor/state.json`:
- Set `last_briefing_date` to today (kept for backward compatibility)
- Set `last_briefing_timestamp` to the current ISO 8601 datetime
- Increment `briefing_count`
- Set `today_priorities` to the list of suggested priorities (short strings)
  so the evening wrap-up can reconcile against them

```bash
python3 -c "
import json
from datetime import datetime
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
p.parent.mkdir(parents=True, exist_ok=True)
state = json.loads(p.read_text()) if p.exists() else {}
state['last_briefing_date'] = '$(date +%Y-%m-%d)'
state['last_briefing_timestamp'] = datetime.now().isoformat(timespec='seconds')
state['briefing_count'] = state.get('briefing_count', 0) + 1
state['today_priorities'] = $PRIORITIES_LIST  # agent replaces with actual list
p.write_text(json.dumps(state, indent=2))
"
```

### Work Area Auto-Detection

Refresh `user_work_areas` in state.json periodically or when state has no
`user_work_areas` at all. The refresh cadence is controlled by
`work_area_refresh_interval` in state.json (default: 5 briefings if not set).

Check: `briefing_count % refresh_interval == 0 or "user_work_areas" not in state`

#### Step 1: Gather project signals

Use data already collected for the briefing plus lightweight exploration:

1. **Jira tickets** (already fetched): collect summaries and descriptions of
   all active tickets.
2. **Recent PRs** (already fetched): collect titles and repo names.
3. **Repo READMEs**: inspect the current workspace first, then nearby project
   directories the assistant can already access. Look for repos or project
   roots that contain a `.git/` directory or project files (`README.md`,
   `PROJECT.md`, `pyproject.toml`). Read the README/PROJECT.md of each
   (first 80 lines is enough). Skip repos that look like forks, personal
   config, or one-off experiments.

#### Step 2: Extract research-relevant keywords

From the gathered signals, derive **technical keywords that would surface
relevant AI/ML and industry news**. Apply these rules:

- **NO internal project names** (e.g., "Project Atlas", "System Phoenix"). These
  won't match any external news articles.
- **YES to the underlying technical concepts** (e.g., "automated data
  cataloging", "LLM metadata generation", "text-to-SQL").
- Group keywords by project/domain for organizational clarity.
- Keywords are used for **relevance annotations** on general news
  headlines, not for narrowing search queries.
- Include both specific terms ("content moderation ML") and broader terms
  ("RAG retrieval augmented generation") so annotations can match a wider
  range of general headlines.

#### Step 3: Staleness check on pinned keywords

Before merging, check whether pinned keywords are still relevant:

1. Read `user_work_areas_pinned` from state.
2. For each **group** of pinned keywords (they cluster by project -- e.g.,
   keywords related to the same project area all cluster together as a
   group), check if the project still has active work:
   - Any assigned Jira tickets in non-Done status that relate to this area?
   - Any open PRs or recent commits in related repos?
   - Any currently active repo in the user's accessible workspaces still tied
     to this domain?
3. If a keyword group has **no active signals** (all tickets Done/Closed,
   no recent PRs, no active repo), flag it for removal. Present the user
   with a brief prompt:
   > "These pinned work areas appear inactive -- remove from news tracking?
   > [list of stale keywords]. Say 'keep' to retain them."
4. If the user confirms removal, move the keywords from
   `user_work_areas_pinned` to `user_work_areas_retired` (a new list in
   state.json for historical reference).
5. If the user says "keep", leave them pinned. Do not ask again for
   `staleness_suppress_interval` briefings (default: 10 if not set in
   state). Track via `staleness_check_suppressed_until` count in state.

**Manual removal:** If the user says "remove X from my work areas" or
"I'm done with project Y", immediately remove related keywords from both
`user_work_areas` and `user_work_areas_pinned`, and add them to
`user_work_areas_retired`.

#### Step 4: Merge and write to state

Merge intelligently:

1. Surviving pinned keywords (after staleness removal) stay.
2. Auto-detected keywords replace the non-pinned portion.
3. Final list = surviving pinned + auto-detected, deduplicated.

When the user **manually requests** a keyword addition (like "add Project Atlas
keywords"), add those keywords to `user_work_areas_pinned` so they survive
future auto-detection runs.

```bash
python3 -c "
import json
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
state = json.loads(p.read_text())
# pinned and auto_detected should be set by the agent before this step
pinned = state.get('user_work_areas_pinned', [])
auto_detected = $AUTO_DETECTED_LIST  # agent replaces this with the actual list
combined = list(dict.fromkeys(pinned + auto_detected))  # dedup, preserve order
state['user_work_areas'] = combined
state['user_work_areas_last_refreshed'] = '$(date +%Y-%m-%d)'
p.write_text(json.dumps(state, indent=2))
"
```

## Follow-Up Interaction

After the briefing, the user may ask follow-up questions. Handle them naturally:

- **"Tell me more about [ticket/PR]"** -- Fetch details using the appropriate
  tool (Atlassian MCP for tickets, `gh pr view` for PRs)
- **"Draft a design doc for [ticket]"** -- Use the
  `/valor-design-doc` command for structured options and trade-offs
- **"What should I say in standup?"** -- Synthesize a concise standup update
  from the briefing data (yesterday, today, blockers)
- **"Help me review [PR]"** -- Use the
  `/valor-pr-review` command for coached review with career-level annotations
- **"Prioritize differently"** -- Re-order based on user's input

These follow-ups are part of the natural conversation -- no special trigger needed.
