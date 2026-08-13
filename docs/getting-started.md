# Getting Started

This guide walks you through setting up Valor from scratch. You'll have a
working career coaching layer in about 5 minutes, no external integrations
required.

## 1. Install

```bash
git clone https://github.com/yihanzhu/valor.git ~/.valor/repo
cd ~/.valor/repo
# pin to the latest release tag (stays on the default branch if none tagged yet):
tag="$(git tag --list | python3 scripts/latest_release_tag.py)"; [ -n "$tag" ] && git checkout "$tag"
bash install.sh                           # All targets (default)
# or install for a specific target:
bash install.sh --target claude-code      # Claude Code only
bash install.sh --target codex            # Codex CLI only
bash install.sh --target cursor           # Cursor only
```

This creates `~/.valor/` for local state and evidence, and installs Valor's
rule and commands into your coding agent.

**Updates are notify-only.** Releases are tagged `vX.Y.Z`. After install, Valor
checks daily for a newer release and, if one exists, **tells you** — it never
pulls `main` or checks anything out on its own. Update manually by checking out
the tag and re-installing; pin a version by also disabling the daily check:

```bash
git -C ~/.valor/repo fetch --tags && git -C ~/.valor/repo checkout vX.Y.Z && bash ~/.valor/repo/install.sh
# then set "update_check_interval_hours": 0 in ~/.valor/state.json
```

(If no release has been tagged yet, the `git checkout` above is a no-op and you
install from the default branch; the daily check starts surfacing releases once
one is cut.)

## 2. Run Setup

Open your agent and run `/valor-setup` (or say "set up valor"). The guided
setup walks you through:

1. **Career framework** -- paste your company's career ladder and Valor
   converts it into the right format with the five competency axes
2. **Level selection** -- pick your current level and the one you're targeting
3. **Integrations** -- configure GitHub org, Jira projects, and disable
   tools you don't use

No career ladder handy? Setup offers the ready-made, fully generic frameworks in
[`examples/frameworks/`](../examples/frameworks/) — a software-engineering IC
ladder, an engineering-manager ladder, and a no-formal-levels growth framework —
or it can generate one from your job title. Pick one, then customize. You can
always re-run `/valor-setup` later.

### Manual setup (alternative)

If you prefer to configure manually:

- Edit `~/.valor/career_framework.md` with your company's levels,
  competencies, and values
- Set `current_level`, `target_level`, `ceiling_level` in
  `~/.valor/state.json` to match your framework's level codes
- Disable integrations you don't have in `state.json` under `integrations`

See [docs/integrations.md](integrations.md) for details on each integration.

## 3. Try It Out

### Ambient coaching (automatic)

Start working normally. After you complete a meaningful task (debug a bug,
review a PR, investigate an issue), Valor adds a brief coaching footer
connecting your work to target-level competencies.

### Morning briefing

Say "morning briefing" or use `/valor-briefing` (Claude Code). Even without
external integrations, you'll get career coaching based on your evidence
history.

### Evening wrap-up

Say "wrap up" or use `/valor-wrapup`. Valor reconstructs the day from git
history, evidence entries, and your agent sessions across workspaces, captures
meeting notes from calendar-event attachments into your evidence store, and
saves carry-forward items for tomorrow.

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
python3 ~/.valor/evidence_cli.py export --days 7 --format markdown
python3 ~/.valor/evidence_cli.py weekly-summary-list --limit 4
```

## 4. Add Integrations Later

As you connect more tools, enable them in `state.json`:

| Integration | What you need | What it adds |
|-------------|---------------|--------------|
| GitHub | `gh auth login` | PR tracking, review history, merged PR summaries |
| Jira | Atlassian MCP plugin | Ticket tracking, sprint context, spare-capacity backlog pickups |
| Calendar | Google Calendar plugin | Meeting prep, time-blocked day plan, meeting-notes capture |
| News | WebSearch support | AI/ML and tech news in morning briefings |

Each integration enriches the commands but none are required for the core
career coaching loop.

## What's Next

- Run a few briefings and wrap-ups to build evidence
- Say "build a review console for #123" or use `/valor-pr-console` on a PR that's
  hard to review cold — you get an interactive C4 walkthrough plus a
  diff-verified mastery quiz (needs GitHub)
- Try `/valor-weekly` at the end of the week for a weekly reflection
- Say "prep for 1:1" or use `/valor-prep` before your manager sync
- Say "sync prep" or use `/valor-sync-prep` ~30 min before a project sync
- Say "half-year reflection" or use `/valor-reflection` at review time for a
  self-reflection draft built from your evidence
- Say "feedback about my manager" or use `/valor-upward-feedback` at review time
  for a manager upward-feedback draft grounded in your meeting notes + 1:1 evidence
- Say "valor quiet" to suppress coaching for a conversation
- Showing Valor to your team? [`examples/demo/`](../examples/demo/) seeds a
  fictional profile into a throwaway `HOME` so you can demo every workflow
  without exposing your own work
