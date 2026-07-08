#!/usr/bin/env python3
"""Resolve the latest Valor release tag from a list of git tags.

Valor releases are tagged ``vX.Y.Z`` (matching ``VERSION``'s ``X.Y.Z``). The
update path (``install.sh --auto-update`` / ``--upgrade`` / ``--clone``) tracks
the latest such tag rather than ``main`` HEAD, so every user runs a *released*
version -- not whatever was last pushed.

"Latest" is resolved **semver-aware** (numeric field comparison, NOT
lexicographic -- so ``v0.10.0`` > ``v0.9.0``) and **pre-releases are skipped**
(anything with a suffix after the patch number, e.g. ``v1.2.3-rc.1``); those
must never be auto-applied.

Usage:
    git tag --list | python3 scripts/latest_release_tag.py

Reads candidate tags from stdin (one per line; ``git tag --list`` *or*
``git ls-remote --tags`` output both work) and prints the single latest release
tag, or nothing (exit 0) when there are no release tags yet -- the caller treats
empty output as "no release to track" and no-ops, never falling back to main.
"""

from __future__ import annotations

import re
import sys
from typing import Iterable, Optional

# Exact vX.Y.Z -- no pre-release/build suffix. Pre-releases are intentionally
# excluded from the auto-update path.
_RELEASE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _normalize(token: str) -> str:
    """Reduce a raw git ref line/token to a bare tag name."""
    token = token.strip()
    if not token:
        return ""
    # `git ls-remote --tags` lines look like "<sha>\trefs/tags/v1.2.3"; take the
    # last whitespace-separated field so both that and plain `git tag` output work.
    token = token.split()[-1]
    if token.startswith("refs/tags/"):
        token = token[len("refs/tags/"):]
    # A dereferenced annotated tag adds a "^{}" peel suffix in ls-remote output.
    if token.endswith("^{}"):
        token = token[: -len("^{}")]
    return token


def latest_release_tag(lines: Iterable[str]) -> Optional[str]:
    """Return the highest ``vX.Y.Z`` release tag in *lines*, or ``None``."""
    best_key = None
    best_tag = None
    for line in lines:
        tag = _normalize(line)
        m = _RELEASE_RE.match(tag)
        if not m:
            continue
        key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if best_key is None or key > best_key:
            best_key = key
            best_tag = tag
    return best_tag


def main() -> int:
    tag = latest_release_tag(sys.stdin)
    if tag:
        print(tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
