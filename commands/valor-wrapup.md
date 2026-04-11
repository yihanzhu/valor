# Valor Evening Wrap-up

Generate an end-of-day summary that captures accomplishments, carry-forward
items, and a brief career reflection. This pairs with the Morning Briefing
as bookends for the workday.

## When to Use

- User says: "wrap up", "end of day", "call it a day", "let's wrap up",
  "evening wrap-up", or signals they are done for the day
- Auto-suggested after 5pm on weekdays (see valor-agent.mdc trigger)

## 1. Gather Context

Use available sources to reconstruct the day's work. Run in parallel where
possible. If a source is unavailable, skip it gracefully.

### 1.1 Conversation Context

Review the current conversation for:
- Tasks completed (code written, PRs created, investigations concluded)
- Decisions made (design choices, prioritization changes)
- Cross-team interactions (messages drafted, alignment achieved)
- Open threads (questions asked but not answered, PRs awaiting review)

### 1.2 Git Activity

```bash
# Commits made today in the current workspace repo
git log --oneline --since="$(date +%Y-%m-%d)T00:00:00" --author="$(git config user.name)" 2>/dev/null | head -20
```

Run this in the current workspace repo. If the user mentions work in other
repos, run it there too -- but prefer the current workspace to avoid noise
from unrelated repositories.

### 1.3 Evidence Store

```bash
python3 ~/.valor/evidence_cli.py list --days 1
```

Use today's evidence entries to ensure nothing is missed.

### 1.4 Recalled Memories

Check if there were carry-forward items from a previous session:

Read the project's `MEMORY.md` file (in the project root or `.claude/`
directory). Look for entries tagged with `tomorrow` or `carry-forward` that
were saved by a previous `/valor-wrapup` invocation. If found, read the
linked memory file to recall the carry-forward items.

If no carry-forward memory files exist, skip this step.
Note which carry-forward items were addressed and which remain open.

### 1.5 Activity Reconciliation

Cross-reference the morning briefing's suggested priorities and today's
session transcripts against the evidence store. Activities often get drafted
or planned in a Cursor session but executed outside it (e.g., Slack messages
sent, Confluence pages updated, follow-ups posted). These are real work that
should be captured.

**Load morning priorities from state:** Read `today_priorities` from
`~/.valor/state.json`. This list is set by the morning briefing and
contains the day's planned priorities. If the key is missing (no briefing
today), skip the reconciliation against priorities.

**Steps:**

1. List today's evidence entries from the evidence store (section 1.3).
2. Compare against `today_priorities` -- which priorities were addressed?
   Which were not? Note unaddressed ones as carry-forward candidates.
3. Review agent transcripts from today's sessions for:
   - Messages drafted for Slack, email, or other channels
   - Confluence pages created or updated
   - Jira tickets updated
   - Cross-team coordination planned
   - Follow-up actions discussed
3. Ask the user to confirm which drafted/planned activities were executed:
   "I see you drafted a Slack message and discussed updating a Confluence
   page. Did you end up doing these? Any other work today not captured
   in our session?"
4. For each confirmed activity not already in the evidence store, record it:
   ```bash
   python3 ~/.valor/evidence_cli.py add \
     --activity <type> \
     --competency <competency> \
     --statement "<specific description>" \
     --agent valor-evening-wrapup \
     --date $(date +%Y-%m-%d)
   ```

This reconciliation step ensures the evidence store reflects actual work done,
not just work done inside sessions.

## 2. Summarize the Day

### 2.1 Accomplishments

List concrete things completed today. Be specific — file paths, PR numbers,
ticket IDs, decisions made. Group by theme if there were multiple workstreams.

### 2.2 Carry-Forward Items

List tasks that need attention tomorrow. For each item, note:
- What it is (specific and actionable)
- Current state (where it was left off)
- Any blockers or dependencies

### 2.3 Career Reflection

Map the day's activities to target-level competencies (from `~/.valor/career_framework.md`).
Keep this brief — 2-3 sentences max:
- Which competencies were exercised today
- One specific suggestion for tomorrow that would strengthen a gap area

## 3. Output Format

```markdown
## Valor Evening Wrap-up — [Day], [Date]

### Accomplished Today
- [Activity 1] — *[competency tag if significant]*
- [Activity 2]
- ...

### Tomorrow's Pickup
1. [Task] — [current state / where left off]
2. [Task] — [current state]
3. ...

### Career Note
[2-3 sentences: competencies exercised, one suggestion for tomorrow]
```

## 4. Capture as Memory

After presenting the wrap-up, save carry-forward items as a memory file so
the next session recalls them automatically.

Use the Write tool to create a markdown file at
`.claude/memories/carry-forward-[DATE].md` (where `[DATE]` is today's date
in `YYYY-MM-DD` format) with the following structure:

```markdown
---
name: carry-forward-[DATE]
description: "Evening wrap-up carry-forward items for [TOMORROW_DATE]"
type: project
tags: [tomorrow, wrap-up, carry-forward]
---

# Carry-Forward Items — [DATE]

[List each carry-forward item with its current state and any blockers,
matching the "Tomorrow's Pickup" section from the wrap-up output]
```

Then update (or create) `MEMORY.md` in the project root to include a pointer
to the new file:

```markdown
- [carry-forward-[DATE]](.claude/memories/carry-forward-[DATE].md) — Evening wrap-up carry-forward items for [TOMORROW_DATE]
```

If `MEMORY.md` already exists, append the new entry. If a previous
carry-forward entry exists for the same date, replace it.

## 5. Update State

Set `last_wrapup_date` and `last_wrapup_timestamp` in `~/.valor/state.json`:

```bash
python3 -c "
import json
from datetime import datetime
from pathlib import Path
p = Path.home() / '.valor' / 'state.json'
p.parent.mkdir(parents=True, exist_ok=True)
state = json.loads(p.read_text()) if p.exists() else {}
state['last_wrapup_date'] = '$(date +%Y-%m-%d)'
state['last_wrapup_timestamp'] = datetime.now().isoformat(timespec='seconds')
p.write_text(json.dumps(state, indent=2))
"
```

## 6. Fallbacks

| Scenario | Action |
|----------|--------|
| No git activity today | Use conversation context and evidence store only |
| Evidence store empty | Proceed with conversation context and git log |
| Memory file unavailable | Skip memory recall; present wrap-up only |
| State update fails | Continue; wrap-up is still valid |
