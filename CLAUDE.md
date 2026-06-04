# Valor — repository guide for agents

Valor is a **public, open-source** project. Everything committed here is
world-readable.

## Hygiene: never commit company-specific information

Do not put real employer/organization names, internal ticket or project keys,
colleague names, private repo or project codenames, or non-placeholder emails
into **any of**:

- committed files (code, tests, docs, fixtures, examples, comments)
- commit messages
- PR titles and descriptions

Use neutral placeholders instead: `example.com` for emails/domains, names like
`Alex` / `Sam`, ticket keys like `PROJ-42`, PRs like `#123`. When drawing on
real work for an example, translate it to the underlying generic concept first.

This is also enforced mechanically, so a slip is caught rather than shipped —
but treat the rule above as primary; don't rely on the net:

- **Scanner:** `scripts/check_hygiene.py`. Generic rules (non-placeholder
  emails) are built in; the exact sensitive terms load only from out-of-repo
  sources, never from a committed file.
- **Local hooks:** `.githooks/{pre-commit,commit-msg}` block bad staged content
  and commit messages. Activate once per clone:
  `git config core.hooksPath .githooks`. Put real terms in the git-ignored
  `.hygiene/denylist.local` (copy from `.hygiene/denylist.example`).
- **CI (required to merge):** the `hygiene` job scans tracked files and
  `hygiene-pr` scans the PR title+body, both reading the `HYGIENE_DENYLIST`
  secret.

If a flagged string is a genuine placeholder/fixture, add a `hygiene:ignore`
comment on that line. Never bypass the hook with `--no-verify` for real terms.

## Dev basics

- Runtime code stays Python stdlib-only where practical; keep changes
  local-first and privacy-first.
- Before a PR: `python3 -m pytest -q` and
  `python3 -m compileall src tests scripts`.
- When bumping `VERSION`, also run `python3 scripts/check_version_sync.py` — it
  asserts the plugin manifests and website badges match `VERSION` (CI enforces
  it). Don't hand-edit one without the others.
- See `CONTRIBUTING.md` for conventions and `docs/` for architecture.
