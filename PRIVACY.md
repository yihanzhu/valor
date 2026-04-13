# Privacy Model

Valor is designed to be local-first, but "local-first" is not the same thing as
"nothing ever leaves your machine." This document explains the current trust
boundary as clearly as possible.

## What Valor Stores Locally

By default, Valor stores data under `~/.valor/`:

- `state.json`: preferences and rolling assistant state
- `career_framework.md`: your career ladder and company values
- `evidence.sqlite`: structured evidence entries and summaries
- `backups/`: local SQLite backups created by the CLI
- `carry-forward/`: local wrap-up notes and next-day pickup files

Installed prompts and rules live in assistant-specific local directories:

- Claude Code: `~/.claude/CLAUDE.md` and `~/.claude/commands/`
- Codex CLI: `~/.codex/AGENTS.md` and `~/.codex/skills/`
- Cursor: `~/.cursor/rules/` and `~/.cursor/skills/`

## What This Repo Does Not Do

The code in this repository does not include:

- built-in telemetry
- usage analytics
- automatic cloud sync
- a hosted backend
- automatic data sharing with the maintainer

## When Network Access Can Still Happen

Valor may cause network access indirectly when it instructs the host assistant
to use tools that are already present in the user's environment, such as:

- `gh` CLI for GitHub data
- Jira or Atlassian MCP tools
- calendar integrations
- web search for explicitly requested research

The exact behavior depends on the host assistant, installed plugins, and the
commands the user runs.

## Important Limitation

Valor does not control how your host assistant handles prompts, workspace
context, or tool calls.

If you use a hosted assistant or a hosted model provider, code snippets, ticket
details, or other context may be transmitted according to that platform's
policies. Valor cannot override those policies from inside this repo.

## Recommended Safe Usage

- Use separate workspaces for work and personal projects.
- Grant the minimum tokens and permissions needed for each tool.
- Avoid enabling integrations you do not want Valor to reference.
- Prefer local models or high-trust providers when handling sensitive material.
- Review tool approvals carefully before allowing networked operations.
- Keep confidential company frameworks in your local `~/.valor/` files, not in
  the public repo.

## Deleting Valor Data

To remove Valor's local data:

- delete `~/.valor/`
- remove installed commands/skills from `~/.claude/commands/`, `~/.codex/skills/`, or `~/.cursor/skills/`
- remove the installed Valor rule from `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, or `~/.cursor/rules/`

## Scope of the Privacy Promise

Valor aims to make the local trust boundary explicit and inspectable.

What Valor can promise:

- local storage by default
- no built-in telemetry in this repo
- inspectable prompt and storage logic

What Valor cannot promise on its own:

- that your host assistant is local-only
- that third-party plugins never send data externally
- that external model providers retain nothing

If you need a fully offline workflow, treat your assistant runtime, model
provider, and integration setup as part of the security review, not just Valor.
