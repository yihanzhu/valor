"""Tests for the release-tag resolver (scripts/latest_release_tag.py).

Covers the behaviours the notify-only update check depends on: semver-aware
ordering (not lexicographic), skipping pre-releases, the no-tags fallback, and
the strictly-newer "is an update available" decision behind the notification.
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
ua = lrt.update_available


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


# --- notify decision: is a strictly-newer release available? ---

def test_update_available_returns_newer_tag():
    assert ua("0.15.0", ["v0.14.0", "v0.15.0", "v0.16.0"]) == "v0.16.0"


def test_update_available_equal_version_is_none():
    # Already current -> nothing to surface (no notification).
    assert ua("0.16.0", ["v0.15.0", "v0.16.0"]) is None


def test_update_available_older_tag_is_none():
    # Installed is ahead of the newest release (e.g. an unreleased main build):
    # notify-only never surfaces a downgrade.
    assert ua("0.16.0", ["v0.15.0"]) is None


def test_update_available_no_release_tags_is_none():
    assert ua("0.16.0", ["nightly", "latest", "v0.17.0-rc.1"]) is None


def test_update_available_semver_not_lexicographic():
    # v0.10.0 > v0.9.0 numerically, so an install on 0.9.0 gets notified.
    assert ua("0.9.0", ["v0.9.0", "v0.10.0"]) == "v0.10.0"


def test_update_available_unknown_installed_surfaces_release():
    # A garbage/unknown installed version still points at a real release.
    assert ua("unknown", ["v0.16.0"]) == "v0.16.0"


def test_update_available_prefixed_installed_is_accepted():
    assert ua("v0.15.0", ["v0.16.0"]) == "v0.16.0"


# --- end-to-end CLI (the no-tags path the installer relies on) ---

def _run(stdin: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
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


def test_cli_installed_prints_only_when_newer():
    # Notify mode: strictly newer -> print the tag.
    res = _run("v0.16.0\nv0.17.0\n", "--installed", "0.16.0")
    assert res.returncode == 0
    assert res.stdout.strip() == "v0.17.0"


def test_cli_installed_up_to_date_is_silent_noop():
    # Notify mode: already current -> empty stdout, exit 0 (installer stays quiet).
    res = _run("v0.16.0\n", "--installed", "0.16.0")
    assert res.returncode == 0
    assert res.stdout.strip() == ""
