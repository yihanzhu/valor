# Roadmap

This roadmap reflects the current public direction of Valor as a local-first,
developer-focused project.

## Guiding Constraints

- local-first by default
- inspectable behavior
- privacy-first trust model
- stdlib-only runtime where practical
- optional, explicit integrations instead of mandatory cloud services

## Phase 1: Local Core

**Status:** Complete

What shipped:

- local evidence store and CLI
- configurable career framework template
- six assistant workflows
- ambient coaching rules
- install flow for Claude Code, with Cursor kept as a legacy target

## Phase 2: Open-Source Hardening

**Status:** Complete

What shipped:

- integration portability model (state.json flags, auto-detection, graceful skip)
- contributor workflow (PR/issue templates, Ruff linter in CI)
- getting-started guide and integrations documentation
- expanded test coverage (87 -> 106 tests)

## Phase 3: Better Local Packaging

**Status:** Complete

What shipped:

- VERSION file and `--version` flag for traceability
- `--upgrade` flag (git pull + re-install) and version tracking in state.json
- Claude Code plugin packaging (plugin.json, marketplace.json, bin/, setup skill)
- command files renamed for plugin namespace (`/valor:briefing` etc.)
- evidence CLI enhancements: `search`, `export`, `status` subcommands
- improved `list` filtering: `--from`, `--to`, `--activity` date/type filters
- state_schema_version for forward-only state.json migrations
- architecture documentation (docs/architecture.md)
- `--clone` flag and curl one-liner for quick install
- test coverage: 106 -> 121 tests

## Phase 4: Agent-Native Extensions

**Status:** Complete

What shipped:

- Codex CLI support (`--target codex`) with AGENTS.md rule and skills adapter
- `.codex-plugin/plugin.json` for Codex plugin system
- three install targets: Claude Code (default), Codex CLI, Cursor (legacy)
- docs updated across README, architecture, and getting-started

## Phase 5: Evidence Outputs + Agent Quality

**Status:** Complete

What shipped:

- `export` subcommand filtering: `--days`, `--from/--to`, `--competency`
- weekly-summary CLI: `weekly-summary-save`, `weekly-summary-list`, `weekly-summary-get`
- feedback CLI: `feedback-add`, `feedback-stats`
- weekly reflection now persists structured output to weekly_summary table
- new `/valor-prep` command for 1:1 manager prep (7th agent command)
- standardized integration preamble across all commands
- wrap-up now records evidence (wrapup_completed entry)
- version bump to 0.3.0
- test coverage: 121 -> 133 tests

## Future Considerations

These are not committed but worth exploring:

- local model support for privacy-sensitive environments
- self-hosted or encrypted sync across machines
- cross-agent evidence federation (e.g., Cursor + Claude Code on same machine)
