"""Tests for the PR review-console assembler (src/pr-console/assemble.py).

The header (tab title, on-page heading, one-line summary) is per-PR and comes
from the generator output. It was previously left as template text, so every
console shipped labelled with whatever PR the template was authored against —
these tests lock the injection in. The directory name has a hyphen, so the
script is exercised through subprocess rather than imported.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "src" / "pr-console" / "assemble.py"
TEMPLATE = REPO / "src" / "pr-console" / "template.html"

PLACEHOLDERS = ("/*__SCENES__*/", "/*__QUIZ__*/", "/*__DIFFS__*/", "/*__CTXCODE__*/")


def _gen(**over):
    """Minimal generator output: one container, one component, one question."""
    gen = {
        "title": "Add jittered retry backoff",
        "number": 123,
        "subtitle": "Retries now back off with jitter instead of hammering the API.",
        "context": {
            "system": {"id": "SYS", "label": "Auth service", "sub": "this system"},
            "actors": [{"id": "CLI", "label": "Client app", "impact": "ctx",
                        "phase": "both", "text": "calls the service"}],
            "edges": [{"from": "CLI", "to": "SYS", "kind": "flow", "phase": "both"}],
        },
        "containers": {
            "items": [{"id": "front", "label": "Front door", "sub": "entry point",
                       "impact": "chg", "phase": "both", "cap": "takes the request"}],
            "externals": [],
            "edges": [],
            "play": ["front"],
        },
        "components": {
            "front": {
                "nodes": [{"id": "retry", "label": "Retry policy", "impact": "new",
                           "phase": "after", "sym": "retry_with_jitter",
                           "anchor": "def retry_with_jitter", "file": "net/transport.py",
                           "text": "backs off with jitter", "before": "", "after": "caps at 30s"}],
                "edges": [],
            },
        },
        "quiz": [{"q": "What changed?", "options": ["a", "b", "c", "d"],
                  "answer_index": 0, "explanation": "because", "difficulty": "easy"}],
        "ctxcode": {},
    }
    gen.update(over)
    return gen


def _assemble(tmp_path, gen):
    (tmp_path / "gen.json").write_text(json.dumps(gen), encoding="utf-8")
    diffdir = tmp_path / "diff_by_file"
    diffdir.mkdir(exist_ok=True)
    out = tmp_path / "console.html"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--gen", str(tmp_path / "gen.json"),
         "--diffdir", str(diffdir), "--template", str(TEMPLATE), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return out.read_text(encoding="utf-8"), proc.stderr


def test_template_declares_utf8():
    """Without a charset the browser guesses windows-1252 whenever the server
    doesn't declare one, and every em dash, ✓, ⤢ and ▶ in the console renders as
    mojibake. It must be in the first 1024 bytes."""
    head = TEMPLATE.read_bytes()[:1024].decode("utf-8", "replace").lower()
    assert '<meta charset="utf-8">' in head, "template must declare UTF-8 up front"


def test_assembled_console_declares_utf8(tmp_path):
    html, _ = _assemble(tmp_path, _gen(title="Fix — the em dash case"))
    assert '<meta charset="utf-8">' in html[:1024].lower()
    assert "—" in html


def test_template_keeps_the_header_slots():
    """The injection targets must exist, and the shipped template must not carry
    a hardcoded PR identity (heading, ticket key, repo name)."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="prtitle"' in text, "template lost the heading slot"
    assert 'id="prsub"' in text, "template lost the summary slot"
    assert "PR #" not in text.split("<script>")[0], (
        "template header hardcodes a PR number; it must be injected per-PR"
    )


def test_header_is_injected_from_the_generator_output(tmp_path):
    html, stderr = _assemble(tmp_path, _gen())
    assert 'id="prtitle">PR #123 — Add jittered retry backoff<' in html
    assert 'id="prsub">Retries now back off with jitter instead of hammering the API.<' in html
    assert "<title>PR #123 — Add jittered retry backoff</title>" in html
    assert "WARNING" not in stderr


def test_untitled_pr_falls_back_to_the_title_alone(tmp_path):
    html, _ = _assemble(tmp_path, _gen(number=None))
    assert 'id="prtitle">Add jittered retry backoff<' in html
    assert "PR #None" not in html


def test_header_text_is_escaped(tmp_path):
    """A PR title is untrusted text — it must not be able to inject markup."""
    html, _ = _assemble(tmp_path, _gen(title="Fix <script>alert(1)</script> path"))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_scenes_quiz_and_diffs_are_injected(tmp_path):
    html, stderr = _assemble(tmp_path, _gen())
    for marker in PLACEHOLDERS:
        assert f"{marker}[]" not in html and f"{marker}{{}}" not in html, (
            f"{marker} was never filled"
        )
    assert "What changed?" in html
    assert "retry_with_jitter" in html
    assert "leftover placeholder" not in stderr


@pytest.mark.parametrize("missing", ["title", "subtitle"])
def test_missing_header_fields_leave_the_default_text(tmp_path, missing):
    """A malformed generator payload degrades to the neutral default rather than
    crashing or emitting a half-written header."""
    gen = _gen()
    del gen[missing]
    html, _ = _assemble(tmp_path, gen)
    assert 'id="prtitle"' in html and 'id="prsub"' in html
