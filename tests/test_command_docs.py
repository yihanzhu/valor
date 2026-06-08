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


def test_day_plan_write_is_private():
    """Day-plan items must be written private (Google Task, or private event)."""
    text = Path("src/utilities.md").read_text()
    assert "Google Task" in text          # preferred private target
    assert "visibility: private" in text  # private-event fallback
    btext = Path("commands/briefing.md").read_text()
    assert "private" in btext


def test_routine_times_derive_from_working_hours():
    """Setup derives briefing/wrap-up routine times from the working hours."""
    text = Path("commands/setup.md").read_text()
    assert "workday_start" in text and "workday_end" in text


# --- 1:1 prep: format-aware + chronic (lighter Phase 3) ---

def test_prep_drafts_in_doc_format_and_surfaces_chronic():
    text = Path("commands/prep.md").read_text()
    assert "one_on_one" in text            # reads the configured 1:1 doc
    assert "format" in text.lower()        # mirrors the doc's format
    assert "verify.py list" in text        # chronic-item source (lighter Phase 3)
    assert "escalation_threshold" in text  # chronic threshold
    assert "Chronic" in text               # surfaced as a section


def test_wrapup_captures_meeting_notes():
    """Wrap-up captures meeting notes (e.g. Gemini) into evidence so a sync whose
    notes live only on the calendar still informs later 1:1 prep / weekly, and it
    skips short recurring standups."""
    text = Path("commands/wrapup.md").read_text()
    assert "Capture Meeting Notes" in text
    assert "meeting_notes" in text                       # the evidence activity
    assert "attach" in text.lower()                      # reads event attachments
    assert "standup" in text.lower()                     # the skip-standups rule
    assert "integrations.calendar" in text               # gated on calendar


def test_prep_uses_captured_meeting_notes():
    """1:1 prep stays a pure evidence reader -- it uses the wrap-up-captured
    meeting_notes entries rather than re-reading the calendar itself."""
    text = Path("commands/prep.md").read_text()
    assert "meeting_notes" in text


@pytest.mark.parametrize("cmd", ["prep", "sync-prep"])
def test_paste_ready_output_is_plain_text(cmd):
    """Paste-ready deliverables must be plain text -- markdown asterisks paste
    literally into the user's doc and break their formatting."""
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "plain text" in text.lower()
    assert "no `*`" in text  # the explicit no-asterisks rule


def test_installer_seeds_one_on_one_state():
    text = Path("install.sh").read_text()
    assert '"one_on_one"' in text


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


def _upgrade_case_body(text):
    start = text.index("--upgrade)")
    return text[start:text.index(";;", start)]


def test_upgrade_reexecs_after_pull():
    """M25: --upgrade must re-exec the freshly pulled install.sh -- running the
    stale in-process body would apply new files with old installer logic. The
    case body only flags the pull; the re-exec happens after arg parsing."""
    text = Path("install.sh").read_text()
    assert "DID_UPGRADE_PULL=true" in _upgrade_case_body(text), \
        "--upgrade case should flag the pull for a deferred re-exec"
    assert "VALOR_UPGRADE_REEXEC=1 exec bash" in text, \
        "install.sh does not re-exec the updated install.sh after an upgrade pull"


def test_upgrade_reexec_guard_prevents_loop():
    """The re-exec is gated on the guard var being unset, so the re-exec'd child
    (a plain install) cannot pull+re-exec again."""
    text = Path("install.sh").read_text()
    assert '[ -z "${VALOR_UPGRADE_REEXEC:-}" ]' in text


def test_upgrade_reexec_runs_after_parsing_and_forwards_flags():
    """The deferred re-exec must run AFTER the arg-parsing loop (so --target and
    --check are fully resolved) and forward both -- otherwise `--upgrade --check`
    would silently become a mutating install (regression that was fixed)."""
    text = Path("install.sh").read_text()
    # Re-exec is positioned after the parse loop closes, not inside the case.
    loop_end = text.index("    esac\n    shift\ndone")
    assert text.index("VALOR_UPGRADE_REEXEC=1 exec bash") > loop_end, \
        "re-exec must run after the arg-parsing loop, not mid-parse"
    # Both a plain-install and a --check-forwarding branch exist.
    assert 'exec bash "$SCRIPT_DIR/install.sh" --target "$TARGET" --check' in text
    assert 'if [ "$CHECK_ONLY" = true ]; then' in text


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


def test_installer_delegates_migration_to_evidence_cli():
    # The schema migrator has ONE source of truth: evidence_cli._migrate_state_in_memory.
    # install.sh must delegate to `evidence_cli.py state-migrate` rather than carry
    # its own inline copy — the two had drifted to different key sets, and a
    # short-circuit pop bug once slipped through the duplicate. This test forbids a
    # reintroduction: the migration logic itself is covered in test_evidence_cli.py.
    install = Path("install.sh").read_text()
    assert 'evidence_cli.py" state-migrate' in install, \
        "install.sh must delegate schema migration to `evidence_cli.py state-migrate`"
    assert 'migrate_msg=$(python3 -c "' not in install, \
        "install.sh must not reintroduce an inline duplicate of the migrator"


def test_installer_reads_schema_version_from_evidence_cli():
    # The installer derives the schema version from evidence_cli.py's
    # STATE_SCHEMA_VERSION instead of hardcoding a second literal that could drift.
    install = Path("install.sh").read_text()
    assert "STATE_SCHEMA_VERSION" in install, \
        "install.sh should read STATE_SCHEMA_VERSION from evidence_cli.py"
    assert "schema_version=16" not in install, \
        "install.sh must not hardcode a schema-version literal"
