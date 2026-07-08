# North star

The single goal Valor is steering toward, owned by this repo. Fabrica's tooling reads the
active north star from here to debate proactive proposals against Valor's own goal.

**One north star is active at a time.** On a transition, mark the achieved one `achieved` and
promote (or add) the next as `active`; keep the log below.

---

## Current north star

### Harden Valor for a broad open-source launch  ·  status: **active**

Get the existing, working Valor tool (v0.16.0) to launch quality for strangers: accurate
onboarding, trustworthy releases, and a framework setup a newcomer can complete without a
written career ladder. This is the current corporate-engineering-IC tool made ready for public
adoption — deliberately distinct from the longer-horizon generalization work (a growth coach
for everyone whose work is agent-legible), which is **out of scope** for this north star.

- **Why it's the north star:** Valor is influence-first, and a broad OSS launch is how it earns
  adoption and trust. But today a stranger gets a poor or untrustworthy first run — stale
  plugin-marketplace onboarding, command drift in the docs, and auto-update tracking `main` —
  and a newcomer without a career ladder has no example to start from.
- **Done-signal:** all four hold — (1) the plugin-marketplace first-run is accurate and
  delegates real setup to `/valor-setup`; (2) ADR-001 reflects the shipped command set; (3) the
  version-check and auto-update follow tagged releases, not `main`, with a documented "read the
  script / pin a version" note; (4) two to three neutral example career frameworks ship and are
  offered during setup.
- **Safety note:** public, world-readable repo — no real employer / org / colleague names or
  non-placeholder emails in any artifact (the hygiene scanner enforces it). Auto-update changes
  touch the path every user runs, so that change goes to the human merge gate.

---

## North-star log

- **Harden Valor for a broad open-source launch** — *active (set 2026-07-08).* Scope: the four
  Track A launch-blocker fixes above. Retire on the done-signal; the next candidate is the
  Track B generalization, once its build gate clears.

### Vetoed-but-Faber-thought-relevant (manager-debate filtered these out)

- _(none yet)_
