# Getting Started

This guide walks you through setting up Valor from scratch. You'll have a
working career coaching layer in about 5 minutes, no external integrations
required.

## 1. Install

```bash
git clone https://github.com/yihanzhu/valor.git ~/valor
cd ~/valor
bash install.sh              # Claude Code (default)
# or
bash install.sh --target cursor   # Cursor
```

This creates `~/.valor/` for local state and evidence, and installs Valor's
rule and commands into your coding agent.

## 2. Configure Your Career Framework

Edit `~/.valor/career_framework.md` with your company's career ladder. The
template has placeholder sections -- fill in your actual levels, competencies,
and values.

If your company uses a standard engineering ladder (IC1-IC6 or L3-L8), map
each level to the five competency areas:

- **Subject Matter Expertise** -- technical depth, code quality, system design
- **Industry Knowledge** -- awareness of tools, methods, and trends
- **Internal Collaboration** -- cross-team work, alignment, communication
- **Autonomy & Scope** -- independent execution, design ownership
- **Leadership** -- go-to expertise, mentoring, process improvement

## 3. Set Your Levels

Edit `~/.valor/state.json`:

```json
{
  "current_level": "L3",
  "target_level": "L4",
  "ceiling_level": "L5"
}
```

- `current_level`: where you are now
- `target_level`: what you're working toward (coaching targets this)
- `ceiling_level`: one above target (prevents over-coaching)

When you get promoted, update these three fields.

## 4. Disable Integrations You Don't Have

The installer auto-detects GitHub (`gh` CLI) and sets the rest to `true`.
Disable integrations you don't have in `~/.valor/state.json`:

```json
{
  "integrations": {
    "github": true,
    "jira": false,
    "calendar": false,
    "news": false
  }
}
```

Disabled integrations are skipped silently -- no probing, no error messages.
See [docs/integrations.md](integrations.md) for details on each integration.

## 5. Try It Out

### Ambient coaching (automatic)

Start working normally. After you complete a meaningful task (debug a bug,
review a PR, investigate an issue), Valor adds a brief coaching footer
connecting your work to target-level competencies.

### Morning briefing

Say "morning briefing" or use `/valor-briefing` (Claude Code). Even without
external integrations, you'll get career coaching based on your evidence
history.

### Evening wrap-up

Say "wrap up" or use `/valor-wrapup`. Valor summarizes what you did today
from git history and evidence entries, and saves carry-forward items for
tomorrow.

### Record evidence manually

You can also record evidence directly:

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity code_written \
  --competency subject_matter \
  --statement "Refactored auth module to use strategy pattern" \
  --agent manual
```

### Check your stats

```bash
python3 ~/.valor/evidence_cli.py stats
```

## 6. Add Integrations Later

As you connect more tools, enable them in `state.json`:

| Integration | What you need | What it adds |
|-------------|---------------|--------------|
| GitHub | `gh auth login` | PR tracking, review history, merged PR summaries |
| Jira | Atlassian MCP plugin | Ticket tracking, sprint context, task discovery |
| Calendar | Google Calendar plugin | Meeting prep, schedule-aware prioritization |
| News | WebSearch support | AI/ML and tech news in morning briefings |

Each integration enriches the commands but none are required for the core
career coaching loop.

## What's Next

- Run a few briefings and wrap-ups to build evidence
- Try `valor-weekly` at the end of the week for a 1:1 prep narrative
- Say "what should I work on" to find high-impact tasks
- Say "valor quiet" to suppress coaching for a conversation
