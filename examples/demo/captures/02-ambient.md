id: ambient
command: (no command — always on)
phrase: the retry cap should be configurable, not hardcoded at 30s
label: Ambient coaching
act: A day
blurb: You didn't ask for coaching. It classifies the work, ties it to your target level, and records the evidence.
---
Done — `MAX_DELAY` now reads from the environment with 30s as the default:

    -MAX_DELAY = 30.0
    +MAX_DELAY = float(os.environ.get("PAYMENTS_MAX_RETRY_DELAY", "30"))

Two things worth knowing about the change:

- `retry_with_jitter()` already clamps `Retry-After` to `MAX_DELAY`, so raising the ceiling raises
  how long a provider can hold you. That's the intended lever, but it's now a lever anyone with
  deploy access can pull without a review.
- It's read at import time, like `RETRY_JITTER` above it. Changing either needs a restart, not just
  a config push. Worth a line in the rollback note so nobody expects a live flip.

I left the 30s default in place, so current behaviour is unchanged.

#### 🦅 Valor | Subject Matter Expertise · Craftsmanship

✅ *What you did:* Turned a hardcoded constant into a bounded, defaulted config value and named the
blast radius of the knob rather than just shipping it — that's the L4 "sound trade-offs" line.

🎯 *L4 would also:* Say where the value should live long-term. An env var read at import is fine for
one operator; a retry budget that two teams tune is a config surface, and you already have the
platform conversation open for it (PROJ-248).

✓ Logged as evidence · code_written · subject_matter · role: built
