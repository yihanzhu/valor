# Valor demo run-book

A ~20-minute walkthrough of all eleven Valor workflows plus ambient coaching,
driven entirely by the fictional demo profile in this directory. Everything on
screen is produced by Valor's real prompts and real CLI; only the work being
coached is invented.

Setup is in [README.md](README.md). Run it **the morning of the demo** — the
profile's dates are relative to the seed date, so a stale seed shows a stale
calendar.

**Say this once, up front:** "This is a seeded demo profile — fictional
engineer, fictional tickets. The coaching and the evidence are real output."
That one sentence buys you the whole demo without anyone wondering.

---

## Pre-flight (5 minutes before)

- [ ] Re-seed today: `python3 examples/demo/seed.py ~/valor-demo --force`
- [ ] Start the session: `HOME=~/valor-demo claude` — confirm it greets you with
      Valor context (levels L3 → L4), not a setup prompt
- [ ] Terminal font large enough to read at the back of the room
- [ ] **Pre-generate the review console** (Act 2, step 6) and leave the artifact
      URL open in a browser tab. It runs a multi-agent workflow over the diff and
      takes minutes — you do not want that on stage
- [ ] Have `examples/demo/fixtures/` closed. Nobody needs to see the seams

---

## Act 0 — What it is (1 min, no typing)

Open the site's hero: *the career layer that lives inside your coding agent*.
Then say the one thing the page can't show: **Valor has no UI**. There's no
dashboard to open, no form to fill. It's a rule and a set of commands installed
into the agent you already talk to, plus a local SQLite file.

Then switch to the terminal and stay there.

---

## Act 1 — A day (8 min)

### 1. Morning briefing · `/valor-briefing`

**Type:** `start my day`

Watch for, and name out loud:

- **Priorities ranked against this week's goals**, not just a ticket dump — the
  goals came out of the 1:1 doc silently, on a previous run
- **The dependency rule doing work**: #418 outranks new work because the platform
  team's migration is blocked on it
- **The verification gate**: the seeded claim that a message was "not sent"
  yesterday gets checked before it's re-raised, not carried on faith
- **A day plan fit to real gaps** — a deep block in the 11:30–14:00 stretch, the
  small review dropped in the fragmented slot, a breather after the sync, nothing
  before 09:30. Point out that it's *shown, not written*: `calendar_auto_write` is
  off in this profile
- **Project focus**: the demo rotates projects, so off-focus work is hidden
- **Coaching nudge** tied to a real L4 competency, not a generic tip

*If the briefing is thin:* the profile is seeded — say so, and check that
`~/.valor/demo/` exists.

### 2. Ambient coaching (no command)

**Type:** `the retry cap should be configurable, not hardcoded at 30s — make it read from env with 30 as the default`

There's nothing to run here — let the agent do the small task, then wait for the
footer. This is the part nothing else in the category does: **you didn't ask for
coaching and you didn't switch tools.** It classified the work, tied it to a
target-level competency, and recorded evidence silently.

Then show that last part:

```bash
python3 ~/.valor/evidence_cli.py list --limit 3
```

### 3. PR review coach · `/valor-pr-review`

**Type:** `help me review PR #418`

Point at the three things a linter won't tell you: **architecture** (does the
retry policy belong in this layer?), **blast radius**, and **the tone of your own
review comments**. Note that #418 is the PR the demo profile says *you* wrote —
so this is the "review it before Riley does" pass.

### 4. Design doc coach · `/valor-design-doc`

**Type:** `design doc for PROJ-231`

The refund double-apply ticket. Watch for options with trade-offs and — the part
people notice — **what it recommends explicitly punting**.

### 5. Evening wrap-up · `/valor-wrapup`

**Type:** `wrap up`

- Reconstructs the day from git activity and evidence
- **Captures meeting notes** from the day's calendar attachments into the evidence
  store — so 1:1 prep and the weekly reflection later use what actually happened
  in the room, not what you remember
- Writes a carry-forward file, **verifying each item against its source first**
- Names the honest gap: an execution day that didn't move the ownership gap

Show the artifact: `ls ~/.valor/carry-forward/`

---

## Act 2 — A week (6 min)

### 6. PR review console · `/valor-pr-console`

**Open the pre-generated artifact.** Say: "one command, from the diff, no hand-editing."

Then drive it: zoom **Context → Inside → Components → the real diff lines**, flip
**Before ⇄ After**, hit **▶ Play** to watch a request flow. Then start the quiz
and get one wrong on purpose — the point is the gate: **all correct or you're not
approval-ready**, and every answer was independently verified against the diff
before it was allowed into the quiz. Close with the honest caveat: it can't
approve for you, GitHub still does.

*If you must generate live:* start it at the top of Act 1 and come back to it here.

### 7. Project sync prep · `/valor-sync-prep`

**Type:** `sync prep`

Team-facing talk points for the checkout sync: progress since last sync,
decisions to land, open questions. Plain text, because it pastes into shared
notes that render markdown literally. Note the pairing: the briefing already
reserved the 30 minutes before the sync, and this fills it.

### 8. 1:1 prep · `/valor-prep`

**Type:** `prep for 1:1`

The one managers notice. Two things to name:

- It's drafted **in your own 1:1 doc's format** — it read the doc and matched it
- **Chronic blockers surface**: an item that's been stuck past the threshold gets
  escalated instead of quietly re-listed

### 9. Weekly reflection · `/valor-weekly`

**Type:** `reflect on my week`

Competency breakdown with a real gap: the profile has almost no
industry-knowledge signal, and the reflection says so instead of flattering you.

---

## Act 3 — A review cycle (4 min)

### 10. Performance reflection · `/valor-reflection`

**Type:** `half-year reflection`

The payoff for six months of ambient capture:

- **Impact themes**, clustered and mapped to competencies and company values
- **The coverage check**: it cross-checks git and past sessions for work you never
  logged. The profile has a merged PR (#397, retry budget metrics) with no
  evidence entry — watch it get caught
- **Claims phrased from recorded status and role**: the refund fix is
  `in_progress`, so it must not read as shipped
- **A confirm-before-you-submit list** instead of overclaiming — including one
  deliverable with no `role` recorded, where it asks whether you led or co-built

This is the slide to linger on: *this is why the daily capture matters.*

### 11. Upward feedback · `/valor-upward-feedback`

**Type:** `feedback about my manager`

Grounded in observed behavior from the seeded meeting notes — Sam pushing back on
the retry cap, suggesting the platform conversation, naming the L4 gap plainly,
and one commitment Sam made and hasn't delivered. Note what it does when evidence
is thin: it flags that, rather than inventing a pattern.

### 12. Setup · `/valor-setup`

Don't run it here — it would reconfigure the profile mid-demo. Show what it does
instead:

```bash
head -40 ~/.valor/career_framework.md
python3 ~/.valor/evidence_cli.py setup-status
```

Say: paste your company's ladder and it structures it; no ladder handy and it
offers three ready-made ones or generates one from your job title. If someone
wants to see the interview itself, run it after the demo against a second scratch
home — `HOME=~/valor-setup-demo` — so this profile survives.

---

## Close (2 min)

```bash
python3 ~/.valor/evidence_cli.py stats
python3 ~/.valor/evidence_cli.py export --days 7 --format markdown
```

Three sentences to land:

1. **It's all local.** One SQLite file, plain-text notes, no telemetry, no
   backend. `~/.valor` is the whole product surface.
2. **It's your framework, not ours.** Valor coaches against the ladder you paste
   in, which is why the nudges name your competencies.
3. **The install is one line and then you forget it.** Show the command, then
   `rm -rf ~/valor-demo` on the way out if you're on a shared machine.

---

## Question-time cheat sheet

| Question | Answer |
|---|---|
| "Does this send my code anywhere?" | Valor adds no telemetry and no backend. Your *host agent's* model calls are governed by that host — see `PRIVACY.md`. Say it plainly; don't oversell. |
| "What if I don't have Jira/GitHub?" | Every integration is optional and independently switchable; commands skip what's missing. This demo runs with all four **off**. |
| "Is it Claude-only?" | Claude Code, Codex CLI, and Cursor, one installer. The review console needs a host with workflow + artifact tooling. |
| "Who else can see my evidence?" | Nobody. There's no sharing feature. Export is a local file you choose to paste. |
| "Can it just watch my git history instead?" | That's the gap it exists to fill: commits miss debugging, design, alignment, and mentoring. Point at the reflection's impact themes — most of them aren't commits. |
| "How do I get it?" | `curl -fsSL …/install.sh | bash -s -- --clone`, then say "set up valor". |

## Timing at a glance

| Act | Content | Minutes |
|---|---|---|
| 0 | What it is | 1 |
| 1 | Briefing, ambient coaching, PR review, design doc, wrap-up | 8 |
| 2 | Review console, sync prep, 1:1 prep, weekly | 6 |
| 3 | Reflection, upward feedback, setup | 4 |
| — | Close | 2 |

**Short on time?** Keep Act 1 steps 1–2, Act 2 step 6, and Act 3 step 10. That
quartet — briefing, unprompted coaching, the review console, and the review draft
built from six months of captured evidence — is the whole argument in ten minutes.
