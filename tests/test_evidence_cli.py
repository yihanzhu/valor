import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta

import pytest

import src.evidence_cli as cli_module
from src.evidence_cli import (
    ensure_schema,
    cmd_add,
    cmd_list,
    cmd_search,
    cmd_stats,
    cmd_backup,
    cmd_schema_version,
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


def test_ensure_schema_sets_version_1(cli_db):
    db_path, _ = cli_db
    conn = _make_conn(db_path)
    ensure_schema(conn)
    version = conn.execute(
        "SELECT MAX(version) as v FROM schema_version"
    ).fetchone()["v"]
    assert version == 1
    conn.close()


def test_ensure_schema_is_idempotent(cli_db):
    db_path, _ = cli_db
    conn = _make_conn(db_path)
    ensure_schema(conn)
    ensure_schema(conn)  # should not raise or duplicate version row
    version = conn.execute(
        "SELECT MAX(version) as v FROM schema_version"
    ).fetchone()["v"]
    assert version == 1
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
    cmd_list(argparse.Namespace(days=None, competency=None, limit=50))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) >= 1


def test_cmd_list_competency_filter(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    _add_entry("pr_review_cross_scope", "collaboration", "Reviewed PR")
    capsys.readouterr()
    cmd_list(argparse.Namespace(days=None, competency="subject_matter", limit=50))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) >= 1
    assert all(e["competency"] == "subject_matter" for e in entries)


def test_cmd_list_limit(cli_db, capsys):
    for i in range(5):
        _add_entry(f"activity_{i}", "subject_matter", f"Statement {i}", agent=f"agent_{i}")
    capsys.readouterr()
    cmd_list(argparse.Namespace(days=None, competency=None, limit=2))
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) <= 2


def test_cmd_list_combined_filters(cli_db, capsys):
    _add_entry("code_written", "subject_matter", "Wrote code")
    _add_entry("pr_review", "collaboration", "Reviewed PR")
    capsys.readouterr()
    cmd_list(argparse.Namespace(days=30, competency="subject_matter", limit=50))
    entries = json.loads(capsys.readouterr().out)
    assert all(e["competency"] == "subject_matter" for e in entries)


def test_cmd_list_empty_db(cli_db, capsys):
    cmd_list(argparse.Namespace(days=None, competency=None, limit=50))
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
