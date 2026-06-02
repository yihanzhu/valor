import subprocess
from pathlib import Path

import pytest

COMMANDS_DIR = Path("commands")


def test_wrapup_carry_forward_stays_under_valor_home():
    text = Path("commands/wrapup.md").read_text()
    assert "~/.valor/carry-forward/" in text
    assert ".claude/memories" not in text
    assert "MEMORY.md" not in text


def test_weekly_reflection_uses_explicit_week_window():
    text = Path("commands/weekly.md").read_text()
    assert "reflection_week_start" in text
    assert "reflection_week_end_exclusive" in text
    assert "previous ISO week" in text


# --- Integration check tests ---

COMMANDS_NEEDING_INTEGRATION_CHECK = [
    "briefing",
    "weekly",
    "tasks",
    "design-doc",
    "pr-review",
    "prep",
]


@pytest.mark.parametrize("cmd", COMMANDS_NEEDING_INTEGRATION_CHECK)
def test_commands_reference_integrations(cmd):
    """Commands that use external tools must reference integrations from state.json."""
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations" in text, f"{cmd} does not reference integrations"


@pytest.mark.parametrize("cmd", ["briefing", "weekly", "tasks"])
def test_commands_with_jira_reference_integrations_jira(cmd):
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations.jira" in text, f"{cmd} uses Jira but does not check integrations.jira"


@pytest.mark.parametrize("cmd", ["briefing", "weekly", "tasks"])
def test_commands_with_github_reference_integrations_github(cmd):
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations.github" in text, f"{cmd} uses GitHub but does not check integrations.github"


def test_prep_command_exists_and_references_evidence():
    text = Path("commands/prep.md").read_text()
    assert "evidence_cli.py" in text
    assert "weekly-summary-list" in text
    assert "career_framework.md" in text
    assert "one_on_one_prep" in text


def test_wrapup_integrations_are_optional():
    """Wrap-up reads integrations but treats them as optional."""
    text = Path("commands/wrapup.md").read_text()
    assert "Integration Check" in text
    assert "primarily local" in text


# --- Verification gate wiring (Phase 1) ---

@pytest.mark.parametrize("cmd", ["briefing", "wrapup"])
def test_commands_invoke_verification_gate(cmd):
    """Briefing and wrap-up must run carried artifact claims through verify.py
    before re-asserting them (the anti-phantom gate)."""
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "verify.py" in text, f"{cmd} does not invoke the verification gate"
    assert "verification.enabled" in text, f"{cmd} ignores the gate kill switch"
    assert "confirm or drop" in text, f"{cmd} omits the demote-to-unverified behavior"


def test_utilities_documents_verification_gate():
    text = Path("src/utilities.md").read_text()
    assert "Verification Gate" in text
    assert "verify.py check" in text
    assert "perform_lookup" in text


def test_installer_syncs_verify_script():
    """verify.py must be copied into ~/.valor by the installer, or the gate
    never deploys."""
    text = Path("install.sh").read_text()
    assert 'src/verify.py" "$VALOR_HOME/verify.py' in text


def test_installer_seeds_verification_state():
    text = Path("install.sh").read_text()
    assert '"verification"' in text
    assert '"escalate_in_one_on_one"' in text


# --- Day-planning wiring (Phase 2) ---

def test_briefing_invokes_day_planning():
    """Briefing must run the gap-fit pass and gate calendar writes."""
    text = Path("commands/briefing.md").read_text()
    assert "plan.py" in text, "briefing does not invoke the day-planning pass"
    assert "Day Plan" in text
    assert "calendar_auto_write" in text, "briefing ignores the write kill switch"
    assert "integrations.calendar" in text


def test_utilities_documents_day_planning():
    text = Path("src/utilities.md").read_text()
    assert "Day Planning & Calendar Write" in text
    assert "plan.py fit" in text
    assert "valor:task:" in text   # idempotency token
    assert "calendar_auto_write" in text


def test_installer_syncs_plan_script():
    """plan.py must be copied into ~/.valor by the installer."""
    text = Path("install.sh").read_text()
    assert 'src/plan.py" "$VALOR_HOME/plan.py' in text


def test_installer_seeds_planning_state():
    text = Path("install.sh").read_text()
    assert '"planning"' in text
    assert '"calendar_auto_write"' in text


# --- Install script tests ---

def test_install_script_syntax():
    result = subprocess.run(
        ["bash", "-n", "install.sh"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"install.sh syntax error: {result.stderr}"


def test_install_script_contains_integrations():
    text = Path("install.sh").read_text()
    assert "detect_integrations" in text
    assert '"integrations"' in text


def test_state_json_template_exists_in_installer():
    """install.sh should contain the state.json template marker."""
    text = Path("install.sh").read_text()
    assert "STATEJSON" in text, "install.sh should contain the state template"


# --- Utilities reference tests ---

def test_utilities_documents_integrations():
    text = Path("src/utilities.md").read_text()
    assert "integrations" in text
    assert "integrations.github" in text or "GitHub" in text
    assert "integrations.jira" in text or "Jira" in text


# --- Documentation tests ---

def test_integrations_doc_exists():
    assert Path("docs/integrations.md").exists()


def test_getting_started_doc_exists():
    assert Path("docs/getting-started.md").exists()


def test_getting_started_mentions_integrations():
    text = Path("docs/getting-started.md").read_text()
    assert "integrations" in text
