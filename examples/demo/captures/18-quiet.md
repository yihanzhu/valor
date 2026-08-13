id: quiet
command: (ambient control)
phrase: valor quiet
label: Turn the coaching off
act: Setup
blurb: Three words to silence it. The point is that it's easy to refuse.
---
Coaching off for this conversation. I'll keep working normally and stop adding footers.

The three controls, so you know what you're agreeing to:

- **`valor quiet`** — silences coaching for this conversation only. The next session starts normal.
- **`valor off`** — silences it until you say `valor on`. Persisted in `state.json`, so it survives
  restarts.
- **`valor on`** — back to normal.

Evidence recording follows the same switch. With coaching off, nothing gets written to the store, so a
quiet session leaves no trace in your history either.

Worth being blunt about why this exists: a coach that can't be told to be quiet turns into a nag, and a
nag gets uninstalled. The commands you invoke on purpose — the briefing, the reviews, the reflections —
still work while quiet. It's only the unrequested footers that stop.
