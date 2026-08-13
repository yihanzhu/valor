id: carry-file
command: (local file)
phrase: show me the carry-forward file
label: Read the handoff it wrote
act: A day
blurb: Tomorrow-you gets a file that can be picked up cold, not a memory of today.
---
    $ cat ~/.valor/carry-forward/carry-forward-2026-08-13.md

    # Carry-forward — 2026-08-13

    ## Shipped today
    - Refund idempotency key threaded through payments/refunds.py (draft #419, 4 commits)
    - Rollback note written; #418 re-requested for review
    - Reviewed and approved #421 — Jordan unblocked
    - Retry cap made configurable, 30s default
    - Provider confirmed idempotency keys are honoured on refunds, 24-hour retention

    ## Pick up tomorrow
    - Finish #419 and take it out of draft. Option A is unblocked now that
      retention is confirmed.
    - Add the 24-hour retention limit to the design doc's non-goals: replays older
      than that are not safe, and nothing in the code says so yet.
    - Review #424 — waiting two days, CI still red, touches the p99 regression.
    - PROJ-262 (webhook-replay integration test) is unassigned and is now the
      natural home for #419's regression test.

    ## Verified before writing
    - #418 — open, review re-requested. Carried as open, NOT as "needs a rollback
      note": that part is done.
    - Provider rate-limit message — sent 15:52 in #checkout. Claim retired.

    ## Open question
    - Should the refund key be the raw event id or a hash including the amount?
      Raw is simpler; a hash catches a replayed id with different contents.

That's the whole file — plain Markdown, on your disk. Tomorrow's briefing reads it back, re-checks each
carried item against its source before re-raising it, and drops whatever turned out to be done.

The detail that matters: the third line under "Verified before writing" would have said "not sent" if
nothing had checked. It got checked, so tomorrow doesn't start with a stale worry.
