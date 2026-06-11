
# Valor Morning Briefing

<!-- valor:integrations github=optional jira=optional calendar=optional news=optional -->

Generate a comprehensive morning briefing that cross-references the user's work
items, surfaces opportunities for career growth, and provides relevant news.

## Integration Check

Use `context.integrations` from the session-start context (already loaded).
For any integration set to `false`, skip all sections that depend on it
entirely -- do not probe for the tool and do not print a skip message.

| Integration | Sections skipped when `false` |
|-------------|-------------------------------|
| `jira`      | Jira Tickets (1) |
| `github`    | GitHub PRs (2), Monday catch-up PR queries |
| `calendar`  | Calendar (3) |
| `news`      | News (4) |

Career Coaching (5) and Evidence are always available (local).

## Data Gathering

Gather data from all enabled sources in parallel using direct tool calls
(Shell, WebSearch, etc.). Do not delegate data gathering to Task subagents --
the commands are known, fast, and do not require discovery or exploration.

If an enabled source fails at runtime (e.g. `gh` not authenticated), note it
once and suggest the user either fix the tool or set the integration to `false`
in state.json.

### 1. Jira Tickets

**Preferred: Atlassian MCP**

Check if Atlassian MCP tools are available by looking in the MCP tools directory.
If `jira_search_issues` (or similar) exists, use it with these JQL queries:

- Assigned to current user, status in (In Progress, To Do, Blocked, In Review):
  `assignee = currentUser() AND status IN ("In Progress", "To Do", "Blocked", "In Review") ORDER BY status, updated DESC`
- Recently updated tickets the user is watching:
  `watcher = currentUser() AND updated >= -2d ORDER BY updated DESC`

**Fallback: Jira slash commands**

If Atlassian MCP is not available, check for any
Jira-related slash command (look for commands matching `*jira*`). If found,
read and use it to search for tickets.

**If nothing is available:** Skip the Jira section. If `integrations.jira` is
`true`, note: "Jira tools not found -- install an Atlassian/Jira plugin, or
set `integrations.jira` to `false` in `~/.valor/state.json`."

### 2. GitHub PRs

Use `gh` CLI via the Bash tool. Prefer `gh search prs` over `gh pr list`
because it works globally (no git repo context required):

```bash
# PRs requesting your review
gh search prs --review-requested=@me --state=open --json number,title,author,createdAt,url,repository --limit 20

# Your open PRs
gh search prs --author=@me --state=open --json number,title,createdAt,url,repository --limit 20
```

If `gh` is not authenticated, skip and note: "GitHub: `gh auth login` needed,
or set `integrations.github` to `false` in `~/.valor/state.json`."

For cross-team detection: if a PR's repository or author is outside the user's
typical scope (based on evidence store history), flag it as "cross-team."

### 3. Calendar

**Check for calendar slash commands:** Check for any Google
Calendar or calendar-related slash command (look for commands matching
`*google*` or `*calendar*`). If found, read and use it to fetch today's events.

**If not available:** Skip. If `integrations.calendar` is `true`, note:
"Calendar tools not found -- install a Google Calendar plugin, or set
`integrations.calendar` to `false` in `~/.valor/state.json`."

**RSVP status (mandatory):** After fetching the event list, retrieve full
details for each event (including attendee response statuses). For each event:

1. **Check the user's own RSVP** (`responseStatus` where `self: true`).
   Show status next to each event: *accepted*, *tentative*, *needsAction*
   (no RSVP), or *declined*.
2. **Filter out declined events.** If the user has declined, show it with
   strikethrough (~~event~~) rather than as an active commitment.
3. **Check other attendees for small meetings** (<=5 attendees). If a key
   attendee has declined, note it -- e.g., "Alice: declined". This prevents
   prepping for meetings that won't happen.
4. **Distinguish today vs. next-week preview.** Only today's accepted/tentative
   events affect priority suggestions. Next-week events are informational.

### 4. News

Use the WebSearch tool to search for **general** current news. Always
include the current date in search queries to anchor results.

**Coverage window:** The news section covers a continuous timeline from
the last briefing to now -- no gaps, no overlaps.

Use `context.briefing_meta.news_window_start` (ISO 8601 timestamp from the
session-start context). The coverage window is:

  `[news_window_start, now)`

For example, if last briefing was Tuesday 10:00 AM and this briefing is
Wednesday 9:00 AM, cover news published between Tuesday 10 AM and
Wednesday 9 AM.

Translate the window into search terms:

- **Same-day re-run** (< 12 hours): `"[topic] news today [Month Day Year]"`
- **Next-day** (12-36 hours): `"[topic] news today [Month Day Year]"`
- **Weekend gap** (2-3 days): `"[topic] news this week [Month Year]"`
- **Extended absence** (4+ days): `"[topic] news past week [Month Year]"`
  and select more headlines (4-5 per category).

Always search for **broad, general topics** -- never narrow the search
query to the user's work areas:

- `"AI ML research news [window] [date]"` -- general AI/ML
- `"tech industry news [window] [date]"` -- general tech
- `"world news headlines [window] [date]"` -- general world

**Work area relevance annotations:** After collecting headlines, check if
any naturally overlap with the user's `user_work_areas` from state.json.
If a headline is relevant, add a brief inline note explaining the
connection. Do NOT force relevance -- only annotate when there is a genuine
match. Most headlines will have no annotation and that is fine.

**Recency filter (mandatory):** Only include articles published within
the coverage window. Discard anything published before
`last_briefing_timestamp`, even if highly relevant. If a result has no
clear publication date, use WebFetch to check the article page. If still
unclear, skip it.

Select 2-3 headlines per category. For AI/ML news, add a brief note on
relevance to the user's work if applicable.

**Source URLs:** Every news headline must be plain text, with the source URL on
an indented line below. The link must point to the **specific article** — never a
homepage, section, topic, or daily-roundup/aggregator page (e.g. `site.com/`,
`site.com/topic/ai`, or a "news briefs for [date]" roundup). Those drop the reader
into dozens of unrelated items — the #1 complaint about this section. Prefer the
article permalink WebSearch returns; if a result only yields a hub/section page,
`WebFetch` it and cite the specific story's link instead. If a headline has no
specific-article URL, omit it rather than linking a hub or showing it unsourced.

### 5. Career Coaching

**Check if evidence store exists** at `~/.valor/evidence.sqlite`.

If it exists, query it using the evidence CLI:
```bash
python3 ~/.valor/evidence_cli.py stats
```

Use these counts to identify:
- Strongest competency area (highest count)
- Gap areas (lowest count or zero)
- Specific opportunities tied to today's work items

**If evidence store doesn't exist or is empty:** Skip the coaching section
entirely. Don't show empty placeholders. The section will appear naturally
after a few briefings accumulate evidence.

**Competency reference** (from `valor/src/evidence_cli.py`):
- Subject Matter (`subject_matter`): technical designs, clean code, ML concepts
- Industry Knowledge (`industry_knowledge`): awareness of tools, methods, algorithms
- Collaboration (`collaboration`): cross-team alignment, task identification
- Autonomy & Scope (`autonomy_scope`): independent execution, PR reviews beyond own scope, design docs
- Leadership (`leadership`): go-to expert, design decisions, identifying improvements

**Ground every suggestion — no bare-metric nudges.** A low competency count is a
signal to *look*, not a license to manufacture a task. Before surfacing a
knowledge-sharing action (publish a write-up / 1-pager / doc), require **precedent
or an explicit reason**, and cite it:
- Does Confluence show your team or the parent epic documenting similar work?
  (search it — don't assume.)
- Does the career framework name this behavior for the target level?
- Is there a finished artifact actually ready to share?

If you can cite ≥1, surface it **with that evidence** (e.g. "the epic's sibling
tickets all have Confluence write-ups; yours is the gap"). If you can't, **don't
surface it** — a low metric alone is not a to-do. Same bar for Suggested
Priorities: each carries its grounded *why*, never a bare number.

### Coaching Tone Evolution

Use `context.briefing_meta.tone_tier` (pre-computed from briefing count):

- **onboarding:** Explain what each competency means and why the suggested
  action matters. E.g., "Cross-team PR reviews build Leadership visibility --
  senior engineers are expected to review beyond their direct scope."
- **developing:** Concise nudges with data. E.g., "Cross-team review
  ratio: 10% (target: 25%). Sarah's #892 is a good candidate."
- **established:** Data only. E.g., "Cross-team: 10/25%. #892 available."

### 5.5 Project Focus (filter to the current project — run before Work Context and Priorities)

If `context.project_focus.enabled` is `false` (the default), skip this and
surface all projects as usual. When it's on, the user works **one project at a
time** and has deliberately deferred the others for a later cycle — mixing in
deferred work is noise, so resolve the current focus and filter to it.

Resolve the focus:

- **meeting_derived** (`context.project_focus.mode`): the focus follows a
  recurring per-project sync meeting (you work on whichever project's sync is
  next). Look at the **upcoming calendar** (next ~3 weeks), match event titles
  against the configured sync labels (`python3 ~/.valor/focus.py config` shows
  them — each maps a title fragment to a project), build the dated sync list,
  then:
  ```bash
  python3 ~/.valor/focus.py resolve --syncs '[{"project":"...","date":"YYYY-MM-DD"}, ...]'
  ```
- **manual**: `focus.py resolve` returns the user's set `current_project`.

Apply the result:

- **`current_project` is empty** → focus couldn't be determined; **fail open**
  (don't filter — surface everything). Never hide every project on a misconfig.
- Otherwise, **classify each candidate ticket/PR by reading it** (epic /
  component / labels / content — not a key prefix, since two projects can share a
  prefix) and **keep only items belonging to `current_project`.** Off-focus items
  are **hidden entirely** — not shown under a "later" heading — across Work
  Context, PR Situation, Suggested Priorities, and the Day Plan. A PR that only
  needs your approval still counts as off-focus: a review is a focus session, not
  a click, and the user has asked to hold that boundary.
- **`transition_today` is true** (the focus just flipped — today is the first working day after a sync):
  lead Suggested Priorities with a one-time hand-off line, e.g. *"Focus shifts to
  [current_project] this cycle; [next_project] resumes after its sync on
  [next_sync_date]."* Outside the transition, do not preview the off-focus project
  at all.

This is cheap: reuse the §3 calendar read + one `focus.py` call.

**Project & meeting intelligence (every briefing).** Reconcile your recurring
meetings against the **catalog** (each meeting categorized; `focus.py config`
shows the current one). This is a **daily drift-check** — known meetings stay
silent, only genuinely new ones surface — so there's no periodic gate:

1. Build the list of your **current recurring meeting titles** (scan **~3–4
   weeks** so biweeklies are caught; recurring only — has a `recurringEventId`;
   dedupe by title), then:
   ```bash
   python3 ~/.valor/focus.py catalog-diff --current '["Title A", "Title B", ...]'
   ```
2. **Categorize the `new` meetings (and ALL on a `seed`) from the signals, not the
   name.** Before deciding, use the signals **already in the calendar payload (all
   free — no fetch)**: the **description**, the **attendees** (same recurring small
   group → standup; exactly two → 1:1; broad invite → social), the **cadence +
   duration** (short + frequent → standup; monthly → demo/huddle), and the
   **attachment titles** ("…Project Plan" → project_sync; "…Agenda/Notes" → a
   working meeting). Also honor known **team names** from memory — a team's sync is
   a `standup`, not a `project_sync`. Categories: `1:1` / `focus` / `personal` /
   `standup` / `project_sync` / `team_planning` / `social` / `demo_huddle` /
   `external` / `other`. **Only if the free signals still don't resolve it** (or you
   can't tell team-vs-project) spend a content fetch: open an attached doc →
   Confluence (the project/topic) → Slack (recent context, e.g. a project you were
   just onboarded to). For a `project_sync`, record which **project**. On a `seed`,
   after categorizing, list them and flag any you're **unsure** about for a
   one-line confirm — catch misclassifications upfront, not weeks later. **Tag how
   you decided each** — `source: "signals"` (the free payload was enough) or
   `source: "fetch"` (you had to open a doc / Confluence / Slack) — and pass it
   through to `catalog-sync`. When any meeting needed a fetch, add a one-line note
   (*"opened 'X''s doc to classify it as project_sync"*); those mark where the
   signal heuristic is weak and worth revisiting over time.
3. **Surface, don't swallow — but only once.** A `project_sync` whose project is
   **neither in your focus mapping (`project_focus.syncs`) nor in
   `project_focus.parked_projects`** is a candidate new project — pin a
   top-of-briefing **Heads up**: *"'X' looks like a new project (Y, per its
   docs/Slack) — add it to your rotation?"* On confirm, append `{project, match}`
   to `syncs`; **if the user declines or defers, append the project to
   `parked_projects`** (via `state-set` on the whole `project_focus` block) so the
   *daily* check never re-asks — a parked project (one you joined but set aside)
   must not nag every morning. A `gone` project_sync prompts *"drop project Y?"*.
   Do this **even on a `seed`** (cold start): categorize everything, then flag the
   unmapped, **unparked** project_syncs — don't silently absorb a third project.
4. Write the categorized catalog:
   ```bash
   python3 ~/.valor/focus.py catalog-sync --entries '[{"title":"...","category":"project_sync","project":"Y"}, ...]'
   ```

### 6. Verification Gate (anti-phantom — run before Work Context and Priorities)

Yesterday's `today_priorities` (from state) and the carry-forward file are
**claims, not facts**. The phantom-propagation bug is the briefing re-asserting
"PROJ-42 1-pager unposted (week 14)" — or planning a calendar block around a
message that was sent yesterday — on a guess nobody ever checked.

**Your worklist already arrived: `context.claims`** (loaded at session start).
Do not re-derive claims from carry-forward prose — the runtime enumerated every
open claim for you. Process it:

1. `context.claims.stale_needs_check` — run each entry's embedded `lookup` with
   the matching tool (Atlassian/Slack/Drive MCP; `github_pr` entries are usually
   auto-resolved already), then
   `verify.py record --type <T> --id "<ID>" --result <resolved|unresolved|unverified>`.
   **resolved** → done: drop it from priorities and, if it closes a streak,
   record the completion. **unresolved** → surface with the real `day_count`.
2. `context.claims.unverifiable` — confirm-only claims: ask the user
   ("confirm or drop?"). **Skip entries marked `parked`** — they've gone
   unanswered 3+ mornings; the weekly owns them now.
3. `context.claims.unstamped_assertions` — claim-shaped lines in the
   carry-forward with no registered claim behind them (a bypassed or hand-edited
   wrap-up). Tell the user in one line, register the real ones
   (`verify.py register`), and treat their assertions as unverified until checked.

**Default-deny:** an artifact claim may appear in Work Context, Career Focus, or
Suggested Priorities **only with a fresh verdict from this run's gate**
(`fresh`, or just recorded). Anything else — unverified, never-checked,
confirm-only, unstamped — goes under "Needs Confirmation" as
"unverified — confirm or drop?", never as a numbered priority, never with an
advanced "week N / Nd" figure. Doing nothing must be the safe path.

After processing, print the gate summary line under Suggested Priorities:
`Gate: K claims — R resolved · U unresolved · V unverified`.

- If `context.verification.enabled` is `false`, skip this step.
- If `context.claims` is missing (older runtime), fall back to the per-claim
  protocol in `~/.valor/utilities.md` ("Verification Gate"):
  `verify.py check --type <TYPE> --id "<ID>"` for each carried artifact claim.

**Don't manufacture downstream tasks.** A "publish / write up / document X" item
is a real priority only once the upstream work it describes has actually reached
a publishable stage (the ticket is resolved, or a finished draft exists — confirm
it, don't assume). Until then, keep it as a *coaching nudge* ("when X lands, a
short write-up is strong industry_knowledge evidence"), never a numbered priority
or a carry-forward claim. Surfacing the write-up before the work is done is what
turns an unfinished investigation into a recurring "publish the 1-pager" ghost.
When you do record a claim, identify it by its **stable id** (ticket key, PR
number, doc title) — not a prose phrasing that drifts day to day — so the same
item stays one claim instead of fragmenting into near-duplicates.

### 6.5 Prioritize against the week's goals + dependencies (before the Day Plan)

Runs after focus (§5.5) and the gate (§6), before the Day Plan (§7). The candidate
todos are already focus-filtered and verified; this step decides their **order** so
the plan schedules the *right* work — not just the most recently-updated ticket
(the failure mode: a downstream "In Progress" task outranking the week's actual
goal). Read the inputs from the session-start context: `context.prioritization`
(`week_goals` — this week's ordered goals; `week_goals_stale`; `week_start_current`
— the authoritative ISO-Monday) and `context.standing_rules` (durable
sequencing/priority corrections, e.g. *"READ pipeline waits until WRITE is in
prod"*; a separate top-level field).

**Refresh goals when stale — silently, never ask.** If `week_goals_stale` is true
(new week) or `week_goals` is empty, and a docs reader is available and
`one_on_one.doc` is set, **read the 1:1 doc** (the same capability `/valor-prep`
uses) and extract this week's goals *by meaning* — the short list of what the user
said they're driving this week (format varies per person; don't assume a section).
The 1:1 *meeting's* captured notes (`activity: meeting_notes`) are a secondary
cross-check on what was actually agreed. Store and move on — set `week_start` to
`context.prioritization.week_start_current` **verbatim** (don't compute it yourself,
or the stale check will never match):
```bash
python3 ~/.valor/evidence_cli.py state-set prioritization \
  '{"week_goals": ["..."], "week_start": "<context.prioritization.week_start_current>", "goals_source": "one_on_one_doc"}'
```
This writes only the goals block; `standing_rules` live in their own key and are
untouched here. No doc/reader available → keep the cached goals (or none) and rank
without goal weighting. Never block, never ask to confirm.

**Rank the candidate todos**, in this order:
1. **Dependencies first (hard rule, not a tie-breaker).** Apply `standing_rules`: a
   todo blocked behind unfinished upstream is **held** — listed under "Held
   (blocked)", *never* as a numbered priority — until its blocker is done.
2. **Goal alignment.** A todo that advances or unblocks a `week_goal` outranks one
   that doesn't.
3. **Closeness-to-done / unblocks-others**, then **staleness** (the existing
   tie-breakers).

Show the **why** on each priority line ("advances week goal: <goal>"; "unblocks
<goal>") so a wrong call is obvious at a glance and the user can correct it in one
line. If the in-progress load clearly exceeds a week, add the one-line over-commit
heads-up (a nudge, not estimation math).

**Make corrections stick.** When the user corrects the order ("READ should wait for
WRITE in prod"; "X is this week's focus, not Y"), append it to the `standing_rules`
key so the next briefing honors it automatically — they shouldn't re-correct the
same thing weekly. Re-emit the existing rules from `context.standing_rules` plus the
new one (`state-set` replaces the whole list — never drop an existing rule):
```bash
python3 ~/.valor/evidence_cli.py state-set standing_rules \
  '[<existing rules from context.standing_rules>, "READ pipeline waits until WRITE is in prod"]'
```
Keep rules short and stable; if a correction contradicts an existing rule, replace
that rule rather than stacking a conflicting one. `standing_rules` and `week_goals`
are user-visible state — the user can ask to see or prune them anytime.

**Spare capacity → backlog pickups.** *Only* when the day plan is genuinely light
(open windows, or ≤2 real priorities), surface 1–2 *backlog* pickups so the user can
proactively grab high-impact work — never pad a full day with them. Pull from the
backlog, gated on the integration:
- **Jira** (`integrations.jira`): unassigned, stale (>2w), or High/Highest-priority
  tickets in `context.jira_projects`.
- **GitHub** (`integrations.github`): open PRs in your domain worth picking up —
  **skip any PR already listed under PR Situation (§2)** so a review-requested PR
  appears once, not twice (say "review PR repo#N" to start a coached review).

Rank them by the **same lens** as priorities: advances a `week_goal`, fills a
competency **gap** (from §5's stats — e.g. a low `industry_knowledge` or `leadership`
count), or is a cross-team / design task (stronger career signal), plus Jira
urgency/staleness. Surface under "Spare capacity" with a one-line *why*. If the user
picks one up, record it so the proactivity counts as evidence:
```bash
python3 ~/.valor/evidence_cli.py add --activity task_identified --competency <gap> \
  --statement "Proactively picked up <KEY>: <title>" --agent valor-morning-briefing
```

## Briefing Format

Present the full briefing in this structure. Use markdown formatting.
Cross-reference items across sections (link tickets to meetings, PRs to tickets).

```
## Valor Morning Briefing -- [Day], [Date]

[📌 **Heads up:** rare, high-signal one-time alerts — shown only when present and
pinned above everything else so they survive a news-only skim. E.g. a possible
new/dropped project from §5.5's drift check. Omit this line entirely when there's
nothing.]

### Work Context
- [Ticket ID]: [Title] -- *[Status]* ([days in status])
  [Cross-reference if this ticket relates to a meeting, PR, or blocker resolution]
  [Career coaching annotation if applicable]
- ...

### PR Situation
**Awaiting your review:**
- #[num]: [title] (from [author], [age])
  [Flag if cross-team] [Coaching annotation if applicable]

**Your open PRs:**
- #[num]: [title] -- [approvals], [comments], [CI status]
  [Nudge if action needed, e.g. "2 unresolved comments from Mike"]

### Today's Calendar
- [time] -- [meeting] ([duration]) -- *[your RSVP status]*
  [Prep suggestion if related to a ticket or PR]
- ~~[time] -- [meeting]~~ *declined* [or: key attendee declined]

### News

**AI/ML**
- headline -- [1-sentence relevance note if applicable]
  url

**Tech Industry**
- headline
  url

**World**
- headline
  url

### Career Focus
[Only show if evidence store has data]
- Strongest area: [competency] ([count] entries)
- Gap: [competency] ([count] entries)
- Today's opportunities:
  1. [specific action tied to today's work]
  2. [specific action]

### Suggested Priorities
[Ranked by the §6.5 pass — week goals + dependencies first. Each line shows *why*.]
1. [action] -- [why first, e.g. "advances week goal: <goal>" or "unblocks <goal>"]
2. [action] -- [why]
3. ...

[**Held (blocked):** [item] — behind [unfinished upstream], per a standing rule;
not surfaced as actionable until its blocker is done. Only if something is held.]
[**Heads-up:** this looks like more than a week's work — consider deferring
[item(s)]. Only when clearly over-committed; no estimation math, just a nudge.]
[**Spare capacity (only if the day is light):** 1–2 backlog pickups — [KEY/PR] [why:
gap/goal/team-need]. Omit unless there's real slack.]

[Carried artifact claims appear here only after passing the §6 gate. Verified
resolved items are dropped (or shown as just-completed); unconfirmable ones are
listed under a short "Needs Confirmation" note as "unverified — confirm or
drop?", never as numbered priorities with a day count.]

*Gate: [K] claims — [R] resolved · [U] unresolved · [V] unverified*
[Mandatory whenever any artifact claim was processed — it makes a skipped
gate visible at a glance.]

### Day Plan
[Time-blocked schedule from the §7 day-planning pass. Omit if calendar is off.]
- [HH:MM]–[HH:MM] — [priority] *(deep)*
- [HH:MM]–[HH:MM] — [priority] *(fragmented)*
[**Open windows:** [HH:MM]–[HH:MM] (Nm)[, …] — free slots for a quick win or overflow (from plan.py `open_windows`); if any]
[**Push to next deep block:** [unassigned deep_only items], if any]
[*Calendar: N events written/updated* — only if auto-write ran]
```

## Day Plan & Calendar (§7 — after priorities)

Turn the ranked priorities into a time-blocked plan fit to today's calendar,
and (optionally) write the blocks back as events so the user sees their to-dos
without re-asking. Skip this whole section if `context.integrations.calendar`
is `false`.

Follow the full protocol in `~/.valor/utilities.md` ("Day Planning & Calendar
Write"). In short:

1. Reuse the calendar you already fetched (§3); **drop declined — plus anything
   you marked *tentative/maybe* or are only an *optional* attendee on; those are
   free to schedule over, not busy.** **Always fit against the real calendar —
   never pass an empty event list.** Accepted meetings *and* personal holds (lunch,
   OOO, "busy" blocks) stay busy; a task placed over one is always a bug. If the
   user says the day is "open" or there's "nothing on the calendar," read that as
   **no hard syncs to plan around — not as an empty day**: still pass the accepted
   events + holds and fill only the genuine gaps. Build events with each event's
   **`type`**
   (`default`/`focusTime`/`outOfOffice`/`workingLocation`)
   so plan.py leaves focus-time free for deep work and blocks only real meetings
   + OOO. Mark **real meetings** so plan.py adds a breather after them: set
   **`is_meeting: true`** for collaborative meetings (or pass **`attendees`** and
   plan.py treats > 1 as a meeting). Lunch / personal holds / OOO are not meetings
   and get no break. **Flag prep-worthy meetings** — those categorized
   `project_sync` or `external` in the catalog — with **`prep: true`** plus their
   **`summary`**; plan.py reserves a prep block (default 30 min) immediately before
   each. You only *attend* standups / demos / planning, so those get no prep. If
   the calendar tool exposes the user's working hours, pass
   `--workday-start/--workday-end`; otherwise plan.py uses `state.planning`.
2. Build the **post-gate** priorities as `{"text", "est_minutes"}` objects. A
   task built on an artifact claim enters this list **only if the §6 gate gave
   that claim a fresh `unresolved` verdict this run** — never one demoted to
   "unverified", never one whose claim went unchecked (that's how a calendar
   block got planned around an already-sent message). **Estimate each task's
   duration from its nature** — a publish/post is ~15 min, a PR review ~30–45, a
   pipeline/implementation change is a multi-hour deep block, not 45 min. Lean
   **generous** (better to finish early than overflow). Then fit to the day's gaps:
   ```bash
   python3 ~/.valor/plan.py fit --events "$EVENTS" --priorities "$PRIORITIES"
   ```
   Render `blocks` **exactly as plan.py returns them** — its times, in order;
   don't re-time, merge, or improvise the schedule — and never invent a block for
   a task plan.py left `unassigned`. plan.py won't start tasks before
   `workday_start + morning_buffer_minutes` (your AM ritual) and **prefers
   focus-time blocks for deep work** (that's what they're for); a short task that
   only fits a small window now lands there instead of being pushed. Surface
   `unassigned` `deep_only` items as "push to your next deep block". plan.py also
   returns **`open_windows`** (free slots ≥15 min left after assignment, including
   the leftover of a partly-used gap — render them as **"Open windows: …"** quick-
   win / overflow slots so short free gaps aren't invisible), **`prep_blocks`** (a
   prep slot before each prep-worthy meeting — render them in the plan alongside
   task blocks) and **`prep_unassigned`** (a prep-worthy meeting with no free slot
   before it — surface as *"no prep time before X today — make room, or prep the
   day before"*).
3. **Calendar write** — only if `context.planning.calendar_auto_write` is `true`
   AND a writer is available. These are personal to-dos, so write them
   **private**: prefer a **Google Task** per block (private by nature) if a
   task-create tool exists; otherwise a **private** calendar event
   (`visibility: private` + `transparency: transparent`/free) so the title is
   hidden from others and you're not shown busy. **Reminders are a known
   limitation:** the calendar MCP writer can't suppress them — passing
   `overrideReminders: []` is a no-op (the event keeps `useDefault: true` and
   inherits the calendar's default popup), so expect Valor blocks to ping you at
   the calendar's default. Only a direct Google Calendar API call
   (`reminders: {useDefault: false, overrides: []}`) can zero it, where that path
   is available. **Write the task onto the
   block** — a short actionable description (next action + the artifact's
   **clickable URL**, resolved so it doesn't 404) so it's readable at do-time,
   with a single `valor:task:<slug>` idempotency token appended (labeled "leave
   it"; no shape tag). **Prep blocks** (from `prep_blocks`) get written the same way
   — title `Prep: <for_meeting>`, a "gather docs + frame 2–3 talking points"
   description, and a `valor:prep:<slug>` token (idempotent like the task token).
   Idempotent via the `valor:task:` token (never duplicate), **skip
   unverified claims**, delete/complete items whose claim has since verified
   **resolved**, and never touch items Valor didn't create. No writer → present
   the plan only, note once.
4. **Auto-schedule sync prep** — only if `context.project_focus.auto_sync_prep`
   is `true` (the default) **and `planning.pre_meeting_prep_minutes` > 0** (0 means
   prep is disabled — skip). For each **`project_sync` occurring today**, schedule a
   one-off run of `/valor-sync-prep` at **(sync start − `planning.pre_meeting_prep_minutes`,
   default 30 min)** via the scheduled-tasks tool, so your talk points are
   generated right as the prep block opens. Rules: **idempotent** — first list
   existing scheduled tasks and skip any sync already scheduled for today (one-off
   tasks self-delete after firing); **multiple syncs** → one scheduled run each;
   **past lead time** — if (sync − prep minutes) is already past, run
   `/valor-sync-prep` now when the sync is still upcoming (within ~the hour), else
   skip. The run keeps its own no-op safeguard (does nothing if no `project_sync`
   is imminent), so a stale trigger is harmless.

## Monday / Return-from-Absence Mode

If `context.briefing_meta.is_monday_or_catchup` is `true`, add a "Catch-Up"
section after Work Context:

```
### Weekend/Absence Catch-Up
- PRs merged while you were away: [list from gh pr list --state merged --search "updated:>YYYY-MM-DD"]
- New tickets assigned since [last_briefing_date]
- Status changes on your tickets
```

Run additional queries:
```bash
# PRs merged since last briefing
gh pr list --state merged --search "updated:>LAST_DATE" --author @me --json number,title,mergedAt --limit 10
gh pr list --state merged --search "updated:>LAST_DATE review-requested:@me" --json number,title,mergedAt --limit 10
```

## Evidence Recording

Do NOT record a generic "morning briefing completed" entry. Instead, record
what was actually prioritized and surfaced. Build the `--statement` dynamically
from the briefing content.

**Template:**
```bash
python3 ~/.valor/evidence_cli.py add \
    --activity morning_briefing_completed \
    --competency autonomy_scope \
    --statement "Prioritized: [top 2-3 items from Suggested Priorities]. Key items: [N] tickets, [M] PRs, [P] meetings." \
    --agent valor-morning-briefing
```

**Examples of GOOD statements:**
- "Prioritized: PROJ-123 data pipeline fix (blocked on data), PR #245 review. Key items: 3 tickets, 1 PR, 2 meetings."
- "Prioritized: unblock PROJ-200 cache migration, prep for 1:1. Key items: 2 tickets, 0 PRs, 1 meeting. Gap flagged: no cross-team reviews this week."

**Examples of BAD statements (never use these):**
- "Completed daily planning and prioritization via Valor briefing"
- "Morning briefing completed"

If the user acts on a coaching suggestion during the conversation (e.g.,
reviews a cross-team PR, starts a design doc), record additional evidence
with a specific statement describing what they did:

```bash
python3 ~/.valor/evidence_cli.py add \
    --activity pr_review_cross_team \
    --competency collaboration \
    --statement "Reviewed cross-team PR #892 from Sarah -- flagged missing error handling in retry logic" \
    --agent valor-morning-briefing
```

Available activities and competencies are defined in `valor/src/evidence_cli.py`.
Competencies: subject_matter, industry_knowledge, collaboration, autonomy_scope, leadership.

## State Update

After the briefing, update state:

```bash
python3 ~/.valor/evidence_cli.py state-set \
  last_briefing_date "$(date +%Y-%m-%d)" \
  last_briefing_timestamp "$(date -Iseconds)" \
  briefing_count +1 \
  today_priorities '["Review PR #412","Finish PROJ-1234 design doc"]'
```

Replace the `today_priorities` value with the actual suggested priorities
as a JSON array (single-quoted to prevent shell expansion).

### Work Area Auto-Detection

Refresh `user_work_areas` in state.json when `context.briefing_meta.work_area_refresh_due`
is `true` (already computed by the context command based on briefing count and interval).

#### Step 1: Gather project signals

Use data already collected for the briefing plus lightweight exploration:

1. **Jira tickets** (already fetched): collect summaries and descriptions of
   all active tickets.
2. **Recent PRs** (already fetched): collect titles and repo names.
3. **Repo READMEs**: inspect the current workspace first, then nearby project
   directories the assistant can already access. Look for repos or project
   roots that contain a `.git/` directory or project files (`README.md`,
   `PROJECT.md`, `pyproject.toml`). Read the README/PROJECT.md of each
   (first 80 lines is enough). Skip repos that look like forks, personal
   config, or one-off experiments.

#### Step 2: Extract research-relevant keywords

From the gathered signals, derive **technical keywords that would surface
relevant AI/ML and industry news**. Apply these rules:

- **NO internal project names** (e.g., "Project Atlas", "System Phoenix"). These
  won't match any external news articles.
- **YES to the underlying technical concepts** (e.g., "automated data
  cataloging", "LLM metadata generation", "text-to-SQL").
- Group keywords by project/domain for organizational clarity.
- Keywords are used for **relevance annotations** on general news
  headlines, not for narrowing search queries.
- Include both specific terms ("content moderation ML") and broader terms
  ("RAG retrieval augmented generation") so annotations can match a wider
  range of general headlines.

#### Step 3: Staleness check on pinned keywords

Before merging, check whether pinned keywords are still relevant:

1. Read `user_work_areas_pinned` from state.
2. For each **group** of pinned keywords (they cluster by project -- e.g.,
   keywords related to the same project area all cluster together as a
   group), check if the project still has active work:
   - Any assigned Jira tickets in non-Done status that relate to this area?
   - Any open PRs or recent commits in related repos?
   - Any currently active repo in the user's accessible workspaces still tied
     to this domain?
3. If a keyword group has **no active signals** (all tickets Done/Closed,
   no recent PRs, no active repo), flag it for removal. Present the user
   with a brief prompt:
   > "These pinned work areas appear inactive -- remove from news tracking?
   > [list of stale keywords]. Say 'keep' to retain them."
4. If the user confirms removal, move the keywords from
   `user_work_areas_pinned` to `user_work_areas_retired` (a new list in
   state.json for historical reference).
5. If the user says "keep", leave them pinned. Do not ask again for
   `staleness_suppress_interval` briefings (default: 10 if not set in
   state). Track via `staleness_check_suppressed_until` count in state.

**Manual removal:** If the user says "remove X from my work areas" or
"I'm done with project Y", immediately remove related keywords from both
`user_work_areas` and `user_work_areas_pinned`, and add them to
`user_work_areas_retired`.

#### Step 4: Merge and write to state

Merge intelligently:

1. Surviving pinned keywords (after staleness removal) stay.
2. Auto-detected keywords replace the non-pinned portion.
3. Final list = surviving pinned + auto-detected, deduplicated.

When the user **manually requests** a keyword addition (like "add Project Atlas
keywords"), add those keywords to `user_work_areas_pinned` so they survive
future auto-detection runs.

```bash
python3 ~/.valor/evidence_cli.py state-set \
  user_work_areas '["keyword1","keyword2"]' \
  user_work_areas_last_refreshed "$(date +%Y-%m-%d)"
```

Replace the `user_work_areas` value with the actual combined (pinned + auto-detected,
deduplicated) keyword list.

## Follow-Up Interaction

After the briefing, the user may ask follow-up questions. Handle them naturally:

- **"Tell me more about [ticket/PR]"** -- Fetch details using the appropriate
  tool (Atlassian MCP for tickets, `gh pr view` for PRs)
- **"Draft a design doc for [ticket]"** -- Use the
  `/valor-design-doc` command for structured options and trade-offs
- **"What should I say in standup?"** -- Synthesize a concise standup update
  from the briefing data (yesterday, today, blockers)
- **"Help me review [PR]"** -- Use the
  `/valor-pr-review` command for coached review with career-level annotations
- **"Prioritize differently"** -- Re-order based on user's input

These follow-ups are part of the natural conversation -- no special trigger needed.
