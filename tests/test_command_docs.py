import re
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
    "design-doc",
    "pr-review",
    "prep",
]


@pytest.mark.parametrize("cmd", COMMANDS_NEEDING_INTEGRATION_CHECK)
def test_commands_reference_integrations(cmd):
    """Commands that use external tools must reference integrations from state.json."""
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations" in text, f"{cmd} does not reference integrations"


@pytest.mark.parametrize("cmd", ["briefing", "weekly"])
def test_commands_with_jira_reference_integrations_jira(cmd):
    text = (COMMANDS_DIR / f"{cmd}.md").read_text()
    assert "integrations.jira" in text, f"{cmd} uses Jira but does not check integrations.jira"


@pytest.mark.parametrize("cmd", ["briefing", "weekly"])
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


def test_installer_seeds_prioritization_state():
    text = Path("install.sh").read_text()
    assert '"prioritization"' in text
    assert '"week_goals"' in text
    assert '"standing_rules"' in text


def test_tasks_command_retired():
    """/valor-tasks was folded into the briefing's spare-capacity pickups and the
    standalone command removed — assert no trace remains anywhere."""
    assert not Path("commands/tasks.md").exists()
    install = Path("install.sh").read_text()
    assert "valor-tasks" not in install and "task-identifier" not in install
    assert "Task Identifier" not in install          # the agent-summary list too
    for f in ("rules/valor-agent.md", "README.md", "docs/architecture.md",
              "commands/setup.md", "docs/getting-started.md", "docs/integrations.md"):
        assert "/valor-tasks" not in Path(f).read_text(), f
        assert "Task Identifier" not in Path(f).read_text(), f


def _extract_prune_orphans():
    install = Path("install.sh").read_text()
    start = install.index("prune_orphans() {")
    end = install.index("\n}\n", start) + len("\n}\n")
    return install[start:end]


def test_install_prune_orphans_removes_only_retired_valor_artifacts(tmp_path):
    """install.sh prunes orphaned valor-* commands/skills from a retired command,
    but NEVER touches a current command or a user's own (non-valor) files."""
    fn = _extract_prune_orphans()
    cmds = tmp_path / "commands"
    cmds.mkdir()
    skills = tmp_path / "skills"
    skills.mkdir()
    (cmds / "valor-briefing.md").write_text("x")   # in COMMAND_MAP -> keep
    (cmds / "valor-tasks.md").write_text("x")       # retired -> prune
    (cmds / "my-custom.md").write_text("x")         # user's own (non-valor) -> keep
    (skills / "valor-morning-briefing").mkdir()      # in COMMAND_MAP -> keep
    (skills / "valor-task-identifier").mkdir()       # retired -> prune
    (skills / "my-custom-skill").mkdir()             # user's own -> keep
    harness = (
        'set -euo pipefail\n'
        'COMMAND_MAP=("briefing:valor-briefing:valor-morning-briefing:d")\n'
        + fn +
        f'\nprune_orphans command "{cmds}"\nprune_orphans skill "{skills}"\n'
    )
    r = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert {p.name for p in cmds.iterdir()} == {"valor-briefing.md", "my-custom.md"}
    assert {p.name for p in skills.iterdir()} == {"valor-morning-briefing", "my-custom-skill"}


def test_install_prune_orphans_noop_when_all_current(tmp_path):
    """When every deployed valor-* artifact is still in COMMAND_MAP, prune removes nothing."""
    fn = _extract_prune_orphans()
    cmds = tmp_path / "commands"
    cmds.mkdir()
    (cmds / "valor-briefing.md").write_text("x")
    harness = (
        'set -euo pipefail\n'
        'COMMAND_MAP=("briefing:valor-briefing:valor-morning-briefing:d")\n'
        + fn + f'\nprune_orphans command "{cmds}"\n'
    )
    r = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert {p.name for p in cmds.iterdir()} == {"valor-briefing.md"}


def test_install_prune_orphans_does_not_follow_symlinks(tmp_path):
    """A retired valor-* skill that is a SYMLINK must be unlinked, never followed —
    rm must not delete the link target's contents (which may live outside the dir)."""
    fn = _extract_prune_orphans()
    skills = tmp_path / "skills"
    skills.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep me")
    (skills / "valor-task-identifier").symlink_to(outside, target_is_directory=True)  # retired + symlinked
    harness = (
        'set -euo pipefail\n'
        'COMMAND_MAP=("briefing:valor-briefing:valor-morning-briefing:d")\n'
        + fn + f'\nprune_orphans skill "{skills}"\n'
    )
    r = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert not (skills / "valor-task-identifier").is_symlink()      # orphan symlink unlinked
    assert (outside / "precious.txt").read_text() == "keep me"      # target NOT followed/deleted


def test_install_calls_prune_orphans_for_each_target():
    """Each install target prunes after deploying (commands for Claude Code, skills
    for Codex/Cursor)."""
    text = Path("install.sh").read_text()
    assert text.count("prune_orphans ") >= 3  # the helper def uses "prune_orphans()", calls use "prune_orphans <kind>"
    assert "prune_orphans command " in text
    assert "prune_orphans skill " in text


def test_briefing_folds_in_spare_capacity_backlog():
    """The backlog-discovery /valor-tasks did is preserved as an optional
    spare-capacity pickup in the briefing (surfaced only when the day is light)."""
    text = Path("commands/briefing.md").read_text()
    assert "Spare capacity" in text
    assert "backlog" in text.lower()
    assert "task_identified" in text  # proactivity still recorded as evidence


def test_briefing_prioritizes_against_week_goals_and_dependencies():
    """The briefing ranks todos against the week's goals + standing-rule
    dependencies before planning, instead of by Jira status/recency alone."""
    text = Path("commands/briefing.md").read_text()
    assert "week_goals" in text
    assert "standing_rules" in text
    assert "Held (blocked)" in text                 # dependency-held items surfaced, not planned
    assert "Prioritize against the week" in text    # the §6.5 ranking pass exists


def test_prep_captures_week_goals():
    """1:1 prep extracts this week's goals from the doc into prioritization state
    (silently) so the briefing can rank against them."""
    text = Path("commands/prep.md").read_text()
    assert "week_goals" in text
    assert "prioritization" in text


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


# --- Integration matrix <-> command declaration contract -----------------
#
# Each workflow command declares its integration surface in a machine-readable
# comment near its title, e.g.:
#     <!-- valor:integrations github=optional jira=optional calendar=optional news=none -->
# (values: required | optional | none). The docs/integrations.md Integration
# Matrix must agree with those declarations cell-for-cell. This enforces the
# doc/behavior contract mechanically: change a command's integration surface and
# the matrix is forced to follow (and vice versa), instead of being re-audited
# by hand each release.

INTEGRATIONS = ("github", "jira", "calendar", "news")
_DECL_VALUES = ("required", "optional", "none")

# docs/integrations.md matrix display-name -> command file stem.
# setup.md is intentionally excluded: it *configures* integrations, it does not
# consume them as a data source, so it has no matrix row and no declaration.
MATRIX_NAME_TO_CMD = {
    "Morning Briefing": "briefing",
    "PR Review Coach": "pr-review",
    "Design Doc Coach": "design-doc",
    "Weekly Reflection": "weekly",
    "Evening Wrap-up": "wrapup",
    "1:1 Prep": "prep",
    "Project Sync Prep": "sync-prep",
}
NON_WORKFLOW_COMMANDS = {"setup"}

_DECL_RE = re.compile(r"<!--\s*valor:integrations\s+(.*?)\s*-->")


def _parse_command_declaration(stem):
    """Return {integration: required|optional|none} from a command's
    `<!-- valor:integrations ... -->` declaration."""
    text = (COMMANDS_DIR / f"{stem}.md").read_text()
    match = _DECL_RE.search(text)
    assert match, (
        f"commands/{stem}.md is missing its "
        "<!-- valor:integrations github=... jira=... calendar=... news=... --> declaration"
    )
    decl = {}
    for token in match.group(1).split():
        key, sep, val = token.partition("=")
        assert sep and key in INTEGRATIONS, f"{stem}: bad integration token '{token}'"
        assert val in _DECL_VALUES, (
            f"{stem}: bad value '{val}' for {key} (want one of {_DECL_VALUES})"
        )
        decl[key] = val
    missing = set(INTEGRATIONS) - set(decl)
    assert not missing, f"{stem}: declaration missing {sorted(missing)}"
    return decl


def _classify_matrix_cell(cell):
    """Map a matrix cell to required | optional | none."""
    text = cell.strip()
    if text in ("", "--", "—", "-"):
        return "none"
    if "required" in text.lower():
        return "required"
    return "optional"


def _parse_integration_matrix():
    """Parse the Integration Matrix table in docs/integrations.md into
    {display_name: {integration: required|optional|none}}."""
    doc = Path("docs/integrations.md").read_text()
    assert "## Integration Matrix" in doc, "docs/integrations.md lost its Integration Matrix"
    section = doc.split("## Integration Matrix", 1)[1].split("\n## ", 1)[0]
    rows = [ln for ln in section.splitlines() if ln.strip().startswith("|")]
    assert len(rows) >= 3, "Integration Matrix table not found / malformed"
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    col = {}
    for integ in INTEGRATIONS:
        matches = [i for i, h in enumerate(header) if h.lower() == integ]
        assert matches, f"matrix header has no '{integ}' column: {header}"
        col[integ] = matches[0]
    matrix = {}
    for row in rows[2:]:  # rows[0]=header, rows[1]=separator
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != len(header):
            continue
        name = cells[0].replace("*", "").strip()
        matrix[name] = {integ: _classify_matrix_cell(cells[col[integ]]) for integ in INTEGRATIONS}
    return matrix


def test_integration_matrix_matches_command_declarations():
    """The docs/integrations.md matrix must agree, cell for cell, with each
    command's valor:integrations declaration."""
    matrix = _parse_integration_matrix()
    assert set(matrix) == set(MATRIX_NAME_TO_CMD), (
        f"matrix commands {sorted(matrix)} != expected {sorted(MATRIX_NAME_TO_CMD)}; "
        "update MATRIX_NAME_TO_CMD and the matrix together"
    )
    mismatches = []
    for name, stem in MATRIX_NAME_TO_CMD.items():
        decl = _parse_command_declaration(stem)
        for integ in INTEGRATIONS:
            if matrix[name][integ] != decl[integ]:
                mismatches.append(
                    f"{name} ({stem}.md) / {integ}: matrix='{matrix[name][integ]}' "
                    f"vs command declares '{decl[integ]}'"
                )
    assert not mismatches, (
        "Integration matrix <-> command declaration drift:\n  " + "\n  ".join(mismatches)
    )


def test_every_workflow_command_is_declared_and_in_the_matrix():
    """Every command except setup must declare its integrations and have a
    matrix row, so a new command can't silently skip the contract."""
    stems = {p.stem for p in COMMANDS_DIR.glob("*.md")}
    expected = set(MATRIX_NAME_TO_CMD.values()) | NON_WORKFLOW_COMMANDS
    assert stems == expected, (
        f"command set changed: {sorted(stems)} != {sorted(expected)}. A new workflow "
        "command needs a valor:integrations declaration + a matrix row (or, if it does "
        "not consume integrations like setup, add it to NON_WORKFLOW_COMMANDS)."
    )
    for stem in MATRIX_NAME_TO_CMD.values():
        _parse_command_declaration(stem)  # asserts presence + validity


def test_command_integration_flags_match_declaration():
    """Any `integrations.<name>` flag a command's prose gates on must be declared
    as used (required/optional), never 'none' — catches a command that starts
    using an integration without updating its declaration."""
    token_re = re.compile(r"integrations\.(github|jira|calendar|news)")
    violations = []
    for stem in MATRIX_NAME_TO_CMD.values():
        text = (COMMANDS_DIR / f"{stem}.md").read_text()
        decl = _parse_command_declaration(stem)
        for integ in set(token_re.findall(text)):
            if decl[integ] == "none":
                violations.append(
                    f"{stem}.md gates on integrations.{integ} but declares it 'none'"
                )
    assert not violations, "\n".join(violations)


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


# --- Verification-gate lifecycle <-> spec contract --------------------------
#
# The phantom-send incident showed prose instructions drift; these tests pin
# the spec<->runtime vocabulary so a renamed/removed subcommand or a spec that
# stops referencing the lifecycle fails CI instead of silently regressing.

VERIFY_SPEC_SURFACES = (
    "commands/wrapup.md",
    "commands/briefing.md",
    "src/utilities.md",
    "src/coaching-ref.md",
)


def test_verify_subcommands_named_in_specs_exist():
    """Every `verify.py <subcommand>` a spec mentions must exist in verify.py's
    argparse, and vice-versa for the lifecycle trio the specs depend on."""
    src_text = Path("src/verify.py").read_text()
    registered = set(re.findall(r'add_parser\(\s*\n?\s*["\']([a-z-]+)["\']', src_text))
    assert {"register", "reconcile", "carry-write"} <= registered
    used = set()
    # Invocation-shaped mentions only ("verify.py <cmd> --flag", "`verify.py
    # <cmd>`", or end-of-line) — prose like "verify.py is unavailable" doesn't
    # name a subcommand. Under-capture is fine: the assert is used ⊆ registered.
    invocation = re.compile(r"verify\.py\s+([a-z][a-z-]*)(?=\s+--|\s*`|\s*$)", re.MULTILINE)
    for surface in VERIFY_SPEC_SURFACES:
        used |= set(invocation.findall(Path(surface).read_text()))
    unknown = used - registered
    assert not unknown, f"specs reference verify.py subcommands that don't exist: {sorted(unknown)}"
    assert {"register", "reconcile"} <= used  # the lifecycle is actually invoked


def test_wrapup_runs_the_claims_lifecycle():
    """Wrap-up must register claims, consume the reconcile worklist, and write
    the carry-forward via carry-write (cache-stamped statuses) — not raw Write."""
    text = Path("commands/wrapup.md").read_text()
    assert "verify.py register" in text
    assert "verify.py reconcile" in text
    assert "carry-write" in text
    assert "from:me" in text          # the broad send-sweep before asking
    assert "Gate:" in text            # printed gate-summary line


def test_briefing_consumes_context_claims_with_default_deny():
    text = Path("commands/briefing.md").read_text()
    assert "context.claims" in text
    assert "stale_needs_check" in text
    assert "Default-deny" in text
    assert "parked" in text           # confirm-only expiry honored
    assert "Gate:" in text


def test_ambient_registers_send_claims_at_draft_time():
    """coaching-ref (on-demand, zero always-loaded cost) must tell the ambient
    flow to register a send-claim when it records a drafted communication."""
    text = Path("src/coaching-ref.md").read_text()
    assert "verify.py register" in text
    assert "--confirm-only" in text


def test_context_embeds_claims_worklist():
    text = Path("src/evidence_cli.py").read_text()
    assert "context_claims_summary" in text
    assert '"claims"' in text
