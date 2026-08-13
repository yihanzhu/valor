# Alex <> Sam — 1:1

<!--
Fictional running 1:1 doc for the Valor demo profile. Two jobs in the demo:
  1. /valor-prep drafts this week's entry in THIS doc's format (pinned block +
     dated entries, plain sentences, no bold headers inside entries).
  2. The briefing silently extracts "Goals this week" into
     prioritization.week_goals and ranks the day against it.
-->

## Pinned

Current level: L3, targeting L4 by the next cycle.
Focus area: checkout/payments reliability.
Growth themes Sam and Alex agreed on:
- own a feature area end to end, not just assigned tickets
- write the design down before building when more than one team is affected
- review outside your own tickets

Standing agenda: goals for the week, progress, blockers, asks, feedback.

---

## {{MONDAY}}

Goals this week
- land the refund idempotency fix (PROJ-231) — this is the one that matters
- get the retry backoff PR (#418) merged, with a rollback note
- start the p99 investigation (PROJ-259) if there's room

Progress
- retry backoff PR is open and has been through one round with Riley
- provider error codes shipped (PROJ-238), which is what made the retry storm legible in the first place

Blockers
- PROJ-248 (platform's transport migration) is waiting on #418 landing; Jordan is blocked until it does

Asks
- can we talk about what "owning a feature area" looks like concretely for payments?

Feedback
- the written retry contract was useful for the platform team — Sam suggested doing that earlier next time, before the code rather than after

---

## {{LAST_MONDAY}}

Goals this week
- unblock the platform team's transport work
- get provider errors visible in the failure log

Progress
- reviewed platform-core#415 and flagged where the retry layer should live; that changed their design before it was built
- PROJ-238 merged

Blockers
- none

Asks
- none

Feedback
- Sam noted the cross-team review as the strongest L4 signal so far this cycle
