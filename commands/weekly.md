
# Valor Weekly Reflection

Generate a weekly reflection that maps the user's activities to target-level
competencies (from `~/.valor/career_framework.md`), identifies gaps, and
produces a concise 1:1 narrative for their manager.

## When to Use

- User says: "weekly reflection", "reflect on my week", "weekly summary",
  or "what did I do this week"
- **Friday (auto-suggested):** Generate the reflection while the week is
  fresh. The valor-agent rule auto-suggests on Friday if not done this week.
- **Monday (re-read):** If the user missed Friday, generate it Monday
  morning using the previous ISO week's data rather than the new week that
  just started.
- Before a 1:1 meeting to prepare talking points

## Integration Check

Before gathering data, read `integrations` from `~/.valor/state.json`.
Skip sections for any integration set to `false` -- do not probe or print
a skip message.

| Integration | Sections skipped when `false` |
|-------------|-------------------------------|
| `jira`      | Jira (1.2) |
| `github`    | GitHub (1.3) |

Evidence (1.1) is always available (local).

## 1. Gather Data

Run all enabled data sources in parallel. If an enabled source fails at
runtime, note it once and suggest the user fix the tool or disable the
integration in state.json.

### 1.0 Define the Reflection Week

Before gathering any data, compute one explicit ISO week window and reuse it
for every source:

- If today is Monday and the user is catching up on a missed Friday reflection,
  reflect on the **previous** ISO week.
- Otherwise, reflect on the **current** ISO week.

Set these values once:

- `reflection_week_start`: Monday of the week being reflected (`YYYY-MM-DD`)
- `reflection_week_end_exclusive`: the following Monday (`YYYY-MM-DD`)
- `previous_week_start`: `reflection_week_start - 7 days`

When a source cannot express the exclusive end date directly, fetch from
`reflection_week_start` and discard any result with a timestamp on or after
`reflection_week_end_exclusive`.

### 1.1 Evidence Store

```bash
# Fetch enough evidence to cover both the reflection week and the previous week
python3 ~/.valor/evidence_cli.py list --days 14

# Overall stats, including the current ISO week's competency breakdown
python3 ~/.valor/evidence_cli.py stats
```

Use the `list --days 14` output as the source of truth for weekly reflection
data:

- Reflection week entries: `date >= reflection_week_start` and
  `date < reflection_week_end_exclusive`
- Previous week entries: `date >= previous_week_start` and
  `date < reflection_week_start`

Use `stats` as supplemental context only. If the reflection week is not the
current ISO week (for example, a Monday catch-up run), derive the counts from
the filtered `list` output instead of from `stats.this_week`.

### 1.2 Jira — Atlassian MCP

1. Call `getAccessibleAtlassianResources` to obtain `cloudId`.
2. Reuse `reflection_week_start` and `reflection_week_end_exclusive`.
3. Call `searchJiraIssuesUsingJql` with:

**JQL for tickets completed or moved during the reflection week:**
```
assignee = currentUser() AND status changed >= "REFLECTION_WEEK_START" AND status changed < "REFLECTION_WEEK_END_EXCLUSIVE"
```

Use `maxResults: 50` and include fields: `summary`, `status`, `issuetype`, `updated`, `resolution`.

**If Atlassian MCP is unavailable:** Skip the Jira section. If
`integrations.jira` is `true`, note: "Jira tools not found -- install an
Atlassian/Jira plugin, or set `integrations.jira` to `false` in state.json."

### 1.3 GitHub

Reuse `reflection_week_start` and `reflection_week_end_exclusive`.

```bash
# PRs merged by the user during or after the reflection week start
gh pr list --author @me --state merged --search "merged:>=REFLECTION_WEEK_START" --json number,title,mergedAt,repository --limit 20

# PRs the user reviewed during or after the reflection week start
gh pr list --search "reviewed-by:@me merged:>=REFLECTION_WEEK_START" --state merged --json number,title,author,mergedAt --limit 15
```

After fetching, discard any PR whose `mergedAt` is on or after
`reflection_week_end_exclusive`. This keeps Friday runs and Monday catch-up
runs aligned to the same reflected week.

If `gh` is not authenticated, skip and note: "GitHub: `gh auth login`
needed, or set `integrations.github` to `false` in state.json."

### 1.4 Previous Weeks (for trend comparison)

Use the same evidence pull from section 1.1 and partition it into:

- Reflection week: `[reflection_week_start, reflection_week_end_exclusive)`
- Previous week: `[previous_week_start, reflection_week_start)`

Compare competency counts across those two explicit windows.

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

Count activities per competency for the reflection week. If you have previous-week data, compute deltas (e.g., "up from 2 to 4").

## 3. Compare to Previous Weeks

If the evidence pull returned data for both windows, compare:
- Reflection week competency counts vs previous week
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

## 8. Persist Weekly Summary

After presenting the reflection, save the structured output so the prep
command and future reflections can reference past weeks:

```bash
python3 ~/.valor/evidence_cli.py weekly-summary-save \
  --week-start "[reflection_week_start, YYYY-MM-DD]" \
  --week-end "[reflection_week_end, YYYY-MM-DD]" \
  --summary '{"subject_matter": N, "industry_knowledge": N, "collaboration": N, "autonomy_scope": N, "leadership": N}' \
  --gaps '["gap competency 1", "gap competency 2"]' \
  --narrative "[The 3-4 sentence narrative from the For Your 1:1 section]"
```

Fill in the actual competency counts from the reflection, the identified
gaps, and the narrative text. If the CLI is unavailable, skip silently --
the reflection itself is the primary output.

## 9. Update State

Set `last_reflection_week` in `~/.valor/state.json` to the ISO week that was
actually reflected:

```bash
python3 -c "
import json
from datetime import datetime, timedelta
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
p.parent.mkdir(parents=True, exist_ok=True)
state = json.loads(p.read_text()) if p.exists() else {}
today = datetime.now().date()
current_week_start = today - timedelta(days=today.weekday())
reflection_week_start = current_week_start - timedelta(days=7) if today.weekday() == 0 else current_week_start
iso_year, iso_week, _ = reflection_week_start.isocalendar()
state['last_reflection_week'] = f'{iso_year}-W{iso_week:02d}'
state['last_reflection_date'] = datetime.now().strftime('%Y-%m-%d')
p.write_text(json.dumps(state, indent=2))
"
```

## 10. Fallbacks

| Scenario | Action |
|----------|--------|
| Evidence store missing or empty | Proceed with enabled integrations only. Note: "Start recording evidence for richer reflections." |
| Jira disabled or unavailable | Skip Jira; use evidence + GitHub if enabled. |
| GitHub disabled or unavailable | Skip GitHub; use evidence + Jira if enabled. |
| All integrations disabled | Build reflection from evidence store only. This is a valid workflow. |
| Evidence CLI add fails | Continue; note: "Evidence recording unavailable." |
| State update fails | Continue; reflection is still valid. |
