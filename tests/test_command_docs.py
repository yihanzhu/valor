import subprocess
from pathlib import Path

import pytest

COMMANDS_DIR = Path("commands")
COMMAND_FILES = sorted(COMMANDS_DIR.glob("valor-*.md"))


def test_wrapup_carry_forward_stays_under_valor_home():
    text = Path("commands/valor-wrapup.md").read_text()
    assert "~/.valor/carry-forward/" in text
    assert ".claude/memories" not in text
    assert "MEMORY.md" not in text


def test_weekly_reflection_uses_explicit_week_window():
    text = Path("commands/valor-weekly.md").read_text()
    assert "reflection_week_start" in text
    assert "reflection_week_end_exclusive" in text
    assert "previous ISO week" in text


# --- Integration check tests ---

COMMANDS_NEEDING_INTEGRATION_CHECK = [
    "valor-briefing",
    "valor-weekly",
    "valor-tasks",
    "valor-design-doc",
    "valor-pr-review",
]


@pytest.mark.parametrize("cmd", COMMANDS_NEEDING_INTEGRATION_CHECK)
def test_commands_reference_integrations(cmd):
    """Commands that use external tools must reference integrations from state.json."""
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations" in text, f"{cmd} does not reference integrations"


@pytest.mark.parametrize("cmd", ["valor-briefing", "valor-weekly", "valor-tasks"])
def test_commands_with_jira_reference_integrations_jira(cmd):
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations.jira" in text, f"{cmd} uses Jira but does not check integrations.jira"


@pytest.mark.parametrize("cmd", ["valor-briefing", "valor-weekly", "valor-tasks"])
def test_commands_with_github_reference_integrations_github(cmd):
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations.github" in text, f"{cmd} uses GitHub but does not check integrations.github"


def test_wrapup_does_not_require_external_integrations():
    """Wrap-up is fully local and should not gate on integrations."""
    text = Path("commands/valor-wrapup.md").read_text()
    assert "Integration Check" not in text


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


def test_state_json_template_is_valid_json():
    """The initial state.json template in install.sh should produce valid JSON."""
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
