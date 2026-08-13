id: evidence-stats
command: (evidence CLI)
phrase: what does my evidence look like?
label: Look at the local store
act: A day
blurb: The whole product surface is one SQLite file and some plain text under ~/.valor.
---
    $ python3 ~/.valor/evidence_cli.py stats

    {
      "total_entries": 51,
      "by_competency": {
        "collaboration": 15,
        "subject_matter": 15,
        "autonomy_scope": 11,
        "leadership": 8,
        "industry_knowledge": 2
      },
      "this_week": {
        "subject_matter": 4,
        "collaboration": 4,
        "autonomy_scope": 2
      },
      "by_agent": {
        "valor-ambient": 44,
        "valor-wrapup": 3,
        "valor-design-doc": 2,
        "valor-briefing": 1,
        "valor-weekly": 1
      }
    }

51 entries over six months, and 44 of them came from ambient coaching — work that got captured while
you were doing it rather than remembered afterwards. That ratio is the point: the reflection you'd
write at review time is built mostly from moments nobody would have written down.

The 2 under `industry_knowledge` is the honest weak spot. It's why this morning's briefing suggested
going into the partner call with their rate-limit change read.

Everything here is local: `~/.valor/evidence.sqlite` for the entries, `career_framework.md` for the
ladder they're scored against, plain Markdown in `carry-forward/`. No telemetry, no sync, no server —
you can read the whole store with `sqlite3` or delete it with `rm`.
