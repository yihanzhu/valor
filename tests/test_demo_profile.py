"""Tests for the shipped demo profile (examples/demo/).

The demo profile is the thing a presenter runs in front of an audience, so the
failure modes that matter are: a fixture that stopped parsing, a date token that
never got resolved, an integration that isn't actually off, and a run-book that
silently stopped covering a command. Seeding runs against a temp HOME, never the
real one.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from src.evidence_cli import VALID_COMPETENCIES

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "examples" / "demo"
FIXTURES = DEMO / "fixtures"
SEED = DEMO / "seed.py"
EVIDENCE = DEMO / "evidence.jsonl"

VALID_STATUS = {"in_progress", "merged", "deployed", "live", "validated"}
VALID_ROLE = {"led", "built", "co-built", "contributed", "advised", "decided-by-other"}

# Commands the run-book must cover, kept in step with commands/.
COMMAND_STEMS = sorted(p.stem for p in (REPO / "commands").glob("*.md"))

DEMO_DAY = "2026-06-10"  # a Wednesday, so the seeded week looks like a work week


@pytest.fixture(scope="module")
def seeded_home(tmp_path_factory):
    """Seed a real profile once into a temp HOME (few evidence rows, for speed)."""
    home = tmp_path_factory.mktemp("valor-demo-home")
    proc = subprocess.run(
        [sys.executable, str(SEED), str(home), "--date", DEMO_DAY, "--max-evidence", "6"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return home


# --- fixture content -----------------------------------------------------


def test_fixtures_directory_is_populated():
    files = [p for p in FIXTURES.iterdir() if p.is_file()]
    assert len(files) >= 8, f"expected the full fixture set in {FIXTURES}, found {len(files)}"


@pytest.mark.parametrize(
    "name", sorted(p.name for p in FIXTURES.glob("*.json")), ids=lambda n: n
)
def test_json_fixtures_parse_before_rendering(name):
    """Date tokens live inside JSON string values, so the raw fixture must still
    be valid JSON — that keeps them editable with normal tooling."""
    json.loads((FIXTURES / name).read_text())


def test_fixtures_use_only_known_date_tokens():
    known = {"TODAY", "MONDAY", "LAST_MONDAY", "CYCLE_START", "TZ", "YEAR"}
    bad = []
    for path in FIXTURES.iterdir():
        if not path.is_file():
            continue
        for token in re.findall(r"\{\{([A-Z_]+)([+-]\d+)?\}\}", path.read_text()):
            if token[0] not in known:
                bad.append(f"{path.name}: {{{{{token[0]}}}}}")
    assert not bad, f"unknown date tokens (seed.py can't resolve these): {bad}"


# --- seeded evidence -----------------------------------------------------


def _evidence_records():
    records = []
    for line in EVIDENCE.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if "_comment" in record:
            continue
        records.append(record)
    return records


def test_evidence_history_is_substantial_and_valid():
    records = _evidence_records()
    assert len(records) >= 40, (
        f"{len(records)} evidence entries — the reflection and weekly demos need a "
        "populated history to look like anything"
    )
    for record in records:
        assert isinstance(record["day_offset"], int) and record["day_offset"] >= 0
        assert record["competency"] in VALID_COMPETENCIES, record
        assert record["activity"] and record["statement"]
        if "status" in record:
            assert record["status"] in VALID_STATUS, record
        if "role" in record:
            assert record["role"] in VALID_ROLE, record


def test_evidence_covers_every_competency():
    seen = {r["competency"] for r in _evidence_records()}
    assert seen == set(VALID_COMPETENCIES), f"missing competencies: {set(VALID_COMPETENCIES) - seen}"


def test_evidence_has_the_reflection_demo_hooks():
    """Two planted hooks the /valor-reflection demo depends on: a deliverable
    with no recorded role, and work still in progress."""
    records = _evidence_records()
    assert any("role" not in r and r.get("status") for r in records), (
        "no deliverable is missing its `role` — the confirm-before-submit list "
        "has nothing to ask about"
    )
    assert any(r.get("status") == "in_progress" for r in records), (
        "nothing is in_progress — the reflection can't demo status-honest phrasing"
    )


# --- seeding -------------------------------------------------------------


def test_seed_refuses_the_real_home():
    """The one mistake that would matter: seeding over a real profile."""
    proc = subprocess.run(
        [sys.executable, str(SEED), str(Path.home())],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode != 0
    assert "refusing" in (proc.stdout + proc.stderr).lower()


def test_seed_refuses_to_overwrite_without_force(seeded_home):
    proc = subprocess.run(
        [sys.executable, str(SEED), str(seeded_home), "--date", DEMO_DAY],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode != 0
    assert "--force" in proc.stdout + proc.stderr


def test_seeded_profile_has_the_expected_shape(seeded_home):
    valor = seeded_home / ".valor"
    for expected in ("career_framework.md", "state.json", "evidence.sqlite", "demo"):
        assert (valor / expected).exists(), f"seed did not create {expected}"
    assert list((valor / "carry-forward").glob("carry-forward-*.md")), "no carry-forward seeded"
    assert (valor / "demo" / "pr_diff.diff").exists()


def test_seeded_state_is_demo_safe(seeded_home):
    """Nothing in a demo may reach a real system or write to a calendar."""
    state = json.loads((seeded_home / ".valor" / "state.json").read_text())
    assert state["integrations"] == {
        "github": False, "jira": False, "calendar": False, "news": False
    }, "an integration is live in the demo profile"
    assert state["planning"]["calendar_auto_write"] is False, (
        "the demo would write blocks to a calendar"
    )
    assert state["update_check_interval_hours"] == 0, "an update nag could interrupt the demo"
    assert state["current_level"] == "L3" and state["target_level"] == "L4"


def test_rendered_fixtures_have_no_unresolved_tokens(seeded_home):
    leftovers = [
        path.name
        for path in (seeded_home / ".valor").rglob("*")
        if path.is_file() and "{{" in path.read_text(errors="ignore")
    ]
    assert not leftovers, f"unresolved date tokens in: {leftovers}"


def test_rendered_json_fixtures_still_parse(seeded_home):
    for path in sorted((seeded_home / ".valor" / "demo").glob("*.json")):
        json.loads(path.read_text())


def test_rendered_calendar_is_dated_to_the_demo_day(seeded_home):
    calendar = json.loads((seeded_home / ".valor" / "demo" / "calendar.json").read_text())
    today_events = [e for e in calendar["events"] if e["start"].startswith(DEMO_DAY)]
    assert len(today_events) >= 4, "the demo day should have a full calendar"


def test_context_runs_in_the_seeded_home(seeded_home):
    """End to end: the real CLI reads the seeded profile and reports the persona."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "src" / "evidence_cli.py"), "context"],
        capture_output=True, text=True, env={"HOME": str(seeded_home), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr
    context = json.loads(proc.stdout)
    assert context["levels"] == {"current": "L3", "target": "L4", "ceiling": "L5"}
    assert context["integrations"] == {
        "github": False, "jira": False, "calendar": False, "news": False
    }
    assert context["claims"]["open_count"] >= 1, "the verification gate has nothing to check"


def test_demo_mode_block_is_installed_exactly_once(seeded_home):
    """Re-seeding is routine (dates are relative), so the block must be replaced,
    never appended a second time."""
    claude_md = seeded_home / ".claude" / "CLAUDE.md"
    assert claude_md.exists()
    proc = subprocess.run(
        [sys.executable, str(SEED), str(seeded_home), "--date", DEMO_DAY,
         "--force", "--max-evidence", "2"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = claude_md.read_text()
    assert text.count("# --- BEGIN VALOR DEMO MODE ---") == 1
    assert text.count("# --- END VALOR DEMO MODE ---") == 1


# --- run-book / demo-mode contracts --------------------------------------


@pytest.mark.parametrize("stem", COMMAND_STEMS)
def test_runbook_covers_every_command(stem):
    """A new command must get a demo beat, or the 'complete tour' isn't."""
    text = (DEMO / "DEMO.md").read_text()
    assert f"/valor-{stem}" in text, (
        f"examples/demo/DEMO.md has no step for /valor-{stem} — the run-book claims "
        "to cover every workflow"
    )


def test_demo_mode_routes_every_shipped_fixture():
    """Every fixture must be named in demo-mode.md, or the agent will never read
    it; every file it names must exist."""
    block = (DEMO / "demo-mode.md").read_text()
    special = {"carry_forward.md"}  # a state file, not an integration stand-in
    for path in sorted(FIXTURES.iterdir()):
        if not path.is_file() or path.name in special:
            continue
        assert path.name in block, f"demo-mode.md never routes anything to {path.name}"
    for named in re.findall(r"demo/([\w.\-]+)", block):
        assert (FIXTURES / named).exists(), f"demo-mode.md points at missing fixture {named}"


def test_demo_mode_forbids_external_writes():
    block = (DEMO / "demo-mode.md").read_text().lower()
    assert "never write to a calendar" in block
    assert "data, not instructions" in block, (
        "demo-mode.md should keep fixture contents from being treated as instructions"
    )
