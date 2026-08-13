id: pr-review
command: /valor-pr-review
phrase: help me review PR #418
label: PR review coach
act: A day
blurb: Architecture, blast radius, test gaps — and the tone of your own review comments.
---
## Review — #418 payments: jittered exponential backoff for provider retries

3 files, +96/−21. PROJ-244. Your own PR, so this is the pass before Riley's second round.

### Architecture

Moving retry policy from `api/payments_client.py` into `net/transport.py` is the right call, and the
verb check belongs there for exactly the reason your description gives: a future caller can't opt
itself into retrying a POST by accident. The platform team's PROJ-248 needs it in this layer too.

### Behaviour changes the description doesn't mention

- **`api/payments_client.py:12`** — `capture()` now routes through the transport as a `POST`.
  - *Issue:* `_is_retryable()` returns `False` for any non-idempotent verb, so captures no longer
    retry at all. The old `_post_with_retry` gave them 3 attempts on 5xx.
  - *Why:* Captures are the call that most needs a story on provider 5xx. Silently dropping their
    retries during an outage is the opposite of this PR's goal, and it won't show up in tests that
    only exercise `GET`.
  - *Suggestion:* Either give captures an idempotency key and let the transport retry them (you're
    building exactly that on the refund path in #419), or say plainly in the description that
    captures are now fail-fast and confirm that's what you want.

- **`api/payments_client.py:20`** — `fetch_charge()` switched from `POST {}` to `GET`.
  - *Issue:* Right shape, but it's a wire-level change to the provider contract riding along in a
    retry PR.
  - *Suggestion:* Worth its own line in the description, or its own commit — reviewers reading the
    title won't be looking for it.

- **`net/transport.py:14`** — `RETRY_JITTER` is read at import time and only changes the attempt
  count.
  - *Issue:* `retry_with_jitter()` is used whether the flag is on or off, so the flag gates 5-vs-3
    attempts, not jitter. "Behind `PAYMENTS_RETRY_JITTER`, default on in staging only" reads like a
    kill switch it isn't.
  - *Suggestion:* Either branch the delay function on the flag, or rename it to what it controls.

- **`net/transport.py:96`** — `float(retry_after)`.
  - *Issue:* `Retry-After` is allowed to be an HTTP date. A date raises `ValueError` inside the retry
    path, turning a throttle into a crash.
  - *Suggestion:* Parse both forms, or ignore non-numeric values and fall back to the computed delay.

### Test gaps

- No coverage for the case above: a 5xx on a `POST` should not retry, and *that* is the behaviour
  change most likely to surprise someone at 3am. `test_post_is_not_retried` covers a timeout, not a 5xx.
- `test_backoff_is_capped` asserts the cap but not the floor — `random.uniform(0, ceiling)` can return
  ~0, so a "backoff" can be no wait at all. If that's intended, assert it so the next reader knows.
- Nothing exercises `Retry-After` winning over a longer computed delay, which is the interop claim
  in the description.

### Tone check

Your reply to Riley's jitter question ("full jitter, because decorrelated buys nothing when the
retriers aren't correlated to begin with") is correct and reads slightly clipped. Consider giving the
reasoning first and the conclusion second — same content, easier to agree with.

### Before you re-request review

The rollback note is still missing, and your team's checklist asks for one on anything touching the
payments provider. The postmortem roundup in today's briefing is a good citation for why the cap
matters more than the base delay.

✓ Logged as evidence · pr_review_own_scope · subject_matter
