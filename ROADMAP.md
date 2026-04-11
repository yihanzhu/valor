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

**Status:** In progress

Focus areas:

- privacy and security documentation
- clearer public-facing README and project framing
- contributor workflow and CI
- tighter separation between local core and optional integrations
- improved docs around the trust boundary

## Phase 3: Better Local Packaging

**Status:** Planned

Possible work:

- more transparent local exports beyond SQLite
- improved workspace separation
- friendlier install and upgrade flows
- better local state introspection
- standalone local packaging beyond assistant-specific installation

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
