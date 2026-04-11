# Valor Vision

Valor is a local-first ambient career coach for developers.

The core idea is simple:

- developers already spend a meaningful part of the workday in assistant and
  agent conversations
- a lot of high-value engineering work never shows up clearly in commits alone
- career growth tools are more useful when they work with the user's real
  workflow instead of asking for extra manual bookkeeping

## The Problem

Performance reviews are often retrospective and recency-biased. Engineers end up
reconstructing months of work from memory, scattered notes, and merge history.

That misses a lot of important work:

- debugging and root-cause analysis
- design decisions and tradeoffs
- cross-team alignment
- mentoring and knowledge sharing
- operational ownership
- drafting, planning, and investigative work that happens before anything ships

## Why Developers First

Valor is intentionally aimed at developers before broader knowledge-worker use.

Developers already interact heavily with assistants, code review systems,
tickets, design docs, and other machine-readable artifacts. That makes it
possible to provide coaching in the flow of work instead of only during review
season.

## Core Thesis

The best version of Valor should feel closer to "Obsidian for career evidence
and coaching" than "another HR platform."

That implies a few non-negotiable properties:

- **local-first**: the user's raw data should remain on their machine by default
- **inspectable**: prompts, storage, and decision logic should be auditable
- **user-owned**: the user controls their framework, evidence, and exports
- **optional integrations**: external systems are useful, but not the center of
  trust

## What Makes Valor Different

Valor is not trying to be:

- a generic performance-management suite
- a manager dashboard
- a commit-only brag doc generator
- an HRIS add-on

The current direction is narrower and more developer-native:

- ambient coaching during daily assistant interactions
- local storage of career evidence and summaries
- mapping work to a user-supplied career framework
- prompts that help with reviews, design docs, prioritization, and reflection

## Current Shape of the Project

Today the repo is a working local core that provides:

- a local evidence store and CLI
- a configurable career framework template
- assistant commands for daily and weekly workflows
- ambient coaching rules that connect completed work to career signals

It currently targets Claude Code by default and Cursor as a legacy install path.

## Trust Boundary

The hardest product problem in Valor is trust, not prompt quality.

If Valor can see confidential code, internal tickets, planning notes, and daily
assistant conversations, then users need very strong reasons to believe:

- what is stored locally
- what can leave the machine
- what external tools are being used
- what is merely suggested by the repo versus enforced by the host assistant

That is why the local-first and inspectable design matters so much.

## Non-Goals for the Core Project

The open core should not require:

- a mandatory cloud account
- a central hosted data plane
- employer-managed access
- hidden telemetry

Optional hosted or team-oriented layers might exist in the future, but they are
not the identity of the core project.

## Future Directions

Promising directions that still fit the local-first model:

- stronger local exports and plain-text evidence views
- better workspace separation and trust controls
- standalone local packaging beyond prompt installation
- local daemon support for reminders and summaries
- optional local-model support
- optional self-hosted or encrypted sync for users who want it

The key constraint is that convenience features should not erase the trust
advantages of a local-first system.
