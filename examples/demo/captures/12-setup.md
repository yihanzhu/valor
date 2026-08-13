id: setup
command: /valor-setup
phrase: set up valor
label: Setup
act: Setup
blurb: Paste your company's ladder, or start from one of the bundled examples. Runs once.
---
Setting up Valor. Three things: your career framework, your levels, and which integrations you have.

**1. Career framework**

Paste your company's career ladder — a Google Doc, a Confluence page, a wiki dump, whatever you have.
Formatting doesn't matter; I'll structure it into levels, competencies, and values.

No ladder handy? Four options:

    a) A generic software-engineering IC ladder (L3 -> L6)
    b) An engineering-manager ladder
    c) A growth framework with no formal levels, for companies that don't use them
    d) Generate one from your job title

    > b

Copied the engineering-manager ladder into `~/.valor/career_framework.md`. It's a starting point with
placeholder company values — edit it whenever, and re-run setup to reload.

    ✓ 4 levels found: M1, M2, M3, M4
    ✓ 5 competency axes
    ✓ 3 company values (placeholders — worth replacing with your real ones)

**2. Your levels**

Which are you now, and which are you working toward? The gap is what coaching aims at. The ceiling is
the level where I'll acknowledge behaviour without treating it as an expectation.

    > current M2, target M3

    ✓ current: M2 — Engineering Manager
    ✓ target:  M3 — Senior Engineering Manager
    ✓ ceiling: M4 — Director (inferred; say so if you'd rather it were M3)

**3. Integrations**

Checking what's already available in your environment:

    ✓ GitHub    — gh CLI authenticated
    ✓ Jira      — Atlassian tools present
    ✗ Calendar  — no connector found
    ✓ News      — web search available

    Which GitHub org should I watch? > example-org
    Which Jira project keys? > PROJ

Calendar is what powers the day plan and meeting-notes capture. Everything works without it; the
briefing just won't try to schedule your day. Enable it later by flipping one flag in `state.json`.

**Done.** Working hours are 09:00–18:00, so the morning briefing offers itself before 11:00 and the
wrap-up after 16:00 — say "start my day" or "wrap up" whenever you like instead.

Your framework, levels, and evidence all live in `~/.valor/`. Nothing leaves this machine.
