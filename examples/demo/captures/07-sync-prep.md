id: sync-prep
command: /valor-sync-prep
phrase: sync prep
label: Project sync prep
act: A week
blurb: Team-facing talk points for the sync the briefing already reserved time for. Plain text, pastes clean.
---
Checkout weekly sync — Thursday 14:00. Talk points, plain text so it pastes into the shared notes.

PROGRESS SINCE LAST SYNC

Retry backoff (PROJ-244, #418) is in review with one round answered. Retries now back off with
jitter and stop synchronising across pods, capped at 30s. The cap is configurable as of today.
This is the item the group named as the critical path last week, and it is one review away.

Refund double-apply (PROJ-231, #419) is a draft. The design is settled: idempotency key at the
provider boundary, same pattern as the charge path from PROJ-186.

Provider error codes (PROJ-238) shipped Tuesday. It is what made the retry storm legible in the
first place, so the debugging that follows gets easier.

DECISIONS TO LAND

1. Captures are fail-fast under this PR. Retries only apply to idempotent verbs, so a provider 5xx
   on a capture now fails immediately instead of retrying three times. Either we accept that until
   captures get idempotency keys, or #418 waits for them. Recommend accepting it and tracking the
   keys as follow-up work.

2. PROJ-259 needs an owner. The p99 regression has been open since the address-validation rollout,
   there is a trace pointing at a synchronous call in the hot path, and it is still nobody's.

OPEN QUESTIONS

- Riley's profiling results on PROJ-259: still outstanding, and the ticket cannot be planned without
  them.
- The provider's new per-tenant rate limits land next quarter. Our retry budget was sized against
  today's limits. Who owns re-checking that, and when?

WHAT I NEED FROM THE ROOM

Jordan is blocked on PROJ-248 until #418 merges. If anyone can review it today, that unblocks a
second person's week, not just mine.

✓ Logged as evidence · sync_prep_completed · collaboration
