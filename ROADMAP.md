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
- test coverage: 106 -> 120 tests

## Phase 4: Local Background Assistance

**Status:** Planned

Possible work:

- a local daemon for reminders and periodic summaries
- optional notification hooks that remain local-first
- scheduled reflections and briefings without needing to start a session first

## Phase 5: Optional Extensions

**Status:** Future

Possible work:

- local model support
- self-hosted or encrypted sync
- plugin adapters for more tools
- richer exports for promotion packets and review prep

These are extensions, not requirements for the core experience.
