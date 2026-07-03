# Valor Upward Feedback

<!-- valor:integrations github=none jira=none calendar=none news=none -->

Assemble a **draft of upward feedback about your manager** for a review cycle,
grounded in manager behaviors you actually observed — pulled from the meeting notes
and 1:1 records already in your evidence log — not generic praise. Generate-only:
you review, correct, and paste it into your feedback tool yourself.

This is **feedback about your manager**, which is a different data need from the rest
of Valor:

- **not** `/valor-prep` (that prepares *your* update *for* the manager 1:1), and
- **not** `/valor-reflection` (that's your self-review).

Valor has no dedicated "manager behaviors" signal, so this mines what was captured
incidentally — `meeting_notes` entries (recorded at wrap-up) and 1:1 evidence. Its
quality depends on what those captured, so it is honest about thin evidence rather
than inventing behaviors.

## When to Use

- User says: "upward feedback", "feedback about my manager", "manager feedback",
  "review my manager", or runs `/valor-upward-feedback`
- Around a review cycle, when the review asks for feedback on your manager. No
  auto-suggestion — run on demand.

## 1. Define the window

Establish one explicit date window (usually the same cycle as `/valor-reflection`)
and reuse it. Ask the user if it isn't clear:

- `cycle_start` / `cycle_end` (`YYYY-MM-DD`).

## 2. Gather manager-observed signals

Pull the window's evidence and keep the entries that could reveal manager behavior:

```bash
python3 ~/.valor/evidence_cli.py export --from <cycle_start> --to <cycle_end> --format json
```

Focus on:

- **`meeting_notes` entries** — per-meeting summaries (with links) captured at
  wrap-up; 1:1s and project syncs are where a manager's decisions, direction, and
  coaching show up. Follow a link when you need detail.
- **1:1 records** — any `one_on_one`-related entries.

If a running 1:1 doc is configured (`context.one_on_one_doc_set` is true), also read
it for the manager's comments, direction, and decisions over the window. Use
`evidence_cli.py search "<term>"` to pull specific threads if helpful.

## 3. Extract concrete manager behaviors

From those signals, identify **specific things the manager did** — each tied to a
real instance (a dated 1:1, a decision in a sync), not a generic trait. Look for
both strengths and growth areas:

- Unblocked you / removed obstacles; gave clear (or unclear) direction and
  priorities; coached or grew you; made or drove (or delayed) decisions; advocated
  for / sponsored your work; gave useful feedback; connected you to the right people;
  protected your focus.

Only include a behavior you can point to in the evidence or the 1:1 doc. If you infer
a pattern, tie it to the instances that support it.

## 4. Draft the upward feedback

Two constructive, skip-level-readable sections, each point grounded in a concrete
instance:

- **What your manager does well** — 2–3 strengths, each with the instance that shows it.
- **What they could do more of / differently** — framed constructively (the behavior
  and its impact on you/the team), each grounded in a real example.

Keep it fair and specific — feedback a calibration reader can act on, not vague praise
or complaint.

## 5. Be honest about thin evidence — do NOT invent

If the log holds little manager-observed signal (few `meeting_notes`, no 1:1 doc),
**say so** — output what you can support and add a short note: "Thin manager-behavior
evidence for this window; add specifics from memory." Never fabricate a manager
behavior or attribute one the evidence doesn't support. A gap is a prompt to the user,
not a blank to fill.

## 6. Output for review (do NOT auto-write)

Print the draft for the user to read, correct, and paste into their feedback tool
themselves. Do **not** write to any doc or send anything.

Because it's pasted into tools that render markdown literally, emit it as
**plain text — no `*`, `**`, `_`, or `#`** (a plain leading `- ` for a list item is
fine, `*` is not). Close with a one-line offer to revise once the user adds any
missing detail.

## Notes

- **About the manager, not for them.** Distinct from `/valor-prep`.
- **Generate-only.** Never write or send; the user proofs and pastes.
- **No fabrication.** Only manager behaviors grounded in the evidence or 1:1 doc; thin
  evidence is flagged, not filled.
- Recording evidence is usually unnecessary here (this reads, it doesn't produce a
  deliverable); skip it unless the session itself surfaced something worth keeping.
