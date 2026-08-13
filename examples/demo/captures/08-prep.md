id: prep
command: /valor-prep
phrase: prep for 1:1
label: 1:1 prep
act: A week
blurb: Drafted in your own 1:1 doc's format, with anything chronically stuck escalated instead of re-listed.
---
Your doc keeps a pinned block, then one dated entry per week: Goals this week, Progress, Blockers,
Asks, Feedback — plain lines, no bold. Here is next week's entry in that shape, ready to paste.

## 2026-08-17

Goals this week
- land #419 (refund idempotency) — the design is settled and the provider confirmed 24-hour key retention
- take PROJ-259 from "nobody's" to owned, with a plan I wrote
- review #424, which has been waiting since Tuesday

Progress
- retry backoff (#418) is in review with the rollback note attached; it unblocks Jordan's PROJ-248
- refund design is done: idempotency key at the provider boundary, same pattern as the charge path
- partner call answered the blocking design question — keys are honoured on refunds, 24-hour window
- the retry cap is configurable now, with 30s as the default

Blockers
- Riley's profiling results on PROJ-259 — outstanding three weeks running

Asks
- I would like PROJ-259 as mine end to end: I have the trace and nobody owns it. That is the closest
  thing on the board to the "own a problem area where the scope isn't decided" gap from our 1:1.
- The written L4 expectations you mentioned three weeks ago would help me self-check between these.

Feedback
- The suggestion to check with platform before building the retry layer changed the design before it
  was built, not after. More of that would be useful.

---

Supporting analysis, for you rather than the doc:

Evidence this cycle: 51 entries. Collaboration 15, Subject Matter 15, Autonomy & Scope 11,
Leadership 8, Industry Knowledge 2.

Trend across the last three weekly summaries: execution is consistently strong, cross-team contact
comes in bursts around reviews, and Industry Knowledge was flat at zero until yesterday's partner
call.

Chronic item — escalating rather than re-listing: Riley's PROJ-259 profiling has been carried for
three weeks and is now past your escalation threshold. It is the third week in a row this appears
under Blockers, which is the pattern worth naming out loud rather than logging again.

Also carried three weeks: Sam's commitment to share the written L4 expectations. It is in the Asks
above phrased as a request, not a complaint — you asked me to keep that one visible.

Capacity note: next week has no days off and no holidays, so three goals is a real week's work.

✓ Logged as evidence · one_on_one_prep · collaboration
