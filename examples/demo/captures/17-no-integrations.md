id: no-integrations
command: (question)
phrase: what if I don't have Jira?
label: Ask what's required
act: Setup
blurb: Every integration is optional and independently switchable. Sections skip; nothing breaks.
---
Then the briefing skips the ticket section and works from everything else — your PR queue, your
calendar, yesterday's carry-forward, and your evidence history. Nothing errors, and nothing nags you
about the missing one.

That's how all four work. They're independent flags in `~/.valor/state.json`:

    "integrations": {
      "github": true,
      "jira": false,
      "calendar": true,
      "news": true
    }

What you lose per integration, concretely:

- **No GitHub** — no review queue and no PR state, so the wrap-up leans on git history instead. The PR
  review coach and the review console need it; they'll tell you so and stop rather than guess.
- **No Jira** — no ticket context and no backlog pickups. If your team tracks work somewhere else,
  paste a list and it'll rank that instead.
- **No calendar** — no day plan, no prep blocks, no meeting-notes capture. Priorities still come out
  ranked; they just aren't fitted to a schedule.
- **No news** — the briefing loses its industry section. That one is genuinely cosmetic.

What never depends on an integration: the career framework, the evidence store, ambient coaching, the
weekly reflection, the performance reflection, and the upward feedback. Those read your local history,
so they work on a laptop with nothing connected at all.

Worth knowing for the opposite reason: this demo profile runs with **all four off**. Everything you've
seen in this session came from local state and fixture files.
