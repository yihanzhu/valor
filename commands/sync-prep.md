# Valor Project Sync Prep

Generate talk points for an upcoming **project sync** — the recurring meeting
where you walk the team through your project's progress. The output is a short,
team-facing brief you **review, proof, and paste** into wherever that project's
notes/agenda live; it does **not** write to any doc (sync docs differ per
project). Run it ~30 min before the meeting, in the prep block Valor reserves.

## When to Use

Two ways in: (1) **manually** by the user (the triggers below), or (2)
**automatically** — when `project_focus.auto_sync_prep` is on (default), the
briefing schedules a one-off run of this command ~`pre_meeting_prep_minutes`
(default 30) before a `project_sync`.

- User says: "sync prep", "prep for my project sync", "prep my sync talk
  points", "prep for the [project] sync", or runs `/valor-sync-prep`
- Best ~30 min before a `project_sync` — late enough to include what you just
  finished, early enough to share before others join

This is **not** `/valor-prep` (that's the manager 1:1: portfolio-wide, drafted
into your 1:1 doc). This is **one project**, since its **last sync**, framed for
the **team**.

## 1. Identify the sync and its project

The sync you're prepping is normally the next `project_sync` on the calendar.
Resolve the focus:

```bash
python3 ~/.valor/focus.py resolve --syncs '[{"project":"...","date":"YYYY-MM-DD"}, ...]'
```

Use `current_project` (or, if the user named a specific sync, that meeting's
project). Note the **last sync date** for the project — the most recent past
sync in the rotation — that's the window for "what's new."

**No-op safeguard (for the scheduled path):** if there's **no `project_sync`
still upcoming today**, exit quietly and do nothing — this guards against a stale
trigger firing on a day with no sync, and (unlike a fixed "next hour" window) it
holds for whatever `pre_meeting_prep_minutes` lead time is configured. For the
manual path, if focus is off or `current_project` is empty, just ask the user
which project the sync is about.

## 2. Gather progress since the last sync

Pull what actually moved on **this project** since its last sync — not your whole
week (that's the 1:1's job). Use whichever integrations are on
(`context.integrations`):

- **Jira** — the project's tickets that changed status, completed, or are
  in-progress since the last sync.
- **GitHub** — PRs merged / opened on the project's repos since the last sync.
- **Evidence** — `evidence_cli.py export --days <since-last-sync>` for decisions
  and investigations already recorded for the project.

**Verify before you assert** (the same gate as the briefing): don't claim a PR
merged or a doc published unless it checks out. Surface only real progress.

## 3. Frame the talk points

Organize into a short, team-facing brief — what colleagues need to walk in
oriented:

- **Progress since last sync** — what got done / moved (one concrete line each).
- **Decisions / recommendations to land** — what you want the group to align on.
- **Open questions / asks** — what you need from the team to move forward.
- **Risks / blockers** — anything off-track or at risk, if any.

Keep it tight (a screen or less). Peer-framed and factual — a project update,
not a self-review. Skip any empty section.

## 4. Output for review (do NOT auto-write)

Print the talk points for the user to **proof and paste** into the project's
shared sync doc/agenda themselves. Do **not** write to any doc or send anything:
sync docs live in different places per project, and the user wants to read-proof
first. Close with a one-line offer, e.g. *"Want me to tighten any section or
reframe a point?"*

## Notes

- **Pairs with the prep block, and can auto-run.** The day plan reserves a 30-min
  block before each `project_sync` (`planning.pre_meeting_prep_minutes`), and —
  when `project_focus.auto_sync_prep` is true (default) — the briefing
  auto-schedules this command to run at the start of that block. Manual
  invocation still works any time.
- **Stay project-scoped.** Only the current project, only since its last sync.
  Don't fold in off-focus projects or career framing — that's `/valor-prep`.
- **Record evidence** only if the prep surfaced a real design decision or
  cross-team alignment (per the ambient coaching rules); skip it for a routine
  status pull.
