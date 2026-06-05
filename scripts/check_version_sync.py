#!/usr/bin/env python3
"""Assert every "current version" declaration in the repo matches VERSION.

Bumping VERSION doesn't automatically propagate to the plugin manifests, the
website badges, or the OG share image — which is how the plugin manifests
silently sat at 0.3.0 while VERSION had moved to 0.6.x. This check fails if any
of those declarations disagree with VERSION, so the drift can't ship.

Intentionally NOT checked (these aren't "current version" declarations):
  * ROADMAP.md / docs/adr-*.md — they record version *history*.
  * PRIVACY.md "e.g. 0.6.1" — an illustrative example.
  * architecture.md "schema version N" — the state-schema version is a
    different number from the app version.

Usage: python3 scripts/check_version_sync.py   (run from the repo root)
Exit code 1 on any mismatch.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Plugin manifests whose "version" field must equal VERSION exactly.
MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
# Files whose every `vX.Y.Z` badge token must equal "v" + VERSION.
BADGE_GLOBS = ("website/*.html", "website/*.svg")
BADGE_RE = re.compile(r"v\d+\.\d+\.\d+")


def check(root: Path):
    """Return a list of mismatch messages (empty list == all in sync)."""
    version = (root / "VERSION").read_text().strip()
    badge = f"v{version}"
    problems = []

    for rel in MANIFESTS:
        path = root / rel
        if not path.exists():
            continue
        try:
            got = json.loads(path.read_text()).get("version")
        except json.JSONDecodeError:
            problems.append(f"{rel}: invalid JSON")
            continue
        if got != version:
            problems.append(f'{rel}: "version" = {got!r} != VERSION {version!r}')

    for pattern in BADGE_GLOBS:
        for path in sorted(root.glob(pattern)):
            for token in BADGE_RE.findall(path.read_text()):
                if token != badge:
                    problems.append(f"{path.relative_to(root)}: badge {token!r} != {badge!r}")

    # State-schema version: architecture.md's stated version must match the code
    # (STATE_SCHEMA_VERSION) — a different number from the app version, but it
    # drifts the same way when a schema bump skips the docs.
    src = root / "src" / "evidence_cli.py"
    arch = root / "docs" / "architecture.md"
    if src.exists() and arch.exists():
        code = re.search(r"STATE_SCHEMA_VERSION\s*=\s*(\d+)", src.read_text())
        doc = re.search(r"currently at version (\d+)", arch.read_text())
        if code and doc and code.group(1) != doc.group(1):
            problems.append(
                f"docs/architecture.md: schema 'version {doc.group(1)}' != "
                f"STATE_SCHEMA_VERSION {code.group(1)}"
            )

    return problems


def main() -> int:
    version = (ROOT / "VERSION").read_text().strip()
    problems = check(ROOT)
    if problems:
        print(f"version-sync: MISMATCH against VERSION={version}")
        for p in problems:
            print(f"  {p}")
        print("Fix these to match VERSION (or bump VERSION).")
        return 1
    print(f"version-sync: OK (all version declarations == {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
