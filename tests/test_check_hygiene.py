"""Tests for the company-info hygiene scanner (scripts/check_hygiene.py).

Note: any email that should be *flagged* is built by concatenation so the literal
never appears in this file — otherwise the CI tree-scan would flag the test itself.
"""

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_hygiene.py"

_spec = importlib.util.spec_from_file_location("check_hygiene", SCRIPT)
hygiene = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hygiene)

# A flagged email, assembled so no full address is a literal in this source.
BAD_EMAIL = "leak" + "@" + "evil" + "corp.io"


def _exact(*terms):
    return [re.compile(t, re.IGNORECASE) for t in terms]


# --- email_is_flagged ---
def test_placeholder_email_is_safe():
    assert hygiene.email_is_flagged("dev@example.com") is False
    assert hygiene.email_is_flagged("a.b@sub.example.org") is False


def test_coauthor_and_project_domains_safe():
    assert hygiene.email_is_flagged("noreply@anthropic.com") is False
    assert hygiene.email_is_flagged("x@users.noreply.github.com") is False
    assert hygiene.email_is_flagged("hi@valor.yihanzhu.com") is False


def test_foreign_email_is_flagged():
    assert hygiene.email_is_flagged(BAD_EMAIL) is True


# --- scan_line ---
def test_scan_line_flags_denylist_term():
    hits = hygiene.scan_line("working on ACME-123 today", _exact(r"\bACME-\d+"))
    assert hits and hits[0][0] == "denylist"


def test_scan_line_flags_foreign_email():
    hits = hygiene.scan_line(f"ping {BAD_EMAIL} about it", [])
    assert hits and hits[0][0] == "non-placeholder-email"


def test_scan_line_clean_line_passes():
    assert hygiene.scan_line("a normal line with dev@example.com", _exact(r"\bACME-\d+")) == []


def test_ignore_marker_suppresses():
    line = "ACME-123 is fine here  # hygiene:ignore"
    assert hygiene.scan_line(line, _exact(r"\bACME-\d+")) == []


# --- redact (CI output never echoes the term) ---
def test_redact_masks_middle():
    assert hygiene.redact("secret") == "s****t"
    assert hygiene.redact("ab") == "**"


# --- end-to-end CLI (msg mode) ---
def _run_msg(tmp_path, text, denylist_env=None):
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(text)
    env = {**os.environ}
    env.pop("HYGIENE_DENYLIST", None)
    if denylist_env:
        env["HYGIENE_DENYLIST"] = denylist_env
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "msg",
         "--commit-msg-file", str(msg), "--denylist", "/nonexistent"],
        capture_output=True, text=True, env=env,
    )


def test_cli_clean_message_passes(tmp_path):
    r = _run_msg(tmp_path, "fix: tidy up the parser\n")
    assert r.returncode == 0, r.stderr


def test_cli_blocks_denylisted_term(tmp_path):
    r = _run_msg(tmp_path, "fix ACME-123 leak\n", denylist_env=r"\bACME-\d+")
    assert r.returncode == 1
    assert "BLOCKED" in r.stderr


def test_cli_blocks_foreign_email(tmp_path):
    r = _run_msg(tmp_path, f"contact {BAD_EMAIL}\n")
    assert r.returncode == 1


def test_cli_comment_lines_ignored(tmp_path):
    # Lines starting with '#' are git scissors/comments — not part of the message.
    r = _run_msg(tmp_path, "real subject\n# ACME-123 in a comment\n", denylist_env=r"\bACME-\d+")
    assert r.returncode == 0, r.stderr


def test_env_comment_with_commas_does_not_spawn_patterns(tmp_path):
    # Regression: a denylist *comment* line containing commas must not have its
    # fragments parsed as live patterns (env is split on newlines, not commas).
    env = "# org, git-ignored, names\n" + r"\bACME-\d+"
    r = _run_msg(tmp_path, "this line says git-ignored and names\n", denylist_env=env)
    assert r.returncode == 0, r.stderr  # 'git-ignored'/'names' must NOT be flagged


# --- text mode (PR title/body scanning) ---
def _run_text(tmp_path, text, denylist_env, redact=False):
    f = tmp_path / "pr_meta.txt"
    f.write_text(text)
    env = {**os.environ, "HYGIENE_DENYLIST": denylist_env}
    args = [sys.executable, str(SCRIPT), "--mode", "text",
            "--input-file", str(f), "--denylist", "/nonexistent"]
    if redact:
        args.append("--redact")
    return subprocess.run(args, capture_output=True, text=True, env=env)


def test_text_mode_does_not_skip_hash_lines(tmp_path):
    # PR descriptions use markdown headings ('#') — those must still be scanned
    # (unlike git commit-message comments).
    r = _run_text(tmp_path, "# Heading with ACME-9\nbody\n", r"\bACME-\d+")
    assert r.returncode == 1


def test_text_mode_redacts_matches(tmp_path):
    r = _run_text(tmp_path, "title mentions ACME-9\n", r"ACME-\d+", redact=True)
    assert r.returncode == 1
    assert "ACME-9" not in r.stderr  # the term is never echoed in redacted output


def test_text_mode_requires_input_file():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "text", "--denylist", "/nonexistent"],
        capture_output=True, text=True,
        env={**os.environ, "HYGIENE_DENYLIST": ""},
    )
    assert r.returncode == 2  # usage error
