# Valor Performance Reflection

<!-- valor:integrations github=none jira=none calendar=none news=none -->

Turn the accumulated evidence log into an accurate, review-ready **self-reflection
draft** for a performance cycle (e.g. mid-year / end-year): impact themes mapped to
competencies and company values (and an AI-adoption tier **only if your career
framework defines one**) — plus a list of **uncertainties to confirm before you
submit**. Generate-only: you review, correct, and paste it into your review tool
yourself.

The point is accuracy, not cheerleading. Daily briefing/wrap-up prose is written in
an optimistic, forward-looking register ("shipped", "go-live", "prod-ready"); read
literally it **overclaims**. This command treats that prose as **claims to confirm**,
uses each entry's `status` and `role` to phrase precisely, and flags anything it
can't stand behind rather than asserting it.

## When to Use

- User says: "performance review", "half-year reflection", "self-reflection",
  "write my self-review", or runs `/valor-reflection`
- Around a review cycle (mid-year / end-year). No auto-suggestion — run on demand.
- This is **not** `/valor-weekly` (one week, competency counts, a 1:1 narrative) or
  `/valor-prep` (the manager 1:1). This is a **whole cycle**, framed as a self-review.

## 1. Define the cycle window

Establish one explicit date window and reuse it everywhere. Ask the user if it isn't
clear from the request:

- `cycle_start` / `cycle_end` (`YYYY-MM-DD`) — e.g. the half-year under review.

## 2. Pull the period's evidence

```bash
python3 ~/.valor/evidence_cli.py export --from <cycle_start> --to <cycle_end> --format json
```

Each entry carries `status` (end-state) and `role` (your attribution) when they were
recorded — §6 and §7 depend on them. Also load the career framework
(`~/.valor/career_framework.md`) for the competency ladder, the company values, and
any AI-adoption tiers:

```bash
python3 ~/.valor/evidence_cli.py framework-slice
```

## 3. Separate signal from noise

The log is dominated by process entries. **Drop** routine activities that aren't
deliverables — `morning_briefing_completed`, `wrapup_completed`,
`weekly_reflection_completed`, and similar — and keep the entries that represent real
work (features, investigations, designs, cross-team alignment, production fixes,
drafted communications).

## 4. Cluster into impact themes

Group the surviving entries into **2–3 impact themes** — the headline stories a
review wants, not a flat activity list. Keep, per theme, the entries that support it
(you'll need their `status`/`role` in §6–§7).

## 5. Map each theme to the framework

For each theme, using the framework slice:

- **Competency** — from the entries' `competency` tags (name the strongest one or two).
- **Company value** — which value the work best evidences.
- **AI-adoption tier** — where the work places you, if the framework defines tiers.

Write for a **skip-level reader**: expand project-internal jargon/acronyms so the
draft stands on its own.

## 6. Draft precisely — honor status and role

Write the draft (impact examples, growth areas, a value-by-value pass, and — **only
if the framework defines AI-adoption tiers** (§5) — an AI-adoption self-placement;
otherwise omit that dimension entirely, never infer one). Two hard rules, taken from
the fields on each entry:

- **`status` governs end-state claims.** Never describe something as "in production",
  "live", or "shipped" unless its `status` is `live` or `validated`. `in_progress` /
  `merged` / `deployed` → phrase as built / merged / rolling out, **not** done.
- **`role` governs attribution.** Phrase ownership by the recorded role
  (`led` / `built` / `co-built` / `contributed` / `advised` / `decided-by-other`).
  Don't claim you *built* what you only `advised` on — and don't hand your own
  `led`/`built` work to someone else.

## 7. Surface uncertainties to confirm (the headline)

This is what saves you from an overclaim in front of a skip-level reader. For every
deliverable in the draft, auto-generate the exact question a careful reviewer would
ask, and collect them into a **"Confirm before you submit"** list instead of guessing:

- **Status unknown** (empty / `in_progress` / `merged` / `deployed`): "Is *X* live
  now, or still pending rollout?"
- **Role ambiguous** (empty or shared): "Did you lead *X*, or co-build it? Who else
  owned it?"
- **Claim unverified**: any "shipped / published / sent" phrasing not backed by a
  known-done `status` → "Confirm *X* actually landed."

Blank `status`/`role` is expected on older entries — flag it, don't assume. (Entries
recorded from here on can carry `--status`/`--role`, so future cycles need fewer flags.)

## 8. Output for review (do NOT auto-write)

Print two blocks for the user to read, correct, and paste into their review tool:

1. **The draft** — impact themes, values, growth areas (and an AI-adoption
   placement only if the framework defines tiers).
2. **Confirm before you submit** — the flags from §7, each phrased as a question.

Because it's pasted into tools that render markdown literally, emit the draft as
**plain text — no `*`, `**`, `_`, or `#`** (a plain leading `- ` for a list item is
fine, `*` is not). Close with a one-line offer to revise once the user answers the
flags.

## 9. Record evidence (optional)

If the reflection produced a genuine synthesis worth keeping (per the ambient
coaching rules), record one entry — otherwise skip:

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity performance_reflection_completed \
  --competency autonomy_scope \
  --statement "Half-year reflection: [top impact theme], strongest in [competency]; [N] items flagged to confirm." \
  --agent valor-reflection
```

## Notes

- **Generate-only.** Never write to a review tool or send anything; the user proofs
  and pastes.
- **Accuracy over optimism.** When `status`/`role` are unknown, the correct output is
  a flag, not a confident claim.
- **Coverage is a future step.** This version reflects only what's in the evidence
  log. Cross-checking git / calendar / chat for *uncaptured* work is a planned
  follow-up; for now, if you recall work that isn't in the draft, add it yourself.
