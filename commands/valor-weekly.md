
# Valor Weekly Reflection

Generate a weekly reflection that maps the user's activities to target-level
competencies (from `~/.valor/career_framework.md`), identifies gaps, and
produces a concise 1:1 narrative for their manager.

## When to Use

- User says: "weekly reflection", "reflect on my week", "weekly summary",
  "1:1 prep", or "what did I do this week"
- **Friday (auto-suggested):** Generate the reflection while the week is
  fresh. The valor-agent rule auto-suggests on Friday if not done this week.
- **Monday (re-read):** If the user missed Friday, generate it Monday
  morning using last week's data. The reflection covers the same ISO week
  regardless of when it runs.
- Before a 1:1 meeting to prepare talking points

## 1. Gather Data

Run all data sources in parallel. If a source is unavailable, skip that section gracefully — never error out or block the reflection.

### 1.1 Evidence Store

```bash
# This week's evidence entries (reflection_window_days from state.json, default 7)
python3 ~/.valor/evidence_cli.py list --days 7

# Overall stats including this week's competency breakdown
python3 ~/.valor/evidence_cli.py stats
```

### 1.2 Jira — Atlassian MCP

1. Call `getAccessibleAtlassianResources` to obtain `cloudId`.
2. Compute the start of this week (Monday) as `YYYY-MM-DD` in the user's local timezone.
3. Call `searchJiraIssuesUsingJql` with:

**JQL for tickets completed or moved this week:**
```
assignee = currentUser() AND status changed DURING (startOfWeek(), now())
```

Use `maxResults: 50` and include fields: `summary`, `status`, `issuetype`, `updated`, `resolution`.

**If Atlassian MCP is unavailable:** Skip the Jira section and note: "Jira data unavailable — install Atlassian MCP plugin for ticket tracking."

### 1.3 GitHub

Compute `YYYY-MM-DD` as the Monday of the current week.

```bash
# PRs merged by the user this week
gh pr list --author @me --state merged --search "merged:>=YYYY-MM-DD" --json number,title,mergedAt,repository --limit 20

# PRs the user reviewed (merged this week)
gh pr list --search "reviewed-by:@me merged:>=YYYY-MM-DD" --state merged --json number,title,author,mergedAt --limit 15
```

If `gh` is not authenticated, skip and note: "GitHub data unavailable — run `gh auth login`."

### 1.4 Previous Weeks (for trend comparison)

```bash
# Last 14 days to compare this week vs last week
python3 ~/.valor/evidence_cli.py list --days 14
```

Partition entries by ISO week (from `date` field). Compare this week's counts per competency to last week's.

## 2. Map to Competencies

Use the five competencies from `~/.valor/career_framework.md`. Map each activity to one or more competencies:

| Competency | CLI Value | Examples |
|------------|-----------|----------|
| Subject Matter Expertise | `subject_matter` | Technical work, code quality, ML concepts, designs |
| Industry Knowledge | `industry_knowledge` | New tools, methods, algorithms, tech exploration |
| Internal Collaboration | `collaboration` | Cross-team work, task identification for others, alignment |
| Autonomy & Scope | `autonomy_scope` | Independent execution, design docs, PR reviews beyond own scope |
| Leadership | `leadership` | Go-to expertise, design decisions, improvements identified |

**Mapping rules:**
- Jira tickets completed → `subject_matter` (or `autonomy_scope` if complex)
- PRs merged (own code) → `subject_matter`
- PRs reviewed (own team) → `autonomy_scope`
- PRs reviewed (cross-team) → `collaboration`, `leadership`

Use `user_work_areas` from `~/.valor/state.json` to determine what
constitutes "cross-team" -- repos or topics outside those areas.
- Evidence entries from CLI → use the entry's `competency` field directly
- Design docs, tech debt proposals → `autonomy_scope`, `subject_matter`
- Cross-team alignment, mentoring → `collaboration`, `leadership`

Count activities per competency for the current week. If you have last week's data, compute deltas (e.g., "up from 2 to 4").

## 3. Compare to Previous Weeks

If `list --days 14` returned data, group entries by ISO week and compare:
- This week's competency counts vs last week
- Highlight trends: "Cross-team reviews up from 1 to 3 this week."
- Note consistency: "Subject matter entries steady at 5."

If no previous data exists, omit the trend section or note: "No prior week data for comparison."

## 4. Identify Gaps

Which competencies have 0 or low entries this week? For each gap, suggest **specific** actions for next week:

- **Subject Matter:** "Pick up a technical spike or complex ticket."
- **Industry Knowledge:** "Read one paper or try a new tool; record a 5-min summary."
- **Internal Collaboration:** "Review 1–2 PRs from another team; align on one cross-team task."
- **Autonomy & Scope:** "Draft a design doc for an upcoming ticket or review 3+ PRs."
- **Leadership:** "Identify one improvement and document it; or be the go-to on a technical decision."

If gaps suggest the user needs help finding work, mention the task identifier:
"Say 'what should I work on' to find high-impact tasks that fill these gaps."

## 5. Generate 1:1 Narrative

Write 3–4 sentences the user can tell their manager, highlighting senior-level behaviors:
- Lead with impact: what shipped, what was unblocked
- Mention scope: cross-team work, design thinking, PR reviews beyond own tickets
- Note any leadership: go-to decisions, improvements identified
- Keep it conversational, not a bullet list

## 6. Output Format

Present the reflection in this structure:

```markdown
## Valor Weekly Reflection — Week of [MONDAY DATE]

### What You Did
- [Activity 1] — *[competency tag]*
- [Activity 2] — *[competency tag]*
- ...

### Competency Breakdown
| Competency | Count | Trend |
|------------|-------|-------|
| Subject Matter Expertise | N | [vs last week if available] |
| Industry Knowledge | N | ... |
| Internal Collaboration | N | ... |
| Autonomy & Scope | N | ... |
| Leadership | N | ... |

### Gaps & Next Week Focus
- **[Gap competency]:** [Specific suggestion]

### For Your 1:1
"[3–4 sentence narrative paragraph the user can say to their manager]"
```

## 7. Record Evidence

After presenting the reflection, record it with a **specific** statement
that summarizes this week's key outcomes -- not a generic "completed
reflection" phrase.

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity weekly_reflection_completed \
  --competency autonomy_scope \
  --statement "Weekly reflection: [top shipped item], [strongest competency with count], gap in [weakest competency]. Focus next week: [specific action]." \
  --agent valor-weekly-reflection
```

**Good example:** "Weekly reflection: shipped PR #1025 right-boundary fix,
strongest in autonomy_scope (5 entries), gap in leadership (0 entries).
Focus next week: review cross-team PR and propose pipeline improvement."

**Bad example:** "Completed weekly reflection for week of 2026-03-24"

## 8. Update State

Set `last_reflection_week` in `~/.valor/state.json` to the current ISO week number (1–53):

```bash
python3 -c "
import json
from datetime import datetime
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
p.parent.mkdir(parents=True, exist_ok=True)
state = json.loads(p.read_text()) if p.exists() else {}
iso_year, iso_week, _ = datetime.now().isocalendar()
state['last_reflection_week'] = f'{iso_year}-W{iso_week:02d}'
state['last_reflection_date'] = datetime.now().strftime('%Y-%m-%d')
p.write_text(json.dumps(state, indent=2))
"
```

## 9. Fallbacks

| Scenario | Action |
|----------|--------|
| Evidence store missing or empty | Proceed with Jira/GitHub only. Note: "Start recording evidence for richer reflections." |
| Jira MCP unavailable | Skip Jira; use evidence + GitHub. |
| GitHub not authenticated | Skip GitHub; use evidence + Jira. |
| All external sources unavailable | Build reflection from evidence store only; suggest connecting Jira/GitHub. |
| Evidence CLI add fails | Continue; note: "Evidence recording unavailable." |
| State update fails | Continue; reflection is still valid. |
