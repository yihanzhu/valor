import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta

import pytest

import src.evidence_cli as cli_module
from src.evidence_cli import (
    ensure_schema,
    cmd_add,
    cmd_list,
    cmd_search,
    cmd_export,
    cmd_stats,
    cmd_status,
    cmd_backup,
    cmd_schema_version,
    cmd_feedback_add,
    cmd_feedback_stats,
    cmd_weekly_summary_save,
    cmd_weekly_summary_list,
    cmd_weekly_summary_get,
    cmd_context,
    cmd_state_set,
    cmd_framework_slice,
    cmd_setup_status,
    cmd_framework_validate,
    iso_week_bounds,
)


def _make_conn(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _add_entry(activity, competency, statement, agent="test-agent"):
    """Helper: call cmd_add with minimal args. Requires cli_db monkeypatch to be active."""
    args = argparse.Namespace(
        activity=activity, competency=competency,
        statement=statement, agent=agent, metadata=None,
        date=None,
    )
    cmd_add(args)


# --- ensure_schema ---

def test_ensure_schema_creates_required_tables(cli_db):
    db_path, _ = cli_db
    conn = _make_conn(db_path)
    ensure_schema(conn)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "evidence" in tables
    assert "feedback" in tables
    assert "weekly_summary" in tables
    assert "schema_version" in tables
    conn.close()


def test_ensure_schema_sets_latest_version(cli_db):
    db_path, _ = cli_db
    conn = _make_conn(db_path)
    ensure_schema(conn)
    version = conn.execute(
        "SELECT MAX(version) as v FROM schema_version"
    ).fetchone()["v"]
    assert version == 2
    conn.close()


def test_ensure_schema_is_idempotent(cli_db):
    db_path, _ = cli_db
    conn = _make_conn(db_path)
    ensure_schema(conn)
    ensure_schema(conn)  # should not raise or duplicate version row
    version = conn.execute(
        "SELECT MAX(version) as v FROM schema_version"
    ).fetchone()["v"]
    assert version == 2
    conn.close()


# --- cmd_add ---

def test_cmd_add_new_entry_returns_ok(cli_db, capsys):
    args = argparse.Namespace(
        activity="pr_review",
        competency="collaboration",
        statement="Reviewed PR #42",
        agent="test-agent",
        metadata=None,
        date=None,
    )
    cmd_add(args)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
    assert output["activity"] == "pr_review"
    assert "id" in output


def test_cmd_add_duplicate_returns_skipped(cli_db, capsys):
    args = argparse.Namespace(
        activity="code_written",
        competency="subject_matter",
        statement="Wrote some code",
        agent="test-agent",
        metadata=None,
        date=None,
    )
    cmd_add(args)
    capsys.readouterr()  # clear first call output
    cmd_add(args)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "skipped"
    assert output["reason"] == "duplicate"
    assert "existing_id" in output


def test_cmd_add_with_metadata(cli_db, capsys):
    args = argparse.Namespace(
        activity="design_doc_written",
        competency="autonomy_scope",
        statement="Wrote design doc",
        agent="test-agent",
        metadata={"pr": 99},
        date=None,
    )
    cmd_add(args)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"


def test_cmd_add_default_agent(cli_db, capsys):
    args = argparse.Namespace(
        activity="ticket_completed",
        competency="subject_matter",
        statement="Completed ticket",
        agent="manual",
        metadata=None,
        date=None,
    )
    cmd_add(args)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"


def test_cmd_add_invalid_competency_raises(cli_db):
    args = argparse.Namespace(
        activity="ticket_completed",
        competency="not_a_valid_competency",
        statement="Completed ticket",
        agent="manual",
        metadata=None,
        date=None,
    )
    with pytest.raises(ValueError):
        cmd_add(args)


def test_cmd_add_invalid_date_raises(cli_db):
    args = argparse.Namespace(
        activity="ticket_completed",
        competency="subject_matter",
        statement="Completed ticket",
        agent="manual",
        metadata=None,
        date="2026-02-30",
    )
    with pytest.raises(argparse.ArgumentTypeError):
        cli_module.parse_ymd_date(args.date)


# --- cmd_list ---

def test_cmd_list_returns_all_entries(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    capsys.readouterr()
    cmd_list(argparse.Namespace(
        days=None, from_date=None, to_date=None,
        competency=None, activity=None, limit=50,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) >= 1


def test_cmd_list_competency_filter(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    _add_entry("pr_review_cross_scope", "collaboration", "Reviewed PR")
    capsys.readouterr()
    cmd_list(argparse.Namespace(
        days=None, from_date=None, to_date=None,
        competency="subject_matter", activity=None, limit=50,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) >= 1
    assert all(e["competency"] == "subject_matter" for e in entries)


def test_cmd_list_limit(cli_db, capsys):
    for i in range(5):
        _add_entry(f"activity_{i}", "subject_matter", f"Statement {i}", agent=f"agent_{i}")
    capsys.readouterr()
    cmd_list(argparse.Namespace(
        days=None, from_date=None, to_date=None,
        competency=None, activity=None, limit=2,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) <= 2


def test_cmd_list_combined_filters(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    _add_entry("pr_review", "collaboration", "Reviewed PR")
    capsys.readouterr()
    cmd_list(argparse.Namespace(
        days=30, from_date=None, to_date=None,
        competency="subject_matter", activity=None, limit=50,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert all(e["competency"] == "subject_matter" for e in entries)


def test_cmd_list_from_date_filter(cli_db, capsys):
    args_old = argparse.Namespace(
        activity="code_written", competency="subject_matter",
        statement="Old entry", agent="test", metadata=None, date="2026-01-01",
    )
    args_recent = argparse.Namespace(
        activity="code_written", competency="subject_matter",
        statement="Recent entry", agent="test2", metadata=None, date="2026-04-01",
    )
    cmd_add(args_old)
    cmd_add(args_recent)
    capsys.readouterr()
    cmd_list(argparse.Namespace(
        days=None, from_date="2026-03-01", to_date=None,
        competency=None, activity=None, limit=50,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1
    assert entries[0]["evidence_statement"] == "Recent entry"


def test_cmd_list_to_date_filter(cli_db, capsys):
    args_old = argparse.Namespace(
        activity="code_written", competency="subject_matter",
        statement="Old entry", agent="test", metadata=None, date="2026-01-01",
    )
    args_recent = argparse.Namespace(
        activity="code_written", competency="subject_matter",
        statement="Recent entry", agent="test2", metadata=None, date="2026-04-01",
    )
    cmd_add(args_old)
    cmd_add(args_recent)
    capsys.readouterr()
    cmd_list(argparse.Namespace(
        days=None, from_date=None, to_date="2026-02-01",
        competency=None, activity=None, limit=50,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1
    assert entries[0]["evidence_statement"] == "Old entry"


def test_cmd_list_activity_filter(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    _add_entry("pr_review", "collaboration", "Reviewed PR")
    capsys.readouterr()
    cmd_list(argparse.Namespace(
        days=None, from_date=None, to_date=None,
        competency=None, activity="pr_review", limit=50,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1
    assert entries[0]["activity"] == "pr_review"


def test_cmd_list_empty_db(cli_db, capsys):
    cmd_list(argparse.Namespace(
        days=None, from_date=None, to_date=None,
        competency=None, activity=None, limit=50,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert entries == []


# --- cmd_search ---

def test_cmd_search_finds_matching_entries(cli_db, capsys):
    _add_entry("pr_review", "collaboration", "Reviewed cross-team PR #42")
    _add_entry("code_written", "subject_matter", "Wrote caching layer")
    capsys.readouterr()
    cmd_search(argparse.Namespace(query="PR", limit=50))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1
    assert "PR #42" in entries[0]["evidence_statement"]


def test_cmd_search_case_insensitive(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote CACHING layer")
    capsys.readouterr()
    cmd_search(argparse.Namespace(query="caching", limit=50))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1


def test_cmd_search_no_results(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote some code")
    capsys.readouterr()
    cmd_search(argparse.Namespace(query="nonexistent", limit=50))
    entries = json.loads(capsys.readouterr().out)
    assert entries == []


def test_cmd_search_respects_limit(cli_db, capsys):
    for i in range(5):
        _add_entry(f"activity_{i}", "subject_matter", f"PR review {i}", agent=f"agent_{i}")
    capsys.readouterr()
    cmd_search(argparse.Namespace(query="PR review", limit=2))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 2


# --- cmd_export ---

def test_cmd_export_json_format(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote caching layer")
    _add_entry("pr_review", "collaboration", "Reviewed PR #42")
    capsys.readouterr()
    cmd_export(argparse.Namespace(format="json"))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 2


def test_cmd_export_markdown_format(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote caching layer")
    capsys.readouterr()
    cmd_export(argparse.Namespace(format="markdown"))
    output = capsys.readouterr().out
    assert "##" in output
    assert "subject_matter" in output
    assert "Wrote caching layer" in output


def test_cmd_export_markdown_empty(cli_db, capsys):
    cmd_export(argparse.Namespace(format="markdown"))
    output = capsys.readouterr().out
    assert "No evidence" in output


def test_cmd_export_json_empty(cli_db, capsys):
    cmd_export(argparse.Namespace(format="json"))
    entries = json.loads(capsys.readouterr().out)
    assert entries == []


def test_cmd_export_filters_by_competency(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "SM entry")
    _add_entry("pr_review", "collaboration", "Collab entry")
    capsys.readouterr()
    cmd_export(argparse.Namespace(
        format="json", days=None, from_date=None, to_date=None,
        competency="collaboration",
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1
    assert entries[0]["competency"] == "collaboration"


def test_cmd_export_filters_by_days(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Recent")
    capsys.readouterr()
    cmd_export(argparse.Namespace(
        format="json", days=1, from_date=None, to_date=None, competency=None,
    ))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1


def test_cmd_export_filters_by_date_range(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "In range")
    capsys.readouterr()
    today = date.today().isoformat()
    cmd_export(argparse.Namespace(
        format="markdown", days=None, from_date=today, to_date=today,
        competency=None,
    ))
    output = capsys.readouterr().out
    assert "In range" in output


# --- cmd_stats ---

def test_cmd_stats_empty_db(cli_db, capsys):
    cmd_stats(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["total_entries"] == 0
    assert result["by_competency"] == {}


def test_cmd_stats_with_data(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    _add_entry("pr_review_cross_scope", "collaboration", "Reviewed PR")
    capsys.readouterr()
    cmd_stats(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["total_entries"] == 2
    assert "subject_matter" in result["by_competency"]
    assert "by_agent" in result
    assert "recent" in result
    assert len(result["recent"]) == 2


def test_cmd_stats_this_week_uses_iso_monday_boundary(cli_db, capsys):
    week_start, _ = iso_week_bounds()
    week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    previous_day = (week_start_date - timedelta(days=1)).strftime("%Y-%m-%d")

    args_in_week = argparse.Namespace(
        activity="code_written",
        competency="subject_matter",
        statement="In reflected week",
        agent="test-agent",
        metadata=None,
        date=week_start,
    )
    args_before_week = argparse.Namespace(
        activity="pr_review_cross_scope",
        competency="collaboration",
        statement="Before reflected week",
        agent="test-agent",
        metadata=None,
        date=previous_day,
    )
    cmd_add(args_in_week)
    capsys.readouterr()
    cmd_add(args_before_week)
    capsys.readouterr()

    cmd_stats(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["this_week"] == {"subject_matter": 1}


# --- cmd_status ---

def test_cmd_status_includes_version_from_file(cli_db, capsys, tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.2.0\n")
    monkeypatch.setattr(cli_module, "__file__", str(tmp_path / "evidence_cli.py"))
    cmd_status(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["version"] == "0.2.0"


def test_cmd_status_falls_back_to_state_json(cli_db, capsys, tmp_path, monkeypatch):
    """When VERSION file is absent, version comes from state.json installed_version."""
    no_version_dir = tmp_path / "noversion"
    no_version_dir.mkdir()
    monkeypatch.setattr(cli_module, "__file__", str(no_version_dir / "evidence_cli.py"))
    fake_home = tmp_path / "fakehome"
    valor_dir = fake_home / ".valor"
    valor_dir.mkdir(parents=True)
    (valor_dir / "state.json").write_text(json.dumps({
        "installed_version": "0.2.0-test",
        "coaching_mode": "ambient",
    }))
    monkeypatch.setenv("HOME", str(fake_home))
    cmd_status(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["version"] == "0.2.0-test"


def test_cmd_status_includes_evidence_counts(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    capsys.readouterr()
    cmd_status(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert "evidence" in result
    assert result["evidence"]["total"] >= 1


def test_cmd_status_no_db_shows_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "DB_PATH", tmp_path / "nonexistent.sqlite")
    monkeypatch.setattr(cli_module, "BACKUP_DIR", tmp_path / "backups")
    cmd_status(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["evidence"]["total"] == 0


# --- cmd_backup ---

def test_cmd_backup_creates_backup_file(cli_db, capsys):
    db_path, backup_dir = cli_db
    # Create DB first
    conn = cli_module.get_conn()
    ensure_schema(conn)
    conn.close()
    cmd_backup(argparse.Namespace())
    output = capsys.readouterr().out
    assert "Backed up to" in output
    backups = list(backup_dir.glob("evidence_*.sqlite"))
    assert len(backups) == 1


def test_cmd_backup_no_db_prints_message(cli_db, capsys):
    db_path, _ = cli_db
    if db_path.exists():
        db_path.unlink()
    cmd_backup(argparse.Namespace())
    output = capsys.readouterr().out
    assert "No database" in output


def test_cmd_backup_prunes_old_backups_to_10(cli_db, capsys):
    db_path, backup_dir = cli_db
    # Create DB
    conn = cli_module.get_conn()
    ensure_schema(conn)
    conn.close()
    # Pre-create 11 fake backups
    backup_dir.mkdir(parents=True, exist_ok=True)
    for i in range(11):
        (backup_dir / f"evidence_202601{i:02d}_000000.sqlite").write_bytes(b"fake")
    cmd_backup(argparse.Namespace())
    capsys.readouterr()
    backups = sorted(backup_dir.glob("evidence_*.sqlite"))
    assert len(backups) <= 10


# --- cmd_schema_version ---

def test_cmd_schema_version_shows_version(cli_db, capsys):
    cmd_schema_version(argparse.Namespace())
    output = capsys.readouterr().out
    assert "v1" in output


# --- main arg parsing ---

def test_main_no_command_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["evidence_cli"])
    with pytest.raises(SystemExit):
        cli_module.main()


def test_main_missing_required_arg_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["evidence_cli", "add", "--competency", "collaboration"])
    with pytest.raises(SystemExit):
        cli_module.main()


def test_main_invalid_competency_exits(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evidence_cli",
            "add",
            "--activity",
            "code_written",
            "--competency",
            "not_a_valid_competency",
            "--statement",
            "bad row",
        ],
    )
    with pytest.raises(SystemExit):
        cli_module.main()


# --- feedback ---

def test_feedback_add(cli_db, capsys):
    cmd_feedback_add(argparse.Namespace(
        evidence_id="abc-123", agent="valor-ambient", type="helpful",
    ))
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"
    assert result["type"] == "helpful"


def test_feedback_stats(cli_db, capsys):
    cmd_feedback_add(argparse.Namespace(
        evidence_id="", agent="valor-ambient", type="helpful",
    ))
    cmd_feedback_add(argparse.Namespace(
        evidence_id="", agent="valor-ambient", type="helpful",
    ))
    cmd_feedback_add(argparse.Namespace(
        evidence_id="", agent="valor-ambient", type="not_relevant",
    ))
    capsys.readouterr()
    cmd_feedback_stats(argparse.Namespace(agent=""))
    result = json.loads(capsys.readouterr().out)
    assert result["helpful"] == 2
    assert result["not_relevant"] == 1


def test_feedback_stats_filters_by_agent(cli_db, capsys):
    cmd_feedback_add(argparse.Namespace(
        evidence_id="", agent="agent-a", type="helpful",
    ))
    cmd_feedback_add(argparse.Namespace(
        evidence_id="", agent="agent-b", type="helpful",
    ))
    capsys.readouterr()
    cmd_feedback_stats(argparse.Namespace(agent="agent-a"))
    result = json.loads(capsys.readouterr().out)
    assert result.get("helpful") == 1


# --- weekly-summary ---

def test_weekly_summary_save_and_get(cli_db, capsys):
    cmd_weekly_summary_save(argparse.Namespace(
        week_start="2026-04-06", week_end="2026-04-12",
        summary={"subject_matter": 3, "collaboration": 1},
        gaps=["leadership"], narrative="Good week overall.",
    ))
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"

    cmd_weekly_summary_get(argparse.Namespace(week_start="2026-04-06"))
    entry = json.loads(capsys.readouterr().out)
    assert entry["week_start"] == "2026-04-06"
    assert entry["summary"]["subject_matter"] == 3
    assert entry["gaps"] == ["leadership"]
    assert entry["narrative"] == "Good week overall."


def test_weekly_summary_save_upserts_same_week(cli_db, capsys):
    cmd_weekly_summary_save(argparse.Namespace(
        week_start="2026-04-06", week_end="2026-04-12",
        summary={"subject_matter": 1}, gaps=[], narrative="First pass",
    ))
    capsys.readouterr()

    cmd_weekly_summary_save(argparse.Namespace(
        week_start="2026-04-06", week_end="2026-04-12",
        summary={"subject_matter": 5}, gaps=["leadership"], narrative="Revised",
    ))
    capsys.readouterr()

    cmd_weekly_summary_list(argparse.Namespace(limit=10))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 1, "Duplicate rows created for the same week_start"
    assert entries[0]["summary"]["subject_matter"] == 5
    assert entries[0]["narrative"] == "Revised"


def test_weekly_summary_list(cli_db, capsys):
    for i in range(3):
        ws = f"2026-04-{6 + i * 7:02d}"
        we = f"2026-04-{12 + i * 7:02d}"
        cmd_weekly_summary_save(argparse.Namespace(
            week_start=ws, week_end=we,
            summary={"count": i}, gaps=[], narrative=f"Week {i}",
        ))
    capsys.readouterr()

    cmd_weekly_summary_list(argparse.Namespace(limit=2))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 2
    assert entries[0]["week_start"] > entries[1]["week_start"]


def test_weekly_summary_get_not_found(cli_db, capsys):
    cmd_weekly_summary_get(argparse.Namespace(week_start="2020-01-01"))
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "not_found"


def test_weekly_summary_list_empty(cli_db, capsys):
    cmd_weekly_summary_list(argparse.Namespace(limit=8))
    entries = json.loads(capsys.readouterr().out)
    assert entries == []


# --- cmd_context ---

def test_context_returns_all_fields(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "L3",
        "target_level": "L4",
        "ceiling_level": "L5",
        "coaching_mode": "ambient",
        "integrations": {"github": True, "jira": False},
        "installed_version": "0.3.0",
        "briefing_count": 15,
        "github_owner": "TestOrg",
        "jira_projects": ["PROJ1"],
    }))
    cmd_context(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["levels"] == {"current": "L3", "target": "L4", "ceiling": "L5"}
    assert result["coaching_mode"] == "ambient"
    assert result["integrations"] == {"github": True, "jira": False}
    assert result["installed_version"] == "0.3.0"
    assert "suggest" in result
    assert "briefing_meta" in result
    assert result["briefing_meta"]["count"] == 15
    assert result["briefing_meta"]["tone_tier"] == "developing"
    assert result["github_owner"] == "TestOrg"
    assert result["jira_projects"] == ["PROJ1"]


def test_context_suggest_briefing_before_11(cli_db, capsys, monkeypatch):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "last_briefing_date": "2020-01-01",
    }))
    # Mock to Wednesday 9am
    mock_now = datetime(2026, 4, 15, 9, 0, 0)  # Wednesday
    monkeypatch.setattr("src.evidence_cli.datetime", type("MockDT", (datetime,), {
        "now": staticmethod(lambda *a, **kw: mock_now),
        "fromisoformat": datetime.fromisoformat,
        "strptime": datetime.strptime,
    }))
    cmd_context(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["suggest"]["briefing"] is True
    assert result["suggest"]["wrapup"] is False


def test_context_suggest_wrapup_after_17(cli_db, capsys, monkeypatch):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "last_wrapup_date": "2020-01-01",
    }))
    mock_now = datetime(2026, 4, 15, 18, 0, 0)  # Wednesday 6pm
    monkeypatch.setattr("src.evidence_cli.datetime", type("MockDT", (datetime,), {
        "now": staticmethod(lambda *a, **kw: mock_now),
        "fromisoformat": datetime.fromisoformat,
        "strptime": datetime.strptime,
    }))
    cmd_context(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["suggest"]["wrapup"] is True


def test_context_tone_tiers(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    for count, expected_tier in [(0, "onboarding"), (10, "onboarding"),
                                  (11, "developing"), (40, "developing"),
                                  (41, "established")]:
        (valor_home / "state.json").write_text(json.dumps({"briefing_count": count}))
        cmd_context(argparse.Namespace())
        result = json.loads(capsys.readouterr().out)
        assert result["briefing_meta"]["tone_tier"] == expected_tier, f"count={count}"


def test_context_work_area_refresh_not_due_at_count_zero(cli_db, capsys):
    """When briefing_count is 0 and work_areas exist, refresh should NOT be due."""
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "briefing_count": 0,
        "user_work_areas": ["topic1", "topic2"],
    }))
    cmd_context(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["briefing_meta"]["work_area_refresh_due"] is False


def test_context_work_area_refresh_due_when_empty(cli_db, capsys):
    """When work_areas is empty, refresh should be due regardless of count."""
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "briefing_count": 0,
        "user_work_areas": [],
    }))
    cmd_context(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["briefing_meta"]["work_area_refresh_due"] is True


def test_context_update_check_due_when_empty(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({"last_update_check": ""}))
    cmd_context(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["update_check_due"] is True


def test_context_empty_state(cli_db, capsys):
    """Context works even with no state.json at all."""
    cmd_context(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["coaching_mode"] == "ambient"
    assert result["levels"] == {"current": "", "target": "", "ceiling": ""}


# --- cmd_state_set ---

def test_state_set_basic(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({"existing": "value"}))
    cmd_state_set(argparse.Namespace(pairs=["key1", "hello", "key2", "world"]))
    state = json.loads((valor_home / "state.json").read_text())
    assert state["key1"] == "hello"
    assert state["key2"] == "world"
    assert state["existing"] == "value"


def test_state_set_increment(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({"briefing_count": 10}))
    cmd_state_set(argparse.Namespace(pairs=["briefing_count", "+1"]))
    state = json.loads((valor_home / "state.json").read_text())
    assert state["briefing_count"] == 11


def test_state_set_decrement(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({"counter": 5}))
    cmd_state_set(argparse.Namespace(pairs=["counter", "-2"]))
    state = json.loads((valor_home / "state.json").read_text())
    assert state["counter"] == 3


def test_state_set_increment_missing_key(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    cmd_state_set(argparse.Namespace(pairs=["new_count", "+5"]))
    state = json.loads((valor_home / "state.json").read_text())
    assert state["new_count"] == 5


def test_state_set_json_value(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    cmd_state_set(argparse.Namespace(pairs=["items", '["a","b"]']))
    state = json.loads((valor_home / "state.json").read_text())
    assert state["items"] == ["a", "b"]


def test_state_set_boolean_json(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    cmd_state_set(argparse.Namespace(pairs=["flag", "true"]))
    state = json.loads((valor_home / "state.json").read_text())
    assert state["flag"] is True


def test_state_set_increment_non_numeric(cli_db, capsys):
    """Increment on a non-numeric existing value resets to the delta."""
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({"count": "oops"}))
    cmd_state_set(argparse.Namespace(pairs=["count", "+1"]))
    state = json.loads((valor_home / "state.json").read_text())
    assert state["count"] == 1
    stderr = capsys.readouterr().err
    assert "not numeric" in stderr.lower() or "Warning" in stderr


# --- cmd_framework_slice ---

def test_framework_slice_extracts_levels(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "L3",
        "target_level": "L4",
        "ceiling_level": "L5",
    }))
    (valor_home / "career_framework.md").write_text(
        "# Career Framework\n\n"
        "### L3\n\nDoes basic work.\n\n"
        "### L4\n\nLeads features.\n\n"
        "### L5\n\nDrives architecture.\n\n"
        "### L6\n\nOrg-wide impact.\n"
    )
    cmd_framework_slice(argparse.Namespace())
    output = capsys.readouterr().out
    assert "### L3" in output
    assert "### L4" in output
    assert "### L5" in output
    assert "### L6" not in output
    assert "Does basic work." in output
    assert "Leads features." in output
    assert "Drives architecture." in output
    assert "Org-wide impact." not in output


def test_framework_slice_includes_values(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "L3",
        "target_level": "L4",
        "ceiling_level": "L5",
    }))
    (valor_home / "career_framework.md").write_text(
        "# Career Framework\n\n"
        "## Levels\n\n"
        "### L3\n\nDoes basic work.\n\n"
        "### L4\n\nLeads features.\n\n"
        "### L5\n\nDrives architecture.\n\n"
        "---\n\n"
        "## Company Values\n\n"
        "### Excellence\n\nWe strive for excellence.\n\n"
        "### Teamwork\n\nWe work together.\n"
    )
    cmd_framework_slice(argparse.Namespace())
    output = capsys.readouterr().out
    assert "### L3" in output
    assert "### L4" in output
    assert "### Excellence" in output
    assert "We strive for excellence." in output
    assert "### Teamwork" in output


def test_framework_slice_prefix_match(cli_db, capsys):
    """Headings like '### L3 - Software Engineer' match level 'L3'."""
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "L3",
        "target_level": "L4",
    }))
    (valor_home / "career_framework.md").write_text(
        "# Career Framework\n\n"
        "### L3 - Software Engineer\n\nEntry level work.\n\n"
        "### L4 - Senior Software Engineer\n\nLeads projects.\n\n"
        "### L5 - Staff Software Engineer\n\nArchitecture.\n"
    )
    cmd_framework_slice(argparse.Namespace())
    output = capsys.readouterr().out
    assert "Entry level work." in output
    assert "Leads projects." in output
    assert "Architecture." not in output


def test_framework_slice_missing_level(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "L3",
        "target_level": "L99",
        "ceiling_level": "",
    }))
    (valor_home / "career_framework.md").write_text(
        "### L3\n\nSolid contributor.\n"
    )
    cmd_framework_slice(argparse.Namespace())
    output = capsys.readouterr().out
    assert "### L3" in output
    assert "Solid contributor." in output
    assert "(Not found in career framework)" in output


def test_framework_slice_no_levels_configured(cli_db):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    with pytest.raises(SystemExit):
        cmd_framework_slice(argparse.Namespace())


# --- cmd_setup_status ---

def test_setup_status_unedited_template(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    (valor_home / "career_framework.md").write_text(
        "# Career Framework\n\n"
        "### [Level 1] - [Title]\n\nPlaceholder.\n\n"
        "### [Level 2] - [Title]\n\nPlaceholder.\n"
    )
    cmd_setup_status(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["framework_exists"] is True
    assert result["framework_is_template"] is True
    assert result["framework_levels"] == []
    assert result["levels_configured"] is False


def test_setup_status_configured_framework(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "L3",
        "target_level": "L4",
        "ceiling_level": "L5",
        "github_owner": "MyOrg",
        "jira_projects": ["PROJ"],
    }))
    (valor_home / "career_framework.md").write_text(
        "# Career Framework\n\n"
        "## Levels\n\n"
        "### L3 - Engineer\n\nDoes work.\n\n"
        "### L4 - Senior Engineer\n\nLeads work.\n\n"
        "### L5 - Staff Engineer\n\nArchitecture.\n"
    )
    cmd_setup_status(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["framework_is_template"] is False
    assert result["framework_levels"] == [
        "L3 - Engineer", "L4 - Senior Engineer", "L5 - Staff Engineer"
    ]
    assert result["levels_configured"] is True
    assert result["github_owner"] == "MyOrg"
    assert result["jira_projects"] == ["PROJ"]


def test_setup_status_no_framework_file(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    cmd_setup_status(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["framework_exists"] is False
    assert result["framework_levels"] == []


# --- cmd_framework_validate ---

VALID_FRAMEWORK = (
    "# Career Framework\n\n"
    "## Levels\n\n"
    "### IC3 - Engineer\n\n"
    "**Role summary:** Does work.\n\n"
    "**Competencies:**\n\n"
    "- **Subject Matter Expertise:** Writes code.\n"
    "- **Industry Knowledge:** Knows tools.\n"
    "- **Internal Collaboration:** Works with team.\n"
    "- **Autonomy & Scope:** Handles tasks.\n"
    "- **Leadership:** Suggests improvements.\n\n"
    "### IC4 - Senior Engineer\n\n"
    "**Role summary:** Leads work.\n\n"
    "**Competencies:**\n\n"
    "- **Subject Matter Expertise:** Designs systems.\n"
    "- **Industry Knowledge:** Tracks trends.\n"
    "- **Internal Collaboration:** Aligns cross-team.\n"
    "- **Autonomy & Scope:** Owns projects.\n"
    "- **Leadership:** Mentors others.\n\n"
    "### IC5 - Staff Engineer\n\n"
    "**Role summary:** Architecture.\n\n"
    "**Competencies:**\n\n"
    "- **Subject Matter Expertise:** Expert.\n"
    "- **Industry Knowledge:** Industry leader.\n"
    "- **Internal Collaboration:** Org-wide.\n"
    "- **Autonomy & Scope:** Strategic.\n"
    "- **Leadership:** Influences direction.\n\n"
    "---\n\n"
    "## Company Values\n\n"
    "### Excellence\n\nWe strive for excellence.\n"
)


def test_framework_validate_valid(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "IC3", "target_level": "IC4", "ceiling_level": "IC5",
    }))
    (valor_home / "career_framework.md").write_text(VALID_FRAMEWORK)
    cmd_framework_validate(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is True
    assert result["errors"] == []
    assert len(result["levels_found"]) == 3


def test_framework_validate_template(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    (valor_home / "career_framework.md").write_text(
        "# Career Framework\n\n### [Level 1] - [Title]\n"
    )
    cmd_framework_validate(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is False
    assert any("template" in e.lower() for e in result["errors"])


def test_framework_validate_missing_levels_section(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    (valor_home / "career_framework.md").write_text(
        "# Career Framework\n\n"
        "### IC3 - Engineer\n\nSome content.\n"
    )
    cmd_framework_validate(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is False
    assert any("## Levels" in e for e in result["errors"])


def test_framework_validate_missing_competency(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "IC3", "target_level": "IC4", "ceiling_level": "IC5",
    }))
    framework_missing_leadership = (
        "# Career Framework\n\n"
        "## Levels\n\n"
        "### IC3 - Engineer\n\n"
        "**Competencies:**\n\n"
        "- **Subject Matter Expertise:** Writes code.\n"
        "- **Industry Knowledge:** Knows tools.\n"
        "- **Internal Collaboration:** Works with team.\n"
        "- **Autonomy & Scope:** Handles tasks.\n\n"
        "### IC4 - Senior Engineer\n\n"
        "**Competencies:**\n\n"
        "- **Subject Matter Expertise:** Designs.\n"
        "- **Industry Knowledge:** Tracks.\n"
        "- **Internal Collaboration:** Aligns.\n"
        "- **Autonomy & Scope:** Owns.\n"
        "- **Leadership:** Mentors.\n\n"
        "### IC5 - Staff Engineer\n\n"
        "**Competencies:**\n\n"
        "- **Subject Matter Expertise:** Expert.\n"
        "- **Industry Knowledge:** Leader.\n"
        "- **Internal Collaboration:** Org-wide.\n"
        "- **Autonomy & Scope:** Strategic.\n"
        "- **Leadership:** Influences.\n"
    )
    (valor_home / "career_framework.md").write_text(framework_missing_leadership)
    cmd_framework_validate(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is False
    assert any("Leadership" in e and "IC3" in e for e in result["errors"])


def test_framework_validate_level_mismatch(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({
        "current_level": "L99", "target_level": "IC4", "ceiling_level": "IC5",
    }))
    (valor_home / "career_framework.md").write_text(VALID_FRAMEWORK)
    cmd_framework_validate(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is False
    assert any("L99" in e for e in result["errors"])


def test_framework_validate_no_file(cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    (valor_home / "state.json").write_text(json.dumps({}))
    cmd_framework_validate(argparse.Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is False
    assert any("not found" in e.lower() for e in result["errors"])
