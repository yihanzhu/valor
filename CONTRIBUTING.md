# Contributing

Thanks for helping improve Valor.

## Before You Start

Valor is intentionally opinionated about a few things:

- local-first storage
- privacy-first behavior
- inspectable prompts and logic
- minimal runtime dependencies

If a change pushes against one of those constraints, please explain why in the
PR or issue before implementation.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

Run checks before opening a PR:

```bash
python3 -m pytest -q
python3 -m compileall src tests scripts
```

### Company-info hygiene (required)

Valor is public, so committed files must never contain an employer name,
internal ticket/project keys, colleague names, or non-placeholder emails — use
neutral placeholders (`example.com`, `Alex`/`Sam`, `PROJ-42`). A scanner
(`scripts/check_hygiene.py`) enforces this in two places:

1. **Local git hooks** — block the commit (staged content *and* the commit
   message) before anything is pushed. Enable once per clone:

   ```bash
   git config core.hooksPath .githooks
   cp .hygiene/denylist.example .hygiene/denylist.local   # then edit in YOUR terms
   ```

   `.hygiene/denylist.local` is git-ignored and holds the **exact** sensitive
   terms (one case-insensitive regex per line). It must never be committed — the
   guard can't contain the secret it guards.

2. **CI** — un-bypassable backstops, required to merge. The `hygiene` job
   re-scans tracked files; `hygiene-pr` scans the PR title and description
   (which live on GitHub, not in git). Both read the `HYGIENE_DENYLIST` repo
   secret (Settings → Secrets and variables → Actions); generic rules
   (non-placeholder emails) run even without it.

If a flagged string is a legitimate placeholder/fixture, add a `hygiene:ignore`
comment on that line. Do not bypass the hook with `--no-verify` for real terms.

## Project Conventions

- Runtime code should remain Python stdlib-only unless there is a strong reason
  to add a dependency.
- Keep local-first and privacy-first guarantees explicit in docs and code.
- Avoid hidden network behavior.
- Prefer plain text and inspectable formats over opaque storage where practical.
- If you update installed artifacts or installer behavior, keep `install.sh`,
  `rules/`, and `commands/` consistent.
- Each workflow command declares its integration surface in a
  `<!-- valor:integrations github=… jira=… calendar=… news=… -->` comment near
  its title (values: `required`/`optional`/`none`). The `docs/integrations.md`
  Integration Matrix is checked against those declarations by
  `tests/test_command_docs.py` — change a command's integrations and update both,
  or CI fails.

## Pull Requests

Good PRs usually include:

- a short explanation of the problem
- the design choice or tradeoff behind the fix
- tests for new behavior when practical
- doc updates if user-facing behavior changed

For larger changes, opening an issue or discussion first is helpful.

Unless explicitly agreed otherwise, contributions submitted to this repository
are licensed under Apache-2.0.

## Areas That Need Help

- privacy and trust hardening
- local data ergonomics and exports
- assistant target support beyond the current install flow
- test coverage
- docs and examples

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Valor is meant to support people
in high-trust workflows, and the contributor culture should reflect that.
