#!/usr/bin/env python3
"""Resolve the latest Valor release tag from a list of git tags.

Valor releases are tagged ``vX.Y.Z`` (matching ``VERSION``'s ``X.Y.Z``). The
update check is **notify-only**: it tells you when a newer release than your
installed version exists -- it never silently tracks ``main`` HEAD or checks
anything out for you; updating is manual. This module is the shared, pure
implementation of "which tag is latest / is it newer", used by that check and by
the documented pin command.

"Latest" is resolved **semver-aware** (numeric field comparison, NOT
lexicographic -- so ``v0.10.0`` > ``v0.9.0``) and **pre-releases are skipped**
(anything with a suffix after the patch number, e.g. ``v1.2.3-rc.1``); those are
never surfaced as an available update.

Usage:
    # latest release tag (used by the documented pin command):
    git tag --list | python3 scripts/latest_release_tag.py
    # notify check -- print the latest tag ONLY when newer than the installed one:
    git ls-remote --tags <origin> | python3 scripts/latest_release_tag.py --installed 0.16.0

Reads candidate tags from stdin (one per line; ``git tag --list`` *or*
``git ls-remote --tags`` output both work) and prints the single latest release
tag, or nothing (exit 0) when there are no release tags yet -- the caller treats
empty output as "no release to surface" and no-ops, never falling back to main.
"""

from __future__ import annotations

import argparse
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


def _version_key(text: Optional[str]):
    """Parse a bare or ``v``-prefixed ``X.Y.Z`` into a comparable tuple, or
    ``None`` when it is not an exact release version (e.g. ``"unknown"``)."""
    if not text:
        return None
    m = _RELEASE_RE.match(text.strip() if text.startswith("v") else "v" + text.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def update_available(installed: str, lines: Iterable[str]) -> Optional[str]:
    """Return the latest release tag when it is **strictly newer** than
    *installed*, else ``None`` -- the decision behind the notify-only update
    check. *installed* is the running version (bare ``X.Y.Z`` from ``VERSION``);
    *lines* are candidate tags. ``None`` means "nothing to surface": up to date,
    only older/equal tags, or no release tagged yet. An unparseable *installed*
    (e.g. ``"unknown"``) still surfaces any real release, since something is off
    and a released version exists to point at."""
    tag = latest_release_tag(lines)
    if tag is None:
        return None
    installed_key = _version_key(installed)
    if installed_key is None:
        return tag
    return tag if _version_key(tag) > installed_key else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the latest Valor release tag from tag lines on stdin.",
    )
    parser.add_argument(
        "--installed",
        metavar="X.Y.Z",
        default=None,
        help="Notify mode: print the latest tag only when it is strictly newer "
        "than this installed version; otherwise print nothing.",
    )
    args = parser.parse_args(argv)
    if args.installed is not None:
        tag = update_available(args.installed, sys.stdin)
    else:
        tag = latest_release_tag(sys.stdin)
    if tag:
        print(tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
