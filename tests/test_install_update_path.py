"""Tests for install.sh's release-tag update path (the shell resolver + guards).

The Python resolver (scripts/latest_release_tag.py) is tested separately in
test_latest_release_tag.py. install.sh carries its OWN git/shell-native resolver
and checkout guard (deliberately self-contained, so it works against an old
~/.valor/repo that predates that script). These tests exercise THAT shell code.

Two layers:
  1. Unit tests of the helper functions (resolve_latest_release_tag,
     checkout_release_tag, version_gt) extracted from install.sh and sourced.
  2. An end-to-end test of the flagged --clone regression: when a release tag
     resolves but the checkout fails (dirty tree), the installer must ABORT and
     never fall through to installing the stale/main/dirty checkout.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"

# Hermetic git: ignore the developer's global/system config and pin identity so
# commits/clones behave identically everywhere (CI included).
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available"
)


# --- git plumbing helpers ---------------------------------------------------

def _g(cwd: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", *args], cwd=str(cwd), env=GIT_ENV,
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"git {args} failed: {res.stderr}"
    return res.stdout.strip()


def _make_origin(tmp: Path, *, base="v1", tags=(), main_content=None) -> Path:
    """Create a bare 'origin' repo. First commit holds `base`; each name in
    `tags` is tagged at that commit. If `main_content` is given, a second commit
    changes the tracked file to it (so the tag and the branch tip differ)."""
    bare = tmp / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare)], env=GIT_ENV,
                   check=True, capture_output=True)
    seed = tmp / "seed"
    subprocess.run(["git", "init", str(seed)], env=GIT_ENV,
                   check=True, capture_output=True)
    (seed / "marker").write_text(base)
    _g(seed, "add", "-A")
    _g(seed, "commit", "-m", "c1")
    for t in tags:
        _g(seed, "tag", t)
    if main_content is not None:
        (seed / "marker").write_text(main_content)
        _g(seed, "add", "-A")
        _g(seed, "commit", "-m", "c2")
    branch = _g(seed, "rev-parse", "--abbrev-ref", "HEAD")
    _g(seed, "remote", "add", "origin", str(bare))
    _g(seed, "push", "origin", branch, "--tags")
    # Make the bare repo's default branch match what we pushed, so a plain clone
    # checks something out.
    _g(bare, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    return bare


def _clone(bare: Path, dest: Path) -> Path:
    subprocess.run(["git", "clone", str(bare), str(dest)], env=GIT_ENV,
                   check=True, capture_output=True)
    return dest


# --- sourcing the shell helpers ---------------------------------------------

def _lib_path(tmp: Path) -> Path:
    """Extract the three update-path helpers from install.sh into a sourceable
    file (no install side effects run)."""
    lines = INSTALL_SH.read_text().splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines)
                 if l.startswith("resolve_latest_release_tag() {"))
    end = next(i for i, l in enumerate(lines)
               if l.startswith("# --- Handle --clone early"))
    lib = tmp / "lib.sh"
    lib.write_text("".join(lines[start:end]))
    return lib


def _run_lib(lib: Path, snippet: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'set -uo pipefail; source "{lib}"; {snippet}'],
        env=GIT_ENV, capture_output=True, text=True,
    )


# --- resolve_latest_release_tag ---------------------------------------------

def test_resolve_picks_highest_semver_skips_prereleases(tmp_path):
    bare = _make_origin(tmp_path, tags=["v0.9.0", "v0.10.0", "v0.2.0",
                                        "v0.11.0-rc.1"])
    work = _clone(bare, tmp_path / "work")
    lib = _lib_path(tmp_path)
    res = _run_lib(lib, f'resolve_latest_release_tag "{work}"')
    assert res.returncode == 0
    # v0.10.0 > v0.9.0 numerically; the rc.1 pre-release is ignored.
    assert res.stdout.strip() == "v0.10.0"


def test_resolve_no_release_tags_is_nonzero_and_empty(tmp_path):
    bare = _make_origin(tmp_path, tags=["nightly", "latest"])
    work = _clone(bare, tmp_path / "work")
    lib = _lib_path(tmp_path)
    res = _run_lib(lib, f'resolve_latest_release_tag "{work}"')
    assert res.returncode != 0
    assert res.stdout.strip() == ""


def test_resolve_offline_remote_is_nonzero_and_empty(tmp_path):
    # A repo whose 'origin' points at a path that does not exist: ls-remote
    # fails, which must be a hard no-op (non-zero, no output) -- never a fall
    # back to a local tag cache.
    work = tmp_path / "work"
    subprocess.run(["git", "init", str(work)], env=GIT_ENV,
                   check=True, capture_output=True)
    _g(work, "remote", "add", "origin", str(tmp_path / "does-not-exist.git"))
    lib = _lib_path(tmp_path)
    res = _run_lib(lib, f'resolve_latest_release_tag "{work}"')
    assert res.returncode != 0
    assert res.stdout.strip() == ""


def test_resolve_ignores_local_only_tag(tmp_path):
    # Origin publishes v0.1.0; the clone also has a stale LOCAL-only v9.9.9 that
    # origin never had. Resolution is origin-authoritative, so it must pick
    # v0.1.0 and ignore the local tag (no silent jump to a withdrawn/never-shipped
    # version).
    bare = _make_origin(tmp_path, tags=["v0.1.0"])
    work = _clone(bare, tmp_path / "work")
    _g(work, "tag", "v9.9.9")  # local only, not on origin
    lib = _lib_path(tmp_path)
    res = _run_lib(lib, f'resolve_latest_release_tag "{work}"')
    assert res.returncode == 0
    assert res.stdout.strip() == "v0.1.0"


# --- checkout_release_tag ---------------------------------------------------

def test_checkout_succeeds_on_clean_tree(tmp_path):
    bare = _make_origin(tmp_path, base="v1", tags=["v0.1.0"], main_content="v2")
    work = _clone(bare, tmp_path / "work")
    lib = _lib_path(tmp_path)
    res = _run_lib(lib, f'checkout_release_tag "{work}" v0.1.0')
    assert res.returncode == 0
    assert (work / "marker").read_text() == "v1"


def test_checkout_fails_on_dirty_conflicting_tree(tmp_path):
    # The flagged failure mode at the helper level: a release tag exists and
    # fetch succeeds, but a dirty tracked file blocks the checkout. The helper
    # MUST report failure (non-zero) so callers can refuse to install.
    bare = _make_origin(tmp_path, base="v1", tags=["v0.1.0"], main_content="v2")
    work = _clone(bare, tmp_path / "work")
    (work / "marker").write_text("dirty-local")  # conflicts with v0.1.0's "v1"
    lib = _lib_path(tmp_path)
    res = _run_lib(lib, f'checkout_release_tag "{work}" v0.1.0')
    assert res.returncode != 0
    # The dirty content is left untouched -- nothing was silently overwritten.
    assert (work / "marker").read_text() == "dirty-local"


# --- version_gt -------------------------------------------------------------

@pytest.mark.parametrize("a,b,expected_gt", [
    ("0.16.0", "0.15.0", True),   # strictly newer
    ("0.16.0", "0.16.0", False),  # equal is NOT greater
    ("0.15.0", "0.16.0", False),  # older -> would be a downgrade
    ("0.10.0", "0.9.0", True),    # numeric, not lexicographic
    ("1.0.0", "0.99.99", True),
])
def test_version_gt(tmp_path, a, b, expected_gt):
    lib = _lib_path(tmp_path)
    res = _run_lib(lib, f'if version_gt "{a}" "{b}"; then echo YES; else echo NO; fi')
    assert res.returncode == 0
    assert res.stdout.strip() == ("YES" if expected_gt else "NO")


# --- end-to-end: the flagged --clone regression -----------------------------

def test_clone_aborts_when_resolved_tag_cannot_be_checked_out(tmp_path):
    """--clone against an existing repo where a release tag RESOLVES but the
    checkout FAILS (dirty tree) must abort non-zero and install nothing -- never
    fall through to exec'ing the stale/main/dirty checkout."""
    home = tmp_path / "home"
    valor_repo = home / ".valor" / "repo"
    valor_repo.parent.mkdir(parents=True)

    bare = _make_origin(tmp_path, base="v1", tags=["v0.1.0"], main_content="v2")
    _clone(bare, valor_repo)                      # existing ~/.valor/repo, on main tip
    (valor_repo / "marker").write_text("dirty")   # blocks checkout of v0.1.0

    env = {**GIT_ENV, "HOME": str(home)}
    res = subprocess.run(
        ["bash", str(INSTALL_SH), "--clone"],
        env=env, capture_output=True, text=True,
    )

    assert res.returncode == 1, f"expected abort; stdout={res.stdout} stderr={res.stderr}"
    assert "v0.1.0" in res.stderr
    assert "Refusing to install" in res.stderr
    # The clincher: the install never ran, so no state.json was written.
    assert not (home / ".valor" / "state.json").exists()
    # And the user's checkout was left untouched (still dirty, not clobbered).
    assert (valor_repo / "marker").read_text() == "dirty"
