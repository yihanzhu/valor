# Valor Evening Wrap-up

<!-- valor:integrations github=optional jira=optional calendar=optional news=none -->

Generate an end-of-day summary that captures accomplishments, carry-forward
items, and a brief career reflection. This pairs with the Morning Briefing
as bookends for the workday.

## When to Use

- User says: "wrap up", "end of day", "call it a day", "let's wrap up",
  "evening wrap-up", or signals they are done for the day
- Auto-suggested after 4pm on weekdays (see valor-agent.md trigger)

## Integration Check

Use `context.integrations` from the session-start context (already loaded).
This command is primarily local (conversation, git, evidence, carry-forward).
If `integrations.github` or `integrations.jira` are `true`, optionally
include relevant activity from those sources. If `false`, skip silently.

## 1. Gather Context

Use available sources to reconstruct the day's work. Run in parallel where
possible. If a source is unavailable, skip it gracefully.

### 1.1 Conversation Context

Review the current conversation for:
- Tasks completed (code written, PRs created, investigations concluded)
- Decisions made (design choices, prioritization changes)
- Cross-team interactions (messages drafted, alignment achieved)
- Open threads (questions asked but not answered, PRs awaiting review)

### 1.2 Git Activity

```bash
# Commits made today in the current workspace repo
git log --oneline --since="$(date +%Y-%m-%d)T00:00:00" --author="$(git config user.name)" 2>/dev/null | head -20
```

Run this in the current workspace repo. If the user mentions work in other
repos, run it there too -- but prefer the current workspace to avoid noise
from unrelated repositories.

### 1.3 Evidence Store

```bash
python3 ~/.valor/evidence_cli.py list --days 1
```

Use today's evidence entries to ensure nothing is missed.

### 1.4 Recalled Memories

Check if there were carry-forward items from a previous session:

Read `~/.valor/carry-forward/latest.md` if it exists. If not, look for the
newest file matching `~/.valor/carry-forward/carry-forward-*.md`.

These files are written by previous `/valor-wrapup` runs and contain the
carry-forward items that should be recalled the next time the user starts work.

If no carry-forward memory files exist, skip this step.
Note which carry-forward items were addressed and which remain open.

### 1.5 Cross-Session Transcript Scan

Agent transcripts are siloed per workspace. The current conversation only
sees its own session. To capture the full day's work, scan ALL workspaces.

**Discover today's sessions:**

```bash
python3 ~/.valor/collect_transcripts.py --days 1 --json
```

This returns a JSON array of all sessions from the past 24 hours across
every workspace (both Claude Code and Cursor). Each entry has: `uuid`, `workspace`, `title`,
`query_preview`, `mtime`, `file`, `size_kb`.

**Process other sessions:** For each session that is NOT the current
conversation, dispatch a `Task` subagent (`model: fast`, `readonly: true`)
to read and summarize the transcript. The subagent prompt should be:

> Read the agent transcript at `{file_path}`. Summarize what was accomplished
> in this session: tasks completed, decisions made, PRs created, messages
> drafted, cross-team interactions, open threads. Be specific -- include file
> paths, PR numbers, ticket IDs. Return a structured bullet list.

Run subagents in parallel (batch them in a single message). If there are
more than 5 other sessions, prioritize by `size_kb` (larger = more work).

**Merge results:** Combine subagent summaries with the current conversation
context (section 1.1) to form the complete picture of the day's work.

### 1.6 Activity Reconciliation

Cross-reference the morning briefing's suggested priorities, today's
evidence store, and the cross-session transcript summaries (section 1.5).
Activities often get drafted or planned in one session but executed outside
it (e.g., Slack messages sent, Confluence pages updated, follow-ups posted).

**Load morning priorities from state:** Read `today_priorities` from
`~/.valor/state.json`. This list is set by the morning briefing and
contains the day's planned priorities. If the key is missing (no briefing
today), skip the reconciliation against priorities.

**Steps (verify-first — look before asking):**

1. List today's evidence entries from the evidence store (section 1.3).
2. Compare against `today_priorities` -- which priorities were addressed?
   Which were not? Note unaddressed ones as carry-forward candidates.
3. Review the merged transcript summaries (current session + other sessions)
   for work not yet in the evidence store:
   - Messages drafted for Slack, email, or other channels
   - Confluence pages created or updated
   - Jira tickets updated
   - Cross-team coordination planned
   - Follow-up actions discussed
4. **Verify sends before asserting or asking.** Session memory says "drafted";
   only the channel says "sent" — a message pasted by the user two hours before
   the wrap-up looks identical to one never sent. If a Slack tool is available:
   - Run **one broad sweep first**: search `from:me` for today. Cross-reference
     every draft found in step 3 against the results.
   - For each draft, **register the claim** (if not already registered at draft
     time) with the destination pinned, then record what the sweep showed:
     ```bash
     python3 ~/.valor/verify.py register --type slack \
       --id "<#channel-or-recipient>: <topic>" \
       --assert-state "not sent" \
       --recipe '{"channel": "<#channel>", "keywords": "<distinctive phrase>", "drafted_at": "<YYYY-MM-DD>"}'
     python3 ~/.valor/verify.py record --type slack --id "<same id>" --result <resolved|unresolved>
     ```
     `resolved` = found sent; `unresolved` = searched and genuinely absent.
     If the destination is unknown and can't be pinned, register `--confirm-only`
     — that claim can only ever surface as a question, never as "not sent".
5. Ask the user **with findings in hand**, not open-ended: "Found the Alex
   message sent 14:59 in #data-eng — marking it sent. The #platform-ops
   question shows no send — still pending, or did it go somewhere else?"
   Only unverifiable drafts get an open question.
6. For each confirmed/verified activity not already in the evidence store,
   record it:
   ```bash
   python3 ~/.valor/evidence_cli.py add \
     --activity <type> \
     --competency <competency> \
     --statement "<specific description>" \
     --agent valor-evening-wrapup \
     --date $(date +%Y-%m-%d)
   ```

**Vocabulary rule:** never write "not sent" / "unsent" / "unposted" about an
artifact unless a same-run `record --result unresolved` backs it. The only
allowed states are the gate's own display strings.

This reconciliation step ensures the evidence store reflects actual work done,
not just work done inside the current session.

### 1.7 Capture Meeting Notes

Meeting notes (e.g. Gemini "I took notes for you") live only on the calendar
event — nothing else reads them, so what happened in a sync is invisible to
later `/valor-prep` and `/valor-weekly` unless it's captured here. Skip this step
if `integrations.calendar` is `false`.

1. List **today's** calendar events (the same calendar source the briefing uses).
   The notes are an **attachment** on the event — Gemini saves them as a Google
   Doc titled **"Notes by Gemini"** (treat any Doc-type attachment as a notes
   doc). An event's `description` is the meeting *agenda*, not the notes — don't
   use it as a notes source. So: a meeting with a notes attachment is one to capture.
2. **Skip short recurring standups** — a daily/weekly recurring meeting ≤ ~15 min
   (e.g. "standup", "daily", "scrum", "check-in") — even if notes are attached;
   that's status noise, not the work. Capture project syncs, 1:1s, design/decision
   reviews, externals, and other substantive meetings.
3. Read the notes doc (the attachment's `fileUrl`) with the same docs-read
   capability `/valor-prep` uses for the 1:1 doc (a Drive/Docs MCP, or a docs
   slash command) and summarize it. **If no docs reader is available, still record
   the meeting with the notes-doc link** so the user can open it — do *not* fall
   back to the agenda in `description`.
4. Record each as a **concise** evidence entry (a summary + a link — never the
   full doc) so it lands in the "last 2 weeks" window `/valor-prep` and
   `/valor-weekly` read:
   ```bash
   python3 ~/.valor/evidence_cli.py add \
     --activity meeting_notes \
     --competency <best-fit> \
     --statement "<meeting> (<who>): <2-3 line summary — decisions, outcomes, action items>. Notes: <link>" \
     --agent valor-evening-wrapup \
     --date $(date +%Y-%m-%d)
   ```
   Pick the dominant competency from the content (a cross-team sync →
   `collaboration`; a technical decision → `subject_matter`; driving the call →
   `leadership`). Keep the full-notes **link** in the statement so detail is one
   click away without bloating the store. **Before recording, list today's
   already-captured notes (`python3 ~/.valor/evidence_cli.py list --days 1`) and
   skip any meeting already in there.** The CLI only auto-dedupes a *byte-identical*
   statement, and a re-run will reword the summary — so this explicit skip is what
   keeps a second wrap-up from double-recording the same meeting (which would then
   double-count in the window `/valor-prep` and `/valor-weekly` read).

### 1.8 Verification Gate (run before writing carry-forward)

The wrap-up is where phantom claims are *born*: an unchecked "PROJ-42 1-pager
unposted" gets written to carry-forward, and tomorrow's briefing reads it as
fact. Stop that here. **The checklist is runtime-enumerated — do not
hand-enumerate claims from memory** (memory is exactly what missed a sent
message for six days).

1. **Register any new artifact claim noticed today** that isn't in the gate yet
   (`verify.py register` — see §1.6 for slack; for PRs use `owner/repo#N`, for
   Confluence the page title/key, for Jira the issue key). Registration is what
   makes tomorrow's gate able to see the claim at all.
2. **Run the reconcile — its output IS the checklist:**
   ```bash
   python3 ~/.valor/verify.py reconcile
   ```
   (`reconcile` auto-resolves `github_pr` claims via `gh` and merges any
   fragmented duplicate claims itself.)
3. For each entry in `stale_needs_check`, run its embedded `lookup` with the
   matching tool (Atlassian/Slack/Drive MCP), then
   `verify.py record ... --result <resolved|unresolved|unverified>`.
   - **resolved** → it's done: move it to Accomplished and record a completion
     entry (this is how a chronic zero-streak finally breaks).
   - **unresolved** → carry it with the real `day_count`.
   - **unverified** → demoted to "unverified — confirm or drop?", counter frozen.
4. Entries in `unverifiable` are confirm-only claims: ask the user (skip ones
   marked `parked` — the weekly owns those).
5. If `verification.enabled` is `false` in context, skip this section.

End the section by printing the gate summary line for the user:
`Gate: K claims — R resolved · U unresolved · V unverified` (counts from the
final reconcile output).

Two more rules when writing carry-forward claims:

- **Don't carry a downstream task before its upstream work is done.** A "publish
  / write up / document X" item isn't a real carry-forward item until the work it
  describes has reached a publishable stage (the ticket is resolved or a finished
  draft exists). Until then it's a coaching nudge, not a claim — carrying it early
  is what breeds a recurring "publish the 1-pager" ghost for work still in flight.
- **Identify each claim by its canonical id** — `owner/repo#N` for PRs (the
  runtime rejects bare numbers at register and merges legacy fragments), the
  issue key for Jira, the doc title for Confluence/Drive,
  `<#channel-or-recipient>: <topic>` for Slack. "publish the PROJ-42 1-pager" vs
  "post the 1-pager" are the *same* claim; phrasing-drift forks counters that
  each look new, so nothing ever escalates. Reuse the `canonical_id` that
  `register` returns.

## 2. Summarize the Day

### 2.1 Accomplishments

List concrete things completed today. Be specific — file paths, PR numbers,
ticket IDs, decisions made. Group by theme if there were multiple workstreams.

### 2.2 Carry-Forward Items

List tasks that need attention tomorrow. For each item, note:
- What it is (specific and actionable)
- Current state (where it was left off)
- Any blockers or dependencies
- **Verification status** for artifact claims (from §1.8): a verified-missing
  item shows its real day count (e.g. "unresolved — 14d"); an unconfirmable one
  is written as "unverified — confirm or drop?" with the counter frozen. Do not
  carry an artifact claim forward without one of these states.

### 2.3 Career Reflection

Map the day's activities to target-level competencies (from `~/.valor/career_framework.md`).
Keep this brief — 2-3 sentences max:
- Which competencies were exercised today
- One specific suggestion for tomorrow that would strengthen a gap area

## 3. Output Format

```markdown
## Valor Evening Wrap-up — [Day], [Date]

### Accomplished Today
- [Activity 1] — *[competency tag if significant]*
- [Activity 2]
- ...

### Tomorrow's Pickup
1. [Task] — [current state / where left off]
2. [Task] — [current state]
3. ...

*Gate: [K] claims — [R] resolved · [U] unresolved · [V] unverified*

### Career Note
[2-3 sentences: competencies exercised, one suggestion for tomorrow]
```

The gate line is mandatory whenever any artifact claim was carried — it makes a
skipped verification pass visible to the user at a glance.

## 4. Capture as Memory

After presenting the wrap-up, write the carry-forward via the runtime — **not**
the Write tool — so every claim-bearing item is stamped with its status from
the verification cache. A stamped file physically cannot say "not sent" about a
claim nobody checked; it says "unverified — confirm or drop?" instead, which is
what tomorrow's briefing should see.

1. Build the items as JSON. Every item that asserts an artifact state carries
   its claim ref; narrative-only items don't:
   ```json
   [
     {"text": "Pre-prod validation for the WRITE DAG", "claim_type": "github_pr",
      "claim_id": "owner/repo#1411", "section": "pickup"},
     {"text": "Send the #eng-ops NATS question", "claim_type": "slack",
      "claim_id": "#eng-ops-review: NATS SG ingress", "section": "pickup"},
     {"text": "Merged PR #1411 — closeout done", "claim_type": "github_pr",
      "claim_id": "owner/repo#1411", "section": "done"},
     {"text": "PR #1049 held by design until WRITE is in prod", "section": "held"}
   ]
   ```
2. Put the freeform narrative (day summary, decisions in force, pattern flags
   for tomorrow — the prose a human actually reads) in a temp file, then:
   ```bash
   python3 ~/.valor/verify.py carry-write --date $(date +%Y-%m-%d) \
     --items-json '<the JSON array>' \
     --narrative-file /tmp/wrapup-narrative.md
   ```
   This writes both `carry-forward-[DATE].md` and `latest.md` atomically,
   replacing any same-date file.
3. **Check the receipt.** If `unregistered_suspects` is non-empty, those lines
   assert artifact states with no registered claim behind them — register the
   real ones (§1.8 step 1) and re-run, or reword the line if it isn't actually
   a claim. Surface anything you leave unregistered to the user in one line.

## 5. Record Evidence

After presenting the wrap-up, record it with a **specific** statement
summarizing the day's key outcomes:

```bash
python3 ~/.valor/evidence_cli.py add \
  --activity wrapup_completed \
  --competency autonomy_scope \
  --statement "Wrap-up: [top accomplishment], [N carry-forward items]. Competency focus: [strongest area today]." \
  --agent valor-evening-wrapup \
  --date $(date +%Y-%m-%d)
```

**Good example:** "Wrap-up: shipped PR #1025 boundary fix, 2 carry-forward
items (pipeline test, design doc draft). Competency focus: subject_matter."

**Bad example:** "Completed evening wrap-up."

If the evidence CLI is unavailable, skip silently -- the wrap-up output
and carry-forward file are the primary outputs.

## 6. Update State

```bash
python3 ~/.valor/evidence_cli.py state-set \
  last_wrapup_date "$(date +%Y-%m-%d)" \
  last_wrapup_timestamp "$(date -Iseconds)"
```

## 7. Fallbacks

| Scenario | Action |
|----------|--------|
| No git activity today | Use conversation context and evidence store only |
| Evidence store empty | Proceed with conversation context and git log |
| Memory file unavailable | Skip memory recall; present wrap-up only |
| Transcript script missing/fails | Skip cross-session scan; use current session + evidence store |
| No Slack tool for send-verification | Register the claims anyway; record nothing — they surface as stale in tomorrow's context worklist |
| `carry-write` fails | Fall back to the Write tool with the same sections; mark every artifact claim "unverified — confirm or drop?" by hand |
| State update fails | Continue; wrap-up is still valid |
