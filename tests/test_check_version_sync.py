"""Tests for the version-sync guard (scripts/check_version_sync.py)."""

import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_version_sync",
    Path(__file__).resolve().parent.parent / "scripts" / "check_version_sync.py",
)
cvs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cvs)

REPO = Path(__file__).resolve().parent.parent


def test_repo_is_in_sync():
    # Regression guard: the real repo must have every version declaration == VERSION.
    assert cvs.check(REPO) == []


def _scaffold(root, version, claude_version, badge_version):
    (root / "VERSION").write_text(version + "\n")
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "valor", "version": claude_version}))
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(json.dumps({"name": "valor", "version": version}))
    (root / "website").mkdir(parents=True)
    (root / "website" / "index.html").write_text(f"<span>v{badge_version} · Apache-2.0</span>")


def test_clean_when_all_match(tmp_path):
    _scaffold(tmp_path, "1.2.3", "1.2.3", "1.2.3")
    assert cvs.check(tmp_path) == []


def test_detects_manifest_mismatch(tmp_path):
    _scaffold(tmp_path, "1.2.3", "0.3.0", "1.2.3")  # claude manifest stale
    problems = cvs.check(tmp_path)
    assert any(".claude-plugin/plugin.json" in p for p in problems)


def test_detects_badge_mismatch(tmp_path):
    _scaffold(tmp_path, "1.2.3", "1.2.3", "0.4.0")  # website badge stale
    problems = cvs.check(tmp_path)
    assert any("index.html" in p and "0.4.0" in p for p in problems)


def test_invalid_manifest_json_reported(tmp_path):
    (tmp_path / "VERSION").write_text("1.2.3\n")
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "plugin.json").write_text("{not valid json")
    assert any("invalid JSON" in p for p in cvs.check(tmp_path))
