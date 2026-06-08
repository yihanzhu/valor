# Valor 1:1 Prep

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
gh pr list --state merged --author @me --limit 10
gh search prs --review-requested=@me --state=closed --limit 5
```

If `integrations.jira` is true and `jira_projects` is set:
Use Atlassian MCP or Jira slash commands to find tickets transitioned to
Done/Closed in the last 2 weeks.

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
   `python3 ~/.valor/evidence_cli.py state-set one_on_one '{"doc":"<ref>","format_notes":""}'`.
2. Discover a docs-read capability (a Drive/Docs MCP that reads file content, or
   a docs-related slash command). If none, use the §4.3 fallback.
3. Read the doc and study the **most recent 1-2 entries** to infer the format:
   section labels (verbatim), their order, bullet vs numbered convention and
   nesting, the tone/length of each section, whether new entries go at the top
   or bottom, and how entries are dated/titled.
4. If the doc can't be read but `state.one_on_one.format_notes` is set, use that
   as the format spec.

Do not impose a structure -- mirror theirs exactly. Formats are personal.

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

- **Plain text — no markdown.** The entry is pasted into a doc that renders
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
- **Concrete and honest:** reference specific PRs/tickets; keep the user's voice
  and length. The user reviews before pasting — do not fabricate; if a section
  has nothing real, leave it light/empty as their doc does.

Then add a short **"Chronic — consider raising"** note: the §2.5 escalation
candidates with how long each has been stuck, so the user decides what to
actually surface.

### 4.2 Supporting analysis (grounding, condensed)

Below the entry, include a condensed version of the §3 competency map and
target-level alignment — the evidence behind the entry, for the user who wants
to go deeper. The entry in §4.1 is the deliverable; this is backup.

### 4.3 Fallback — no doc format available

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
