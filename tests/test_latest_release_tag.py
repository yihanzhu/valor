"""Tests for the release-tag resolver (scripts/latest_release_tag.py).

Covers the three behaviours the update path depends on: semver-aware ordering
(not lexicographic), skipping pre-releases, and the no-tags fallback.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "latest_release_tag.py"
_spec = importlib.util.spec_from_file_location("latest_release_tag", _SCRIPT)
lrt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lrt)

f = lrt.latest_release_tag


# --- semver-aware ordering (NOT lexicographic) ---

def test_picks_highest_semver_not_lexicographic():
    # Lexicographically "v0.9.0" sorts after "v0.10.0"; semver says the opposite.
    assert f(["v0.9.0", "v0.10.0", "v0.2.0"]) == "v0.10.0"


def test_compares_all_three_fields_numerically():
    assert f(["v1.0.0", "v1.0.9", "v1.0.10", "v1.2.0", "v2.0.0"]) == "v2.0.0"
    assert f(["v0.16.0", "v0.16.1", "v0.15.9"]) == "v0.16.1"


def test_double_digit_patch_beats_single_digit():
    assert f(["v0.16.9", "v0.16.10"]) == "v0.16.10"


# --- pre-releases are skipped ---

def test_skips_prereleases():
    assert f(["v1.2.3", "v1.3.0-rc.1", "v1.3.0-beta"]) == "v1.2.3"


def test_prerelease_only_yields_nothing():
    assert f(["v2.0.0-rc.1", "v2.0.0-alpha"]) is None


# --- no-tags fallback ---

def test_no_tags_returns_none():
    assert f([]) is None


def test_ignores_non_release_tags():
    assert f(["nightly", "latest", "v1.2", "1.2.3", "v1.2.3.4"]) is None
    assert f(["nightly", "v1.2.3", "foo"]) == "v1.2.3"


# --- input formats ---

def test_parses_git_ls_remote_lines():
    lines = [
        "0123abc\trefs/tags/v0.16.0",
        "4567def\trefs/tags/v0.16.0^{}",
        "89abcde\trefs/tags/v0.17.0",
        "ffff000\trefs/tags/v0.17.0^{}",
    ]
    assert f(lines) == "v0.17.0"


def test_parses_git_tag_list_lines_with_whitespace():
    assert f(["  v1.0.0  ", "v1.1.0\n", ""]) == "v1.1.0"


# --- end-to-end CLI (the no-tags path the installer relies on) ---

def _run(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
    )

def test_cli_prints_tag():
    res = _run("v0.15.0\nv0.16.0\n")
    assert res.returncode == 0
    assert res.stdout.strip() == "v0.16.0"


def test_cli_no_tags_is_clean_noop():
    # Safety-critical: empty stdin -> empty stdout, exit 0 (installer no-ops).
    res = _run("")
    assert res.returncode == 0
    assert res.stdout.strip() == ""
