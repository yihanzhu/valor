# Carry-forward — {{TODAY-1}}

<!--
Fictional wrap-up note from "yesterday", seeded so the first briefing of the
demo has something to carry forward - and something for the verification gate
to check before it re-raises anything.
-->

## Shipped today

- Answered Riley's review comments on #418 (jitter choice, cap semantics)
- Landed the webhook-replay test that reproduces the double refund
- Reported the retry work in the checkout sync; #418 named the week's critical path

## Carry forward → tomorrow

- Finish threading the idempotency key through `payments/refunds.py` (PROJ-231, draft #419)
- Add the rollback note to #418 before asking for the final review
- Get a date from the provider on the rate-limit change — asked in #checkout, not sent yet
- Riley owes profiling results on PROJ-259 before it can be planned

## Open questions

- Does the refund idempotency key belong on the provider call or our own write? Leaning provider boundary.

## Reflection

Good execution day, all inside already-scoped work. Nothing today moved the "own a
problem area where the scope isn't decided" gap Sam named in the 1:1.
