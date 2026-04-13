# ADR-001: install.sh as Primary Distribution, Plugins as Discovery Only

**Status:** Accepted
**Date:** 2026-04-13
**Context:** Valor 0.3.0, after completing Phase 4 (Codex CLI support) and Phase 5 (Evidence Outputs)

## Decision

`install.sh` is the primary and recommended distribution channel for Valor.
Plugin manifests (`.claude-plugin/`, `.codex-plugin/`) exist for marketplace
discoverability but are explicitly positioned as commands-only.

## Context

Valor's value comes from two layers:

1. **Agent commands** -- 7 discrete commands (briefing, pr-review, design-doc,
   weekly, tasks, wrapup, prep) that users invoke explicitly.
2. **Ambient coaching** -- an always-on layer that auto-triggers suggestions
   (morning/evening/Friday), classifies completed tasks, maps them to career
   competencies, generates coaching annotations, and records evidence.

Both Claude Code and Codex CLI offer plugin systems that can distribute
commands. We explored using plugins as a full distribution channel.

## Why plugins cannot deliver the full experience

Plugin commands activate when a user invokes them. Ambient coaching requires
instructions that load on *every* conversation, regardless of user intent.
The plugin system has no mechanism for "inject these instructions into every
conversation."

Specifically:

- **Post-task coaching** needs the ambient rule in `CLAUDE.md` (or `AGENTS.md`)
  to tell the agent to annotate responses with career coaching after meaningful
  tasks. Plugin instructions only load when a plugin command is called.
- **Evidence recording** happens as a side effect of normal coding work. Without
  always-on instructions, evidence only gets recorded during explicit Valor
  commands.
- **Auto-trigger suggestions** were initially thought to require plugins, but
  Claude Code's `SessionStart` hook (user-level, via `settings.json`) can
  deliver the same behavior. `install.sh` now writes this hook directly.

A `Stop` hook was considered for post-task coaching but rejected: it adds an
extra round-trip per response (hook fires, blocks stop, Claude gets another
turn to add coaching), increasing latency and cost with worse UX than the
inline approach via `CLAUDE.md` instructions.

## What the plugin does provide

- **Marketplace discovery** -- users searching for career coaching tools can
  find Valor and learn about it.
- **Command-only access** -- users who only want the 7 slash commands without
  ambient coaching can install the plugin. This is a valid but limited use case.
- **Auto-trigger hooks** -- the plugin includes a `SessionStart` hook that
  suggests briefings/wrap-ups. This is a bonus for plugin-only users.

## Consequences

- `install.sh` is the single recommended install path in all documentation.
- Plugin manifests stay in the repo but their descriptions direct users to
  `install.sh` for the full experience.
- Future contributors should not invest in making the plugin a full delivery
  channel unless the plugin system gains a mechanism for always-on instructions.
- The `SessionStart` hook lives in both the plugin (`hooks/hooks.json`) and the
  installer (`install.sh` writes to `~/.claude/settings.json`).

## Alternatives considered

1. **Remove plugins entirely** -- simpler, but loses marketplace discoverability.
   Decided against because the manifests are trivial to maintain.
2. **Stop hook for ambient coaching** -- technically possible but worse UX
   (extra round-trip, extra API calls, disjointed flow).
3. **Plugin agents** -- Claude Code plugins can define agents that Claude
   invokes "automatically based on task context." Less reliable than rule-based
   enforcement and still doesn't cover always-on coaching.
