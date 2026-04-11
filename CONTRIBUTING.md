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
python3 -m compileall src tests
```

## Project Conventions

- Runtime code should remain Python stdlib-only unless there is a strong reason
  to add a dependency.
- Keep local-first and privacy-first guarantees explicit in docs and code.
- Avoid hidden network behavior.
- Prefer plain text and inspectable formats over opaque storage where practical.
- If you update installed artifacts or installer behavior, keep `install.sh`,
  `rules/`, and `commands/` consistent.

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
