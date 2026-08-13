"""Tests for the website's demo page, its transcripts, and the embedded console.

The demo page makes a factual claim — that its transcripts are real output and
its review console is the real artifact. These tests keep that claim true: the
committed JSON must match the captures it was built from, every workflow must
have a transcript, and the console must be self-contained (no network calls) with
its quiz answers intact.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "examples" / "demo"
CAPTURES = DEMO / "captures"
BUILDER = DEMO / "build_transcripts.py"
SITE = REPO / "website"
TRANSCRIPTS = SITE / "demo" / "transcripts.json"
CONSOLE = SITE / "demo" / "pr-console.html"
PAGE = SITE / "demo.html"

COMMAND_STEMS = sorted(p.stem for p in (REPO / "commands").glob("*.md"))


@pytest.fixture(scope="module")
def transcripts():
    return json.loads(TRANSCRIPTS.read_text())


# --- transcripts <-> captures --------------------------------------------


def test_transcripts_are_in_sync_with_the_captures():
    """The committed JSON must be exactly what the builder produces, so a hand
    edit to the page's content can't drift from the recorded captures.
    `--check` compares without writing, so the test never dirties the tree."""
    proc = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("stem", COMMAND_STEMS)
def test_every_command_has_a_transcript(stem, transcripts):
    commands = {e["command"] for e in transcripts["entries"]}
    assert f"/valor-{stem}" in commands, (
        f"no demo transcript for /valor-{stem} — the demo page claims to cover "
        "every workflow"
    )


def test_ambient_coaching_has_a_transcript(transcripts):
    """The always-on layer is the differentiator; it needs its own beat."""
    assert any(e["id"] == "ambient" for e in transcripts["entries"])


def test_transcript_entries_are_well_formed(transcripts):
    acts = set(transcripts["acts"])
    seen = set()
    for entry in transcripts["entries"]:
        for field in ("id", "command", "phrase", "label", "act", "blurb", "output"):
            assert entry.get(field), f"{entry.get('id')}: empty {field}"
        assert entry["act"] in acts, f"{entry['id']}: act not in {acts}"
        assert entry["id"] not in seen, f"duplicate id {entry['id']}"
        seen.add(entry["id"])
        assert len(entry["output"].splitlines()) >= 10, (
            f"{entry['id']}: transcript is too short to show anything"
        )


def test_transcripts_carry_no_unresolved_date_tokens(transcripts):
    for entry in transcripts["entries"]:
        assert "{{" not in entry["output"], f"{entry['id']} has an unrendered token"


def test_transcript_version_matches_repo(transcripts):
    assert transcripts["valor_version"] == (REPO / "VERSION").read_text().strip()


# --- the page ------------------------------------------------------------


def test_page_discloses_that_transcripts_are_recordings():
    """The page must not imply a live agent is answering."""
    text = PAGE.read_text()
    assert "These are recordings" in text
    assert "seeded demo profile" in text
    assert "no backend" in text


def test_page_loads_the_transcripts_and_the_console():
    text = PAGE.read_text()
    assert "./demo/transcripts.json" in text
    assert "./demo/pr-console.html" in text


def test_page_is_reachable_from_the_landing_page():
    index = (SITE / "index.html").read_text()
    assert "./demo.html" in index, "the landing page never links to the demo"


def test_landing_page_no_longer_claims_invented_tickets():
    """The old mocks used AUTH-### tickets that never existed in any profile.
    Everything shown now comes from the demo profile's fixtures."""
    index = (SITE / "index.html").read_text()
    assert "AUTH-412" not in index and "AUTH-418" not in index


def test_sitemap_lists_the_demo_page():
    assert "https://valor.sh/demo" in (SITE / "sitemap.xml").read_text()


# --- the embedded console ------------------------------------------------


def test_console_is_self_contained():
    """It ships as a page on the site, so it must not reach the network. (An
    `xmlns` is an identifier, not a fetch, so only loading attributes count.)"""
    html = CONSOLE.read_text()
    for pattern in ("fetch(", "XMLHttpRequest", "WebSocket", "<script src", "<link rel"):
        assert pattern not in html, f"console reaches outside itself: {pattern!r}"
    remote = [
        url for url in re.findall(r'(?:src|xlink:href)\s*=\s*"([^"]+)"', html)
        if url.startswith(("http://", "https://", "//"))
    ]
    assert not remote, f"console loads remote resources: {remote}"


def test_console_header_names_the_demo_pr():
    html = CONSOLE.read_text()
    assert 'id="prtitle">PR #418' in html
    assert "<title>PR #418" in html


def test_console_has_scenes_and_a_verified_quiz():
    html = CONSOLE.read_text()
    for key, opener in (("SCENES", "{"), ("QUIZ", "[")):
        assert f"/*__{key}__*/" not in html, f"{key} was never injected"
    match = re.search(r"const QUIZ = (\[.*?\]);\n", html, re.S)
    assert match, "could not find the injected quiz"
    quiz = json.loads(match.group(1))
    assert len(quiz) >= 5, "too few questions to gate an approval on"
    for question in quiz:
        assert len(question["options"]) == 4
        assert 0 <= question["answer_index"] < 4
        assert question["explanation"].strip()


def test_console_inlines_the_real_diffs_but_not_the_tests():
    """Components point at production files; the test file is excluded from the
    diagram by design."""
    html = CONSOLE.read_text()
    match = re.search(r"const DIFFS = (\{.*?\});\n", html, re.S)
    assert match, "could not find the injected diffs"
    diffs = json.loads(match.group(1))
    assert "net/transport.py" in diffs and "api/payments_client.py" in diffs
    assert not any("tests/" in path for path in diffs)


def test_console_code_nodes_anchor_into_their_diff():
    """Each L4 jump must find its line in the inlined diff, or the deepest zoom
    level lands on nothing."""
    html = CONSOLE.read_text()
    scenes = json.loads(re.search(r"const SCENES = (\{.*?\});\n", html, re.S).group(1))
    diffs = json.loads(re.search(r"const DIFFS = (\{.*?\});\n", html, re.S).group(1))
    misses = [
        node["anchor"]
        for scene in scenes.values()
        for node in scene["nodes"]
        if node.get("code") and node["file"] in diffs
        and node["anchor"] not in diffs[node["file"]]
    ]
    assert not misses, f"anchors not present in their diff: {misses}"
