# Valor 1:1 Prep

<!-- valor:integrations github=optional jira=optional calendar=optional news=none -->

Generate a structured document for your next 1:1 with your manager, grounded
in evidence from the last 1--2 weeks plus any saved weekly reflections.

## When to Use

- User says: "prep for 1:1", "1:1 prep", "prepare for my 1:1", "what should
  I talk about in my 1:1", or runs `/valor-prep`
- Useful before a scheduled manager sync or performance check-in

## 1. Check Integrations

Use `context.integrations` from the session-start context (already loaded).

| Integration | Used for |
|-------------|----------|
| `github` | Recent PRs merged/reviewed (context for talking points) |
| `jira` | Tickets completed/in-progress (context for talking points) |
| `calendar` | This week's working-day capacity (off-days/holidays) to frame the goals section (§2.7) |

If an integration is `false`, skip its section silently. Evidence and weekly
summaries are always available.

## 2. Gather Evidence

### 2.1 Recent Evidence (primary source)

```bash
python3 ~/.valor/evidence_cli.py export --days 14 --format json
```

This is the primary data source. Group entries by competency and count.
If the evidence store is empty, note it and proceed with whatever other
data is available.

Entries may include **meeting notes captured at wrap-up** (`activity:
meeting_notes` — a per-meeting summary with a link to the full notes). Use these
to ground the "what happened / last week" talking points in specific syncs and
the decisions made in them; follow the link if you need detail. This is how a
sync whose notes live only on the calendar still informs the 1:1.

### 2.2 Weekly Summaries (trend context)

```bash
python3 ~/.valor/evidence_cli.py weekly-summary-list --limit 4
```

If available, use these to show trends across weeks (e.g., "collaboration
has been growing over the last 3 weeks"). If none exist, skip the trend
section if none are available yet.

### 2.3 Career Framework

Use `context.levels` for level names, then run:

```bash
python3 ~/.valor/evidence_cli.py framework-slice
```

This returns the target-level competency definitions and company values
for the configured levels.

### 2.4 External Context (if integrations enabled)

If `integrations.github` is true:
```bash
# PRs you merged, and PRs you reviewed, in the last 2 weeks (DATE_14D_AGO = YYYY-MM-DD)
gh search prs --author=@me --merged --merged-at=">=DATE_14D_AGO" --json number,title,closedAt,repository,url --limit 10
gh search prs --reviewed-by=@me --merged --merged-at=">=DATE_14D_AGO" --json number,title,author,closedAt,repository,url --limit 5
```

If `integrations.jira` is true and `jira_projects` is set:
Use Atlassian MCP or Jira slash commands to find tickets completed in the last
2 weeks:
```
assignee = currentUser() AND statusCategory = Done AND updated >= -14d ORDER BY updated DESC
```
`statusCategory = Done` works on every Jira site; status names like
"Done"/"Closed" differ per site, and JQL errors on a name the site doesn't have.

These are supplementary -- evidence entries are the primary source.

### 2.5 Chronic items (escalation candidates)

Surface items carried unresolved long enough to be worth raising. Read the
verification cache:

```bash
python3 ~/.valor/verify.py list --status unresolved
```

Any claim whose `miss_count` >= `context.verification.escalation_threshold`
(default 3) is an **escalation candidate** -- verified-missing across that many
checks (e.g. a doc unposted for weeks, a PR stuck in review). These are
advisory: surface them so the user can choose to raise them; they map naturally
to the "roadblocks / need help" part of a 1:1. Also fold in anything pinned in
`state.escalate_in_one_on_one`.

### 2.6 Your 1:1 doc and its format

If `context.one_on_one_doc_set` is true, the deliverable is this week's entry
drafted **in the format the user already uses** -- not Valor's generic layout.

1. Read the doc reference from `state.one_on_one.doc` (a Google Doc link/id or
   name). If unset, ask once ("What's your 1:1 doc? paste the link") and store:
   `python3 ~/.valor/evidence_cli.py state-set one_on_one '{"doc":"<ref>","format_notes":"","write_mode":"off","staging_doc":""}'`
   (`state-set` replaces the whole object, so carry over any existing
   `write_mode`/`staging_doc` instead of resetting them).
2. Discover a docs-read capability (a Drive/Docs MCP that reads file content, or
   a docs-related slash command). If none, use the §4.4 fallback.
3. Read the doc and study the **most recent 1-2 entries** to infer the format:
   section labels (verbatim), their order, bullet vs numbered convention and
   nesting, the tone/length of each section, whether new entries go at the top
   or bottom, and how entries are dated/titled. If the doc has **tabs**, note
   which tab holds the dated weekly entries (others are often pinned notes or
   archives) -- §4.2 writes only there.
4. If the doc can't be read but `state.one_on_one.format_notes` is set, use that
   as the format spec.

Do not impose a structure -- mirror theirs exactly. Formats are personal.

**While the doc is open, capture this week's goals** (silently — don't ask). Extract
the short list of what the user said they're driving this week (by meaning; format
varies) and store it so the morning briefing ranks the day's todos against it. Set
`week_start` to `context.prioritization.week_start_current` **verbatim** (don't
compute it):
```bash
python3 ~/.valor/evidence_cli.py state-set prioritization \
  '{"week_goals": ["..."], "week_start": "<context.prioritization.week_start_current>", "goals_source": "one_on_one_doc"}'
```
This writes only the goals block; `standing_rules` are a separate key and aren't
touched here. If no goals are stated yet, leave it untouched. The briefing also
refreshes this on its own when stale, so this is just the natural place to catch
them at the 1:1.

### 2.7 This week's capacity (frames the goals)

Goals for the week should be set against the week's **real capacity**, not a
nominal five days — a week with two days off can't carry a full week's load. If
`integrations.calendar` is `true` and a calendar reader is available, size the
week before you draft the goals section:

1. Read this ISO week's events — Mon–Fri of
   `context.prioritization.week_start_current`.
2. Compute **working days available**: 5 weekdays, minus any full-day
   `outOfOffice` / company holiday on the calendar, minus any dates in
   `context.ooo.dates` that fall in this week.
3. Note the count and which days are off — e.g. *"3 working days this week (off
   Thu/Fri)"*.

If no calendar reader is available, skip this silently. Carry the result into
§4.1: scope the goals to the capacity you found and add the one-line framing, so
the goals are read against the real runway.

## 3. Analyze

### 3.1 Competency Map

For each competency, count evidence entries and categorize:

| Competency | Entries | Strength/Gap | Key Examples |
|------------|---------|-------------|--------------|
| Subject Matter Expertise | N | strong/developing/gap | ... |
| Industry Knowledge | N | ... | ... |
| Internal Collaboration | N | ... | ... |
| Autonomy & Scope | N | ... | ... |
| Leadership | N | ... | ... |

**Strength:** 3+ entries. **Developing:** 1--2 entries. **Gap:** 0 entries.

### 3.2 Trends (if weekly summaries available)

Compare competency counts across the last 2--4 weekly summaries. Note:
- Competencies that are growing (more entries week-over-week)
- Competencies that are stagnating or declining
- Gaps that have persisted across multiple weeks

### 3.3 Target-Level Alignment

Map the strongest evidence entries to specific target-level competency
definitions from `career_framework.md`. Identify:
- Where the user is **meeting** target-level expectations
- Where the user is **approaching** but not yet at target level
- Where there is a **gap** with a concrete suggestion

## 4. Output

### 4.1 This week's 1:1 entry — primary deliverable (when a doc format is known)

Using the format learned in §2.6, draft **this week's entry, ready to paste**
into the user's doc. This is the main output — not a pile of key points the user
must reformat afterward.

- **Plain text — no markdown** (paste path; §4.2 writes natively instead). The
  entry is pasted into a doc that renders
  markdown literally, so emit **no `*`, `**`, `_`, or `#`** — no bold, italic,
  markdown bullets, or `#` headers (a plain leading `- ` for a list item is fine;
  `*` is not). The user applies their doc's real formatting (bold, bullets) after
  pasting — don't pre-bake it, and don't make them strip stray asterisks first.
- **Mirror the doc's structure:** the same section labels (verbatim), order,
  tone, and length — rendered as plain text per the rule above. Title/date the
  entry for the upcoming 1:1 and place it where new entries go (usually the top).
- **Fill each section by meaning, not by Valor's labels:** recent shipped work
  / status (evidence entries, merged PRs, closed tickets) → the "what happened /
  last week" section; **chronic escalation candidates (§2.5)** → the "roadblocks
  / need help" section; in-progress work → the "project overview" section;
  next-period priorities → the "goals" section.
- **Scope goals to the week's capacity (§2.7):** when days off shorten the week,
  trim or sequence the goals to fit the working days available and add a brief
  "short week — N working days (off [days])" framing, so next-period goals are
  read against the real runway rather than a nominal five days.
- **Match the user's own length — no longer.** Measure the last 1-2 entries the
  user wrote (bullets per section, words per bullet, nesting depth) and stay at
  or under that. The entry carries **outcomes, status, and asks** only: one line
  per PR in the doc's own PR-line style (e.g. `repo#N - TICKET short title
  (status)`), at most one level of sub-detail. Leave implementation detail out
  of the entry — test counts, row/record counts, step-by-step fixes, per-person
  support lists; that is evidence, and it belongs in §4.3, not in the doc. If
  the user would have to cherry-pick lines, the draft is too long.
- **Concrete and honest:** reference specific PRs/tickets; keep the user's
  voice. The user reviews before pasting — do not fabricate; if a section has
  nothing real, leave it light/empty as their doc does.

Then add a short **"Chronic — consider raising"** note: the §2.5 escalation
candidates with how long each has been stuck, so the user decides what to
actually surface.

### 4.2 Write the entry into a doc (opt-in)

By default prep is **read-only**: §4.1 is paste-ready text and the user pastes
it. The shared 1:1 doc is usually visible to the manager, and **doc version
history keeps every revision** -- trimming an entry after it lands does not
un-share what was written. So **nothing unreviewed ever goes into the shared
1:1 doc.** `context.one_on_one_write_mode` picks one of:

| Mode | Writes to | When |
|------|-----------|------|
| `off` (default) | nothing | -- the §4.1 text is the output |
| `staging` | the user's **private staging doc** (`one_on_one.staging_doc`), never the shared doc | every run, **including unattended** scheduled runs |
| `approve` | the shared 1:1 doc (`one_on_one.doc`) | only in a **live** session, after the user approves the exact text |

**`staging` -- the standing authorization for unattended runs.** Opting into
`staging` is the user's durable permission for prep to write this week's entry
into their staging doc, including a scheduled routine whose prompt is just
`/valor-prep`; do not wait for a live confirmation and do not require the
routine prompt to restate it. It covers only the staging doc. Before every
write, **verify the staging doc is private**: read its sharing/permissions and
write only if the user is the sole person with access (no other users, groups,
domain or link sharing). If it is shared, or permissions cannot be read, do not
write -- fall back to §4.1 and say why in one line. The user trims the entry
there and copies it into the 1:1 doc themselves (doc-to-doc copy keeps the
formatting). No staging doc set → fall back to §4.1 and say "set
`one_on_one.staging_doc` to a private doc to get the draft written there".

**`approve` -- shared doc, live approval only.** Show the entry in chat first.
Write into the shared 1:1 doc only after the user, **live in this session**,
approves that exact text (after their edits). An unattended or scheduled run
never writes the shared doc in any mode -- it behaves like `staging` if a
staging doc is set, else like `off`. Approval covers that one write; a later
change needs a new approval.

**Writer discovery** (match by capability, not a fixed tool name -- MCP server
ids are per-session):

1. **Positional insert only.** The writer must insert text and apply formatting
   **at a position** in the existing document, tab-aware when the doc has tabs
   -- e.g. a Google Docs `batchUpdate` with `insertText` / paragraph-style /
   bullet / link requests at an index, via a Docs MCP or a docs skill/CLI.
2. **Never use a whole-file replace on the 1:1 doc.** A Drive-style
   `update_file` / upload / "replace content" tool rewrites the entire doc and
   can destroy the manager's comments, suggestions, history and the other tabs.
   It is **not** a writer for this purpose, even if it is the only Drive tool
   present.
3. **No suitable writer** → fall back to the §4.1 paste-ready output and say so
   in one line ("Write-back is on, but no positional doc writer is available in
   this session -- here's the entry to paste.").

**What to write** (both modes) -- this week's entry only, nothing else:

- **Where:** in `approve` mode, where new entries go per the §2.6 format
  (usually the top of the entries), in the **tab that holds the weekly
  entries** when the doc has tabs; never into pinned/notes/archive tabs. In
  `staging` mode, at the top of the staging doc, newest first.
- **Date:** the **actual 1:1 date** from the calendar, so a holiday reschedule
  moves the date with it. Find this week's occurrence of the manager 1:1, first
  match wins:
  1. `routines.prep.personalization.calendar_event_id` when set;
  2. the recurring 1:1 with `state.manager` as attendee;
  3. **no manager set** → this week's event whose title reads as a 1:1
     (`1:1`, `1-1`, `one on one`) with exactly two attendees, the user and one
     other person, picking the one with the same title/attendee as recent doc
     entries' Gemini/notes links when several match. A moved single instance of
     the recurring event counts (e.g. Mon → Tue after a holiday): use the
     instance's own date, not the series' usual weekday.
  4. No calendar, or nothing matched → `routines.prep.personalization.one_on_one_day`,
     and say in the report that the date was not confirmed from the calendar.
  Format the date/title the way the doc's existing entries do.
- **Draft marker (staging only):** the staging copy starts with
  `[Draft by Valor, trim before copying]`. Keep `[confirm]` markers on any
  claim not backed by an evidence entry, PR, or ticket. In `approve` mode the
  approved text goes in as approved -- no draft marker, no `[confirm]` left.
- **Native formatting:** apply the doc's real formatting -- its heading style
  for the entry title and section labels, real bullets/nesting, and real links
  for PRs/tickets -- instead of the §4.1 plain-text rule, which applies only to
  the paste path.

**Idempotent, never destructive.** Before inserting, look for an entry already
dated for this 1:1 in the target doc:

- **None** → insert the full entry.
- **Exists** (the user, the manager, or an earlier run started it) → fill only
  sections that are **empty**; leave every non-empty section exactly as is.
  Never overwrite, reorder, or duplicate content someone else wrote, and never
  insert a second entry for the same date.
- Never edit, move, or delete anything outside this week's entry.

**Report** in chat what was inserted and where (which doc, tab, entry
title/date, which sections were filled vs. left alone because they already had
content). The
"Chronic — consider raising" note (§4.1) and the supporting analysis (§4.3)
stay **in chat**, never in the doc.

**Goals feed prioritization.** Goals are read from the shared 1:1 doc as §2.6
describes -- the entry that actually landed there, not the staging draft. In
`approve` mode, the goals section of the written entry is this week's goals: store them into `prioritization.week_goals` exactly as §2.6
describes (`week_start` = `context.prioritization.week_start_current` verbatim,
`goals_source: "one_on_one_doc"`), so the briefing ranks against what is
actually in the doc.

### 4.3 Supporting analysis (grounding, condensed)

Below the entry, include a condensed version of the §3 competency map and
target-level alignment — the evidence behind the entry, for the user who wants
to go deeper. The entry in §4.1 is the deliverable; this is backup.

### 4.4 Fallback — no doc format available

If no 1:1 doc is configured and no docs reader is available, produce the generic
layout instead, and note once: "Set `one_on_one.doc` (your 1:1 doc link) to get
this drafted in your doc's own format." This layout is also a **paste-ready
deliverable — keep it plain text (no `*`/`**`/`_`), so the user can paste without
stripping markup**:

```text
1:1 Prep — [date range]

Highlights
- [Top 2-3 accomplishments with specific evidence]

By Competency
[Competency Name] — [N entries, strength/developing/gap]
- Evidence / Target-level alignment / Talking point

Gaps to Discuss
- [Gap competency]: 0 entries this period. Suggestion: [specific action]

Chronic — consider raising
- [§2.5 escalation candidates, with how long stuck]

Suggested Asks
- [1-2 asks grounded in gaps]

Narrative
[3-5 sentence opener, grounded in evidence]
```

## 5. Tone and Framing

- **Concrete, not aspirational.** Every talking point should reference a
  specific evidence entry, PR, or ticket.
- **Balanced.** Show both strengths and gaps -- managers value self-awareness.
- **Actionable.** Gaps should come with specific next steps, not vague
  "do more of this."
- **Promotion-aware.** Frame accomplishments in terms of the target level,
  not the current level. Use the career framework definitions.

## 6. Record Evidence

After generating the prep document:

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity one_on_one_prep \
  --competency leadership \
  --statement "1:1 prep: [period]. Highlights: [top item]. Strengths: [strongest competency]. Gaps: [weakest]. Ask: [suggested ask]." \
  --agent valor-prep
```

## 7. Fallbacks

| Scenario | Action |
|----------|--------|
| Evidence store empty | Note that evidence recording needs to start. Offer to help with setup. Use any available GitHub/Jira data to build a minimal prep. |
| No weekly summaries | Skip trends section. Note: "Run `/valor-weekly` to enable trend tracking." |
| GitHub/Jira disabled | Build prep from evidence only. This is a valid workflow. |
| Career framework not configured | Use generic competency names. Note: "Configure `~/.valor/career_framework.md` for personalized coaching." |
| Evidence CLI fails | Note the error. Proceed with any available data. |
| `one_on_one_write_mode` is `"staging"`/`"approve"` but no positional doc writer | Output the §4.1 paste-ready entry; note in one line that write-back was skipped. Never substitute a whole-file replace tool. |
| `staging` but the staging doc is shared with anyone, or its permissions can't be read | Do not write. Output §4.1 and say the staging doc must be private. |
| Unattended run with `approve` | Never write the shared doc. Behave as `staging` if a staging doc is set, else `off`. |
