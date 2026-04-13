# Valor 1:1 Prep

Generate a structured document for your next 1:1 with your manager, grounded
in evidence from the last 1--2 weeks plus any saved weekly reflections.

## When to Use

- User says: "prep for 1:1", "1:1 prep", "prepare for my 1:1", "what should
  I talk about in my 1:1", or runs `/valor-prep`
- Useful before a scheduled manager sync or performance check-in

## 1. Check Integrations

Read `integrations` from `~/.valor/state.json`:

```bash
python3 -c "import json; from pathlib import Path; s=json.loads((Path.home()/'.valor'/'state.json').read_text()); print(json.dumps(s.get('integrations',{})))"
```

| Integration | Used for |
|-------------|----------|
| `github` | Recent PRs merged/reviewed (context for talking points) |
| `jira` | Tickets completed/in-progress (context for talking points) |

If an integration is `false`, skip its section silently. Evidence and weekly
summaries are always available.

## 2. Gather Evidence

### 2.1 Recent Evidence (primary source)

```bash
python3 ~/.valor/evidence_cli.py export --days 14 --format json
```

This is the primary data source. Group entries by competency and count.
If the evidence store is empty, note it and proceed with whatever other
data is available.

### 2.2 Weekly Summaries (trend context)

```bash
python3 ~/.valor/evidence_cli.py weekly-summary-list --limit 4
```

If available, use these to show trends across weeks (e.g., "collaboration
has been growing over the last 3 weeks"). If none exist, skip the trend
section if none are available yet.

### 2.3 Career Framework

Read `~/.valor/career_framework.md` for:
- Target-level competency definitions
- Company values (if listed)

Read `~/.valor/state.json` for `current_level`, `target_level`, `ceiling_level`.

### 2.4 External Context (if integrations enabled)

If `integrations.github` is true:
```bash
gh pr list --state merged --author @me --limit 10
gh search prs --review-requested=@me --state=closed --limit 5
```

If `integrations.jira` is true and `jira_projects` is set:
Use Atlassian MCP or Jira slash commands to find tickets transitioned to
Done/Closed in the last 2 weeks.

These are supplementary -- evidence entries are the primary source.

## 3. Analyze

### 3.1 Competency Map

For each competency, count evidence entries and categorize:

| Competency | Entries | Strength/Gap | Key Examples |
|------------|---------|-------------|--------------|
| Subject Matter Expertise | N | strong/developing/gap | ... |
| Industry Knowledge | N | ... | ... |
| Internal Collaboration | N | ... | ... |
| Autonomy & Scope | N | ... | ... |
| Leadership | N | ... | ... |

**Strength:** 3+ entries. **Developing:** 1--2 entries. **Gap:** 0 entries.

### 3.2 Trends (if weekly summaries available)

Compare competency counts across the last 2--4 weekly summaries. Note:
- Competencies that are growing (more entries week-over-week)
- Competencies that are stagnating or declining
- Gaps that have persisted across multiple weeks

### 3.3 Target-Level Alignment

Map the strongest evidence entries to specific target-level competency
definitions from `career_framework.md`. Identify:
- Where the user is **meeting** target-level expectations
- Where the user is **approaching** but not yet at target level
- Where there is a **gap** with a concrete suggestion

## 4. Output Format

Present the prep document in this structure:

```markdown
# 1:1 Prep — [date range]

## Highlights
- [Top 2-3 accomplishments with specific evidence]

## By Competency

### [Competency Name] — [N entries, strength/developing/gap]
- **Evidence:** [specific statements from evidence store]
- **Target-level alignment:** [how this maps to target-level definition]
- **Talking point:** "[suggested thing to mention to your manager]"

[Repeat for each competency with at least 1 entry]

## Gaps to Discuss
- **[Gap competency]:** 0 entries this period. Suggestion: [specific action]

## Trends
[Only if weekly summaries are available]
- [Competency X] growing: N last week → M this week
- [Competency Y] persistent gap: 0 entries for 3 weeks

## Suggested Asks
- [1-2 things the user could ask their manager for, based on gaps]
  e.g., "Ask for a cross-team review opportunity to build collaboration evidence"

## Narrative
"[3-5 sentence summary the user can use as an opening for the 1:1.
Covers what they shipped, where they're growing, and what they want to
focus on next. Grounded in evidence, not generic.]"
```

## 5. Tone and Framing

- **Concrete, not aspirational.** Every talking point should reference a
  specific evidence entry, PR, or ticket.
- **Balanced.** Show both strengths and gaps -- managers value self-awareness.
- **Actionable.** Gaps should come with specific next steps, not vague
  "do more of this."
- **Promotion-aware.** Frame accomplishments in terms of the target level,
  not the current level. Use the career framework definitions.

## 6. Record Evidence

After generating the prep document:

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity one_on_one_prep \
  --competency leadership \
  --statement "1:1 prep: [period]. Highlights: [top item]. Strengths: [strongest competency]. Gaps: [weakest]. Ask: [suggested ask]." \
  --agent valor-prep
```

## 7. Fallbacks

| Scenario | Action |
|----------|--------|
| Evidence store empty | Note that evidence recording needs to start. Offer to help with setup. Use any available GitHub/Jira data to build a minimal prep. |
| No weekly summaries | Skip trends section. Note: "Run `/valor-weekly` to enable trend tracking." |
| GitHub/Jira disabled | Build prep from evidence only. This is a valid workflow. |
| Career framework not configured | Use generic competency names. Note: "Configure `~/.valor/career_framework.md` for personalized coaching." |
| Evidence CLI fails | Note the error. Proceed with any available data. |
