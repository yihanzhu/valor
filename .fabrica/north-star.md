# North star

The single goal Valor is steering toward, owned by this repo. Fabrica's tooling reads the
active north star from here to debate proactive proposals against Valor's own goal.

**One north star is active at a time.** On a transition, mark the achieved one `achieved` and
promote (or add) the next as `active`; keep the log below.

---

## Current north star

### Harden Valor for a broad open-source launch  ·  status: **achieved**

Get the existing, working Valor tool to launch quality for strangers: accurate onboarding,
trustworthy release/update behavior, and a framework setup a newcomer can complete without a
written career ladder. This was the current corporate-engineering-IC tool made ready for public
adoption — deliberately distinct from the longer-horizon generalization work (a growth coach
for everyone whose work is agent-legible), which was **out of scope** for this north star.

- **Why it was the north star:** Valor is influence-first, and a broad OSS launch is how it
  earns adoption and trust. A stranger previously got a poor or untrustworthy first run — stale
  plugin-marketplace onboarding, command drift in the docs, and updates tracking `main` — and a
  newcomer without a career ladder had no example to start from.
- **Done-signal (all met):** (1) the plugin-marketplace first-run is accurate and delegates real
  setup to `/valor-setup` (#59); (2) ADR-001 reflects the shipped command set (#61); (3) the
  update path no longer silently tracks `main` — the version-check **notifies** about new tagged
  releases, with documented read-the-script + pin-a-version guidance (robust silent auto-apply
  intentionally deferred to #67) (#65); (4) neutral example career frameworks ship and are
  offered during setup (#64).
- **Safety note:** public, world-readable repo — no real employer / org / colleague names or
  non-placeholder emails in any artifact (the hygiene scanner enforces it).

---

## North-star log

- **Harden Valor for a broad open-source launch** — *achieved 2026-07-24* (set 2026-07-08).
  Shipped via #59, #61, #64, #65 (+ #69 restored a green `main`: version sync to 0.17.0,
  `/valor-pr-console` registration, pinned ruff). Done-signal ③ was met as **notify-only**
  (updates notify about new releases + pin / read-the-script); robust silent auto-apply was
  deliberately deferred to #67. **No active north star is set now** — the next candidate is the
  Track B generalization (a growth coach for everyone whose work is agent-legible), gated on its
  de-risk work; set + approve it to re-enable proactive mode.

### Vetoed-but-Faber-thought-relevant (manager-debate filtered these out)

- _(none yet)_
