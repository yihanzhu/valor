# Valor Vision

Valor is a local-first, device-local career-growth layer for developers.
It lives inside the coding agents users already prefer, helps turn daily work
into visible growth, and keeps the core memory, evidence, and context on the
machine where that work happens.

## Core Thesis

The coding agent is where the work happens.
Valor is where that work becomes growth.

Valor is designed around a simple belief: developers should not have to
reconstruct their growth from memory, commits, and scattered notes after the
fact. The work already happens in conversations with coding agents, in
implementation sessions, design discussions, reviews, planning, and wrap-ups.

Because Valor lives inside that workflow, it can interpret the real context of
the work as it happens. That makes it more accurate and far lower-friction than
tools that depend on manual logging, retrospective summaries, or commit history
alone.

## The Developer Loop

Valor is built around the natural rhythm of developer work:

1. Start the day with a morning briefing.
2. Do the work with in-flow coaching.
3. Use focused skills for things like design docs and PR reviews.
4. End the day with a wrap-up and carry-forward context.
5. Reflect at the end of the week to improve intentionally.

So Valor is not just a set of commands, and not just a coach. It is a
continuous layer that helps developers plan, execute, interpret, remember, and
reflect.

## Product Principles

### 1. Agent-Integrated

Valor lives inside the coding agent the user already uses instead of asking
them to switch to a separate app or assistant.

### 2. Context-Native and Low-Friction

Because Valor is embedded in the workflow, it can capture and interpret work
more accurately without depending on manual tracking.

### 3. Tool-Portable

Users should be able to move across supported coding agents, such as Claude
Code and Codex, without resetting the Valor layer, as long as those tools share
the same local setup.

### 4. Local-First and Device-Local

Memory, evidence, framework, and sensitive context stay local to the machine
where the work happens by default.

### 5. Career-Aware

Valor does not just help finish tasks. It helps developers understand work
through the lens of growth, evidence, and promotion readiness.

## Continuity Model

Valor should provide continuity across:

- conversations
- sessions
- projects
- supported coding agents on the same machine or trust domain

That means a user can switch from one supported agent to another and still have
a coherent Valor experience if they are using the same local Valor setup.

But Valor should not promise silent continuity across every device everywhere.
A work laptop and a personal laptop are separate trust domains by default. That
separation is intentional.

## Privacy and Trust Model

Privacy and security are first-order product requirements for Valor.

All sensitive memory, evidence, framework data, and local context should stay
on the machine where the work happens unless the user explicitly moves it
elsewhere.

Work captured on a work laptop should remain on the work laptop by default.
A personal laptop should remain separate by default. Valor should not silently
sync or centralize sensitive work context across devices.

This makes Valor more private, but it also means the user carries
responsibility for device security and backup hygiene. Because the data is
local and user-controlled, poor local data management can lead to data loss.
Valor should be explicit about that tradeoff rather than hiding it.

So the trust promise is:

- the core stays local by default
- the trust boundary is explicit
- the user remains in control
- the user also remains responsible for securing and backing up that local data

Valor should also be honest that the surrounding agent environment still
matters. If a host coding agent sends prompts or workspace context to a hosted
model provider, that behavior is governed outside Valor itself. Valor’s job is
to make the local core and its own trust boundary inspectable and clear.

## What Valor Is Not

Valor is not:

- a generic AI career coach
- a manual brag-doc tool
- a performance-management suite
- an HR platform
- a manager dashboard
- a commit-only brag doc generator
- a mandatory cloud product
- a hidden employer-facing system

It should feel much closer to a local, inspectable evidence and coaching layer
for developer growth than to another SaaS career platform.

## Product Outcome

Valor helps developers make daily work legible as career growth.

Not by asking them to do more administrative work, but by living inside the
work they are already doing.

That is the point:

- less manual tracking
- more accurate context
- stronger continuity
- clearer reflection
- better growth awareness over time

## Messaging Implication

If this vision is reflected in the homepage and public docs, they should make
these ideas clear:

- Valor lives inside the coding agent the user already uses.
- It helps plan, coach, wrap up, and reflect.
- It captures work more accurately because it sees the workflow itself.
- It stays consistent across supported tools sharing the same local setup.
- Core memory and evidence stay local to the device where the work happens.
- Privacy and trust are central, with an explicit boundary.

## Short Version

Valor is a local-first, device-local career-growth layer that lives inside the
coding agents developers already use, turning daily work into visible growth
without forcing users to manually reconstruct what happened later.
