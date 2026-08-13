id: design-doc
command: /valor-design-doc
phrase: design doc for PROJ-231
label: Design doc coach
act: A day
blurb: Options with trade-offs, a recommendation, and an explicit list of what you're not doing.
---
## Refund idempotency — PROJ-231

### Problem statement

The provider redelivers refund webhooks when our response is slow. We apply the refund per delivery,
so a slow response can refund a customer twice. Two deliveries of the same event must produce one
refund.

### Background

We ack the webhook *after* applying the refund. To the provider a slow apply looks like a failed
delivery, so it redelivers — and the second delivery finds no record that the first one succeeded.
The charge path already solved a version of this in PROJ-186 with idempotency keys at the provider
boundary.

### Goals

- Two deliveries of the same refund event result in one refund, including when our own write succeeded
  but the ack never landed
- No change to the provider's retry behaviour required — we can't control it
- Safe to replay historical events without refunding again

### Non-goals

- Deduplicating *all* webhook types. Refunds first; the pattern can spread later.
- Multi-provider support. One provider, one contract, until there's a second.
- Reordering the ack. Acking before applying trades double-refunds for lost refunds; that's a worse
  failure, and it's out of scope here.

### Option A — Idempotency key at the provider boundary

Derive a key from the provider's event id and send it on the refund call. The provider collapses
duplicates for us.

- **For:** matches PROJ-186, so one pattern covers charges and refunds. Safe even if our write
  succeeded and the ack didn't — the provider is the arbiter, not our database.
- **Against:** depends on the provider honouring keys for refunds (documented, unverified by us).
  Their key retention window bounds how long a replay stays safe.

### Option B — Dedupe table keyed by event id

Insert the event id before applying; a duplicate insert means we've seen it and can ack immediately.

- **For:** entirely ours, testable offline, no provider assumptions.
- **Against:** the write and the refund aren't atomic. Crash between them and the event looks handled
  when it isn't — trading a double refund for a silently dropped one. Needs a reconciliation job to
  be honest, which is a second moving part.

### Option C — Queue with an at-least-once worker

Ack immediately, enqueue, let a worker apply with its own dedupe.

- **For:** decouples our latency from the provider's redelivery clock, which removes the trigger.
- **Against:** the largest change, and it needs the dedupe from B anyway. Solves latency, not identity.

### Recommendation

**Option A**, with the event id as the key source. It reuses a pattern the team already reviewed,
puts the arbiter outside our failure domain, and is a two-file change. Verify the provider's key
retention against their docs before committing, and if refunds turn out not to honour keys, fall back
to B plus reconciliation rather than C.

### Testing strategy

- Replay the same webhook twice end to end; assert one refund and two 200s
- Crash-inject between our write and the ack; assert replay still nets one refund
- Assert a distinct event id for the same charge still refunds (guard against over-collapsing)
- The integration test from PROJ-262 is the natural home for the first case; it's unassigned and
  adjacent to this work

### Open questions

1. Does the provider honour idempotency keys on refunds, and for how long? (Blocking — ask on today's
   16:30 call.)
2. Should the key be the raw event id or a hash including the amount? Raw is simpler; a hash catches
   a provider replaying an event id with different contents.
3. Who owns the reconciliation report if we ever fall back to B?

#### 🦅 Valor | Autonomy & Scope · Craftsmanship

✅ *What you did:* Framed a correctness problem as options with a recommendation and wrote down what
you're deliberately not doing — the non-goals are the part most people skip.

🎯 *L4 would also:* Land question 1 before the code. You have the provider on a call today; a design
whose blocking unknown gets answered by the author's own meeting is a design that doesn't need a
second review round.

✓ Logged as evidence · design_doc_written · autonomy_scope · role: led
