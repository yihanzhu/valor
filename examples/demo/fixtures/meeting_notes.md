# Meeting notes (fictional)

<!--
Stands in for notes documents attached to calendar events. The wrap-up captures
these as `meeting_notes` evidence; /valor-prep and /valor-weekly then draw on
them, and /valor-upward-feedback mines the manager behaviours below.
Two sections, matching the `section` field in calendar.json.
-->

## 1:1 — Alex / Sam — {{TODAY-7}}

Attendees: Alex, Sam

- Alex walked through the retry storm and why fixed-interval retries synchronised across pods. Sam asked what the cap should be and pushed back on "as many attempts as it takes" — agreed 5 attempts, 30s cap.
- Sam asked whether the retry policy belongs in the payments client or the transport layer. Alex had assumed the client; Sam suggested checking with the platform team first since they were about to build the same thing. That conversation is what led to the cross-team review on platform-core#415.
- Level conversation: Sam confirmed L4 is the target for the next cycle and named the gap plainly — Alex executes well on assigned work, but hasn't yet owned a problem area where the scope wasn't already decided.
- Sam committed to sharing the written L4 expectations for the team by end of week. (Still not shared as of today.)
- Alex committed to writing the retry contract down before the code, next time there's a cross-team dependency.

Decisions
- retry policy moves to the shared transport layer, not the payments client
- 5 attempts, 30s cap, jitter on

Follow-ups
- Alex: add a rollback note to #418 before merging
- Sam: share the written L4 expectations

## Checkout weekly sync — {{TODAY-1}}

Attendees: Alex, Sam, Riley, Jordan, Dana, PM

- Alex reported the retry work is in review and explained the failure mode in plain terms for the PM: "when the provider slows down, we currently make it worse."
- Jordan flagged that the platform transport migration (PROJ-248) is blocked until #418 lands. Group agreed #418 is the week's critical path.
- Riley raised the p99 regression from address validation (PROJ-259). No owner assigned in the meeting; Alex has it in To Do.
- Dana asked whether refunds could double-apply. Alex confirmed yes — that's PROJ-231, currently in progress as a draft PR.
- PM asked for a date on the provider rate-limit change. Nobody had one; Alex took it to the partner call.

Decisions
- #418 is the critical path this week; other checkout work yields to it
- refund idempotency (PROJ-231) is the next thing after it

Follow-ups
- Alex: get a date from the provider on the rate-limit change
- Riley: file the p99 profiling results on PROJ-259
- Sam: decide whether PROJ-259 needs a dedicated owner
