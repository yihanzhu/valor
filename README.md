# Valor

**Versatile Assistant for Life, Organization, and Reasoning**

Valor is a local-first ambient career coach for developers. It works through
your daily assistant interactions, captures meaningful work evidence, maps that
work to your own career framework, and nudges you toward stronger habits over
time.

Status: alpha. The current repo is a working local core for Claude Code,
Codex CLI, and Cursor.

## Why Valor Exists

Most career tools are either:

- manual brag docs
- manager and HR systems
- commit-only summaries

Those approaches miss a lot of real engineering work: debugging, design
thinking, cross-team alignment, operational ownership, mentoring, and the
drafting work that happens before anything is merged.

Valor is built around a different assumption: developers already spend a large
part of their day working with assistants and agents. If that interaction layer
is made useful, careful, and privacy-conscious, it can become an ambient coach
that helps with both daily execution and long-term growth.

## Design Principles

- **Dev-first**: built around real developer workflows, not generic HR forms.
- **Local-first**: your data lives on your machine in files you control.
- **Privacy-first**: no built-in telemetry, analytics, or cloud sync in this repo.
- **Inspectable**: most of the system is plain Markdown and Python.
- **Bring your own framework**: Valor adapts to your company's ladder instead of
hardcoding one.

## What Valor Does Today


| Agent                 | Trigger                                        | What it does                                                                    |
| --------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------- |
| **Morning Briefing**  | Auto before 11am, or `/valor-briefing`         | Jira tickets, PRs, calendar, news, coaching, priorities                         |
| **PR Review Coach**   | `/valor-pr-review` or "help me review"         | Senior-level code review guidance with architecture, testing, and tone coaching |
| **Design Doc Coach**  | `/valor-design-doc` or "how should I approach" | Structured design guidance with options, trade-offs, and recommendations        |
| **Weekly Reflection** | Auto Friday, or `/valor-weekly`                | Week summary mapped to competencies, gap analysis, and 1:1 narrative            |
| **Task Identifier**   | `/valor-tasks` or "what should I work on"      | High-impact work prioritized by career growth potential                         |
| **Evening Wrap-up**   | Auto after 5pm, or `/valor-wrapup`             | Day summary, carry-forward items, and career reflection                         |
| **1:1 Prep**          | `/valor-prep` or "prep for 1:1"                | Evidence-grounded prep document for manager 1:1s                                |


Beyond the discrete commands, Valor also supports **ambient coaching**. After a
meaningful task, it can classify the work, connect it to target-level
competencies, and suggest one concrete "next-level" move.

## Local Data Model

Valor stores its working state under `~/.valor/`:

- `state.json`: user settings and rolling assistant state
- `career_framework.md`: your career ladder and company values
- `evidence.sqlite`: structured evidence store
- `backups/`: local database backups
- `carry-forward/`: local wrap-up notes and next-day pickup files

Installed prompts and rules live in your assistant's local directories:

- Claude Code: `~/.claude/CLAUDE.md` and `~/.claude/commands/`
- Codex CLI: `~/.codex/AGENTS.md` and `~/.codex/skills/`
- Cursor: `~/.cursor/rules/` and `~/.cursor/skills/`

The current runtime is local-first, but not fully air-gapped by itself.
See [PRIVACY.md](PRIVACY.md) for the exact trust boundary.

## Privacy and Trust

This repo does **not** include:

- built-in telemetry
- analytics pipelines
- automatic cloud sync
- a hosted backend

Valor may still interact with external systems through the tools already
configured in your assistant environment, such as:

- `gh` for GitHub data
- Jira or Atlassian MCP tools
- Calendar integrations
- web search when a command explicitly uses it

Important: if your host assistant sends prompts or workspace context to a
hosted model provider, that behavior is governed by the host assistant and
model provider, not by this repo. Valor does not override those policies.

## Install

**Quick install (one command):**

```bash
curl -fsSL https://raw.githubusercontent.com/yihanzhu/valor/main/install.sh | bash -s -- --clone
```

This clones the repo to `~/.valor/repo/`, creates `~/.valor/` for local state
and evidence, and installs Valor for all supported agents (Claude Code,
Codex CLI, and Cursor). Valor checks for updates daily and auto-applies
minor/patch releases.

**Manual install:**

```bash
git clone https://github.com/yihanzhu/valor.git ~/.valor/repo
cd ~/.valor/repo
bash install.sh
```

**Install for a specific target only:**

```bash
bash install.sh --target claude-code   # Claude Code only
bash install.sh --target codex         # Codex CLI only
bash install.sh --target cursor        # Cursor only
```

**Upgrade manually:**

```bash
cd ~/.valor/repo && bash install.sh --upgrade
```

For a complete walkthrough including career framework setup, level
configuration, and integration options, see
[docs/getting-started.md](docs/getting-started.md).

## First-Time Setup

After install, configure two local files:

**1. Career framework**: `~/.valor/career_framework.md`

Fill in your company's levels, competencies, and values. Valor uses these
definitions for coaching instead of imposing its own career ladder.

**2. State config**: `~/.valor/state.json`

Example:

```json
{
  "current_level": "L3",
  "target_level": "L4",
  "ceiling_level": "L5",
  "github_owner": "YourGitHubOrg",
  "jira_projects": ["PROJ1", "PROJ2"]
}
```

When you get promoted, update the three level fields. The framework file can
stay the same.

## Prerequisites

Valor works best when these tools are already available in your environment:


| Tool                         | What for                      | Required?   |
| ---------------------------- | ----------------------------- | ----------- |
| `gh` CLI                     | GitHub PR and issue data      | Recommended |
| Jira / Atlassian integration | Ticket discovery              | Recommended |
| Calendar integration         | Meetings and schedule context | Optional    |


If one of these is unavailable, the affected command should skip that section
and continue with the other available signals.

## Usage

Automatic suggestions:

- start a conversation before 11am on a weekday for a morning briefing
- chat on Friday for a weekly reflection prompt
- chat after 5pm on a weekday for an evening wrap-up prompt

Commands:

- `/valor-briefing`
- `/valor-pr-review`
- `/valor-design-doc`
- `/valor-weekly`
- `/valor-tasks`
- `/valor-wrapup`
- `/valor-prep`

Natural language also works:

- "start my day"
- "review PR #892"
- "design doc for PROJ-123"
- "what did I do this week"
- "what should I work on"
- "wrap up"
- "prep for 1:1"

Ambient coaching controls:

- `valor quiet`: suppress coaching for this conversation
- `valor off`: disable ambient coaching until re-enabled
- `valor on`: re-enable ambient coaching

## Development

Runtime code is Python stdlib-only.

Development and test setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 -m compileall src tests
```

If you are editing installed artifacts locally, you can verify they still match
the repo source:

```bash
./install.sh --check                          # All targets (default)
./install.sh --target claude-code --check     # Claude Code only
```

## Project Layout

```text
valor/
├── .claude-plugin/         # Claude Code plugin manifest (discovery only)
├── .codex-plugin/          # Codex CLI plugin manifest (discovery only)
├── bin/                    # CLI wrappers (valor-evidence)
├── commands/               # User-invoked assistant commands
├── rules/                  # Always-applied Valor rule
├── skills/                 # Plugin skills (setup)
├── src/                    # Evidence CLI, career framework, utilities
├── tests/                  # Test suite
├── docs/                   # Architecture, integrations, getting started
├── website/                # Minimal static landing page
├── install.sh              # Installer for Claude Code, Codex CLI, and Cursor
├── marketplace.json        # Plugin catalog
├── VERSION                 # Version (single source of truth)
└── ...                     # LICENSE, ROADMAP, CONTRIBUTING, etc.
```

## Contributing and Security

- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Privacy model: [PRIVACY.md](PRIVACY.md)
- Community expectations: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security reporting: [SECURITY.md](SECURITY.md)

## License

Licensed under [Apache-2.0](LICENSE).

The `Valor` name and branding are not granted by the software license.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the current public roadmap and
[PRODUCT_VISION.md](PRODUCT_VISION.md) for the longer-term local-first vision.