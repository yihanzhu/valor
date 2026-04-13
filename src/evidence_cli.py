#!/usr/bin/env python3
"""Valor evidence store CLI.

Provides a clean interface for the Cursor skill (and the user) to interact
with the evidence SQLite database. Handles schema creation, migrations,
adding entries, querying, stats, and backup.

Usage:
    python3 src/evidence_cli.py add --activity pr_review --competency collaboration \
        --statement "Reviewed cross-team PR #892" --agent valor-morning-briefing
    python3 src/evidence_cli.py list --days 7
    python3 src/evidence_cli.py search "PR review"
    python3 src/evidence_cli.py export --format markdown --days 7
    python3 src/evidence_cli.py stats
    python3 src/evidence_cli.py status
    python3 src/evidence_cli.py backup
    python3 src/evidence_cli.py schema-version
    python3 src/evidence_cli.py weekly-summary-save --week-start 2026-04-06 \
        --week-end 2026-04-12 --summary '{"subject_matter": 3}' --narrative "Good week"
    python3 src/evidence_cli.py weekly-summary-list --limit 4
    python3 src/evidence_cli.py weekly-summary-get --week-start 2026-04-06
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path.home() / ".valor" / "evidence.sqlite"
BACKUP_DIR = Path.home() / ".valor" / "backups"

VALID_COMPETENCIES = (
    "subject_matter",
    "industry_knowledge",
    "collaboration",
    "autonomy_scope",
    "leadership",
)

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    activity TEXT NOT NULL,
    competency TEXT NOT NULL,
    evidence_statement TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    evidence_id TEXT DEFAULT '',
    agent TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_summary (
    id TEXT PRIMARY KEY,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    summary TEXT NOT NULL,
    gaps TEXT DEFAULT '[]',
    narrative TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_date ON evidence(date);
CREATE INDEX IF NOT EXISTS idx_evidence_competency ON evidence(competency);
CREATE INDEX IF NOT EXISTS idx_evidence_agent ON evidence(source_agent);
CREATE INDEX IF NOT EXISTS idx_weekly_start ON weekly_summary(week_start);
"""

MIGRATIONS: dict[int, str] = {
    # Future migrations go here:
    # 2: "ALTER TABLE evidence ADD COLUMN target_level TEXT DEFAULT 'l4';",
}


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_V1)

    current = conn.execute(
        "SELECT MAX(version) as v FROM schema_version"
    ).fetchone()["v"]
    if current is None:
        conn.execute(
            "INSERT INTO schema_version VALUES (?, ?)",
            (1, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        current = 1

    for version in sorted(MIGRATIONS.keys()):
        if version > current:
            conn.executescript(MIGRATIONS[version])
            conn.execute(
                "INSERT INTO schema_version VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            print(f"Applied migration v{version}")


def parse_competency(value: str) -> str:
    if value not in VALID_COMPETENCIES:
        valid = ", ".join(VALID_COMPETENCIES)
        raise argparse.ArgumentTypeError(
            f"invalid competency '{value}' (choose from: {valid})"
        )
    return value


def parse_ymd_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be in YYYY-MM-DD format") from exc


def iso_week_bounds(day: date | None = None) -> tuple[str, str]:
    current_day = day or datetime.now().date()
    week_start = current_day - timedelta(days=current_day.weekday())
    week_end = week_start + timedelta(days=7)
    return week_start.isoformat(), week_end.isoformat()


def validate_add_args(args: argparse.Namespace) -> None:
    if args.competency not in VALID_COMPETENCIES:
        valid = ", ".join(VALID_COMPETENCIES)
        raise ValueError(f"invalid competency '{args.competency}' (choose from: {valid})")
    if args.date is not None:
        parse_ymd_date(args.date)


def cmd_add(args: argparse.Namespace) -> None:
    validate_add_args(args)
    conn = get_conn()
    ensure_schema(conn)
    now = datetime.now(timezone.utc)
    target_date = parse_ymd_date(args.date) if args.date else now.strftime("%Y-%m-%d")

    existing = conn.execute(
        "SELECT id FROM evidence WHERE date = ? AND activity = ? "
        "AND source_agent = ? AND evidence_statement = ?",
        (target_date, args.activity, args.agent, args.statement),
    ).fetchone()
    if existing:
        conn.close()
        print(json.dumps({
            "status": "skipped",
            "reason": "duplicate",
            "existing_id": existing["id"],
            "activity": args.activity,
        }))
        return

    entry_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?)",
        (
            entry_id,
            target_date,
            args.activity,
            args.competency,
            args.statement,
            args.agent,
            now.isoformat(),
            json.dumps(args.metadata or {}),
        ),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"status": "ok", "id": entry_id, "activity": args.activity}))


def cmd_list(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)

    conditions: list[str] = []
    params: list = []

    if args.days:
        conditions.append(f"date >= date('now', '-{args.days} days')")
    if getattr(args, "from_date", None):
        conditions.append("date >= ?")
        params.append(args.from_date)
    if getattr(args, "to_date", None):
        conditions.append("date <= ?")
        params.append(args.to_date)
    if args.competency:
        conditions.append("competency = ?")
        params.append(args.competency)
    if getattr(args, "activity", None):
        conditions.append("activity = ?")
        params.append(args.activity)

    query = "SELECT * FROM evidence"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY date DESC, created_at DESC"
    if args.limit:
        query += " LIMIT ?"
        params.append(args.limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    entries = [dict(r) for r in rows]
    print(json.dumps(entries, indent=2))


def cmd_stats(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    week_start, week_end = iso_week_bounds()

    total = conn.execute("SELECT COUNT(*) as c FROM evidence").fetchone()["c"]

    by_competency = conn.execute(
        "SELECT competency, COUNT(*) as cnt FROM evidence "
        "GROUP BY competency ORDER BY cnt DESC"
    ).fetchall()

    this_week = conn.execute(
        "SELECT competency, COUNT(*) as cnt FROM evidence "
        "WHERE date >= ? AND date < ? "
        "GROUP BY competency ORDER BY cnt DESC"
        ,
        (week_start, week_end),
    ).fetchall()

    by_agent = conn.execute(
        "SELECT source_agent, COUNT(*) as cnt FROM evidence "
        "GROUP BY source_agent ORDER BY cnt DESC"
    ).fetchall()

    recent = conn.execute(
        "SELECT date, activity, competency, evidence_statement "
        "FROM evidence ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    conn.close()

    result = {
        "total_entries": total,
        "by_competency": {r["competency"]: r["cnt"] for r in by_competency},
        "this_week": {r["competency"]: r["cnt"] for r in this_week},
        "by_agent": {r["source_agent"]: r["cnt"] for r in by_agent},
        "recent": [dict(r) for r in recent],
    }
    print(json.dumps(result, indent=2))


def cmd_backup(args: argparse.Namespace) -> None:
    if not DB_PATH.exists():
        print("No database to back up.")
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"evidence_{ts}.sqlite"
    shutil.copy2(str(DB_PATH), str(dest))
    print(f"Backed up to {dest}")

    backups = sorted(BACKUP_DIR.glob("evidence_*.sqlite"))
    if len(backups) > 10:
        for old in backups[:-10]:
            old.unlink()
            print(f"Removed old backup: {old.name}")


def cmd_search(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    pattern = f"%{args.query}%"
    query = (
        "SELECT * FROM evidence "
        "WHERE evidence_statement LIKE ? "
        "ORDER BY date DESC, created_at DESC"
    )
    params: list = [pattern]
    if args.limit:
        query += " LIMIT ?"
        params.append(args.limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    entries = [dict(r) for r in rows]
    print(json.dumps(entries, indent=2))


def cmd_export(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)

    conditions: list[str] = []
    params: list = []

    if getattr(args, "days", None):
        conditions.append(f"date >= date('now', '-{args.days} days')")
    if getattr(args, "from_date", None):
        conditions.append("date >= ?")
        params.append(args.from_date)
    if getattr(args, "to_date", None):
        conditions.append("date <= ?")
        params.append(args.to_date)
    if getattr(args, "competency", None):
        conditions.append("competency = ?")
        params.append(args.competency)

    query = "SELECT * FROM evidence"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY date DESC, created_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    entries = [dict(r) for r in rows]

    if args.format == "json":
        print(json.dumps(entries, indent=2))
    elif args.format == "markdown":
        if not entries:
            print("_No evidence entries._")
            return
        by_date: dict[str, list[dict]] = {}
        for e in entries:
            by_date.setdefault(e["date"], []).append(e)
        for day, group in by_date.items():
            print(f"## {day}\n")
            for e in group:
                print(f"- **{e['competency']}** ({e['activity']}): {e['evidence_statement']}")
            print()


def _resolve_version() -> str:
    """Determine Valor version from VERSION file or state.json."""
    for candidate in [
        Path(__file__).resolve().parent / "VERSION",
        Path(__file__).resolve().parent.parent / "VERSION",
    ]:
        if candidate.exists():
            return candidate.read_text().strip()
    state_path = Path.home() / ".valor" / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        v = state.get("installed_version", "")
        if v:
            return v
    return "unknown"


def cmd_status(args: argparse.Namespace) -> None:
    valor_home = Path.home() / ".valor"
    state_path = valor_home / "state.json"

    status: dict = {"valor_home": str(valor_home)}
    status["version"] = _resolve_version()

    if state_path.exists():
        state = json.loads(state_path.read_text())
        status["current_level"] = state.get("current_level", "")
        status["target_level"] = state.get("target_level", "")
        status["ceiling_level"] = state.get("ceiling_level", "")
        status["coaching_mode"] = state.get("coaching_mode", "ambient")
        status["installed_version"] = state.get("installed_version", "")
        status["installed_at"] = state.get("installed_at", "")
        status["integrations"] = state.get("integrations", {})
    else:
        status["state"] = "not initialized (run install.sh)"

    if DB_PATH.exists():
        conn = get_conn()
        ensure_schema(conn)
        total = conn.execute("SELECT COUNT(*) as c FROM evidence").fetchone()["c"]
        week_start, week_end = iso_week_bounds()
        this_week = conn.execute(
            "SELECT COUNT(*) as c FROM evidence WHERE date >= ? AND date < ?",
            (week_start, week_end),
        ).fetchone()["c"]
        conn.close()
        status["evidence"] = {"total": total, "this_week": this_week}
    else:
        status["evidence"] = {"total": 0, "this_week": 0}

    print(json.dumps(status, indent=2))


def cmd_feedback_add(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO feedback (id, evidence_id, agent, feedback_type, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (entry_id, args.evidence_id or "", args.agent, args.type, now),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"status": "ok", "id": entry_id, "type": args.type}))


def cmd_feedback_stats(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    where = "WHERE agent = ?" if args.agent else ""
    params = (args.agent,) if args.agent else ()
    rows = conn.execute(
        f"SELECT feedback_type, COUNT(*) as cnt FROM feedback {where} "
        "GROUP BY feedback_type",
        params,
    ).fetchall()
    conn.close()
    print(json.dumps({r["feedback_type"]: r["cnt"] for r in rows}, indent=2))


def cmd_weekly_summary_save(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    summary_data = args.summary if isinstance(args.summary, str) else json.dumps(args.summary)
    gaps_data = args.gaps if isinstance(args.gaps, str) else json.dumps(args.gaps)
    conn.execute(
        "INSERT OR REPLACE INTO weekly_summary "
        "(id, week_start, week_end, summary, gaps, narrative, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entry_id, args.week_start, args.week_end, summary_data, gaps_data,
         args.narrative or "", now),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"status": "ok", "id": entry_id, "week_start": args.week_start}))


def cmd_weekly_summary_list(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT * FROM weekly_summary ORDER BY week_start DESC LIMIT ?",
        (args.limit,),
    ).fetchall()
    conn.close()
    entries = []
    for r in rows:
        entry = dict(r)
        entry["summary"] = json.loads(entry["summary"])
        entry["gaps"] = json.loads(entry["gaps"])
        entries.append(entry)
    print(json.dumps(entries, indent=2))


def cmd_weekly_summary_get(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    row = conn.execute(
        "SELECT * FROM weekly_summary WHERE week_start = ?",
        (args.week_start,),
    ).fetchone()
    conn.close()
    if not row:
        print(json.dumps({"status": "not_found", "week_start": args.week_start}))
        return
    entry = dict(row)
    entry["summary"] = json.loads(entry["summary"])
    entry["gaps"] = json.loads(entry["gaps"])
    print(json.dumps(entry, indent=2))


def cmd_schema_version(args: argparse.Namespace) -> None:
    conn = get_conn()
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT version, applied_at FROM schema_version ORDER BY version"
    ).fetchall()
    conn.close()
    for r in rows:
        print(f"v{r['version']} applied at {r['applied_at']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Valor evidence store CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Record an evidence entry")
    p_add.add_argument("--activity", required=True)
    p_add.add_argument("--competency", required=True, type=parse_competency)
    p_add.add_argument("--statement", required=True)
    p_add.add_argument("--agent", default="manual")
    p_add.add_argument("--date", default=None, type=parse_ymd_date,
                       help="Override date (YYYY-MM-DD) for backdating entries")
    p_add.add_argument("--metadata", type=json.loads, default=None)

    p_list = sub.add_parser("list", help="List evidence entries")
    p_list.add_argument("--days", type=int, default=None,
                        help="Show entries from the last N days")
    p_list.add_argument("--from", dest="from_date", type=parse_ymd_date, default=None,
                        help="Start date (YYYY-MM-DD, inclusive)")
    p_list.add_argument("--to", dest="to_date", type=parse_ymd_date, default=None,
                        help="End date (YYYY-MM-DD, inclusive)")
    p_list.add_argument("--competency", default=None, type=parse_competency)
    p_list.add_argument("--activity", default=None, help="Filter by activity type")
    p_list.add_argument("--limit", type=int, default=50)

    p_search = sub.add_parser("search", help="Full-text search on evidence statements")
    p_search.add_argument("query", help="Text to search for (case-insensitive LIKE)")
    p_search.add_argument("--limit", type=int, default=50)

    p_export = sub.add_parser("export", help="Export evidence (JSON or markdown)")
    p_export.add_argument("--format", choices=["json", "markdown"], default="json")
    p_export.add_argument("--days", type=int, default=None,
                          help="Export entries from the last N days")
    p_export.add_argument("--from", dest="from_date", type=parse_ymd_date, default=None,
                          help="Start date (YYYY-MM-DD, inclusive)")
    p_export.add_argument("--to", dest="to_date", type=parse_ymd_date, default=None,
                          help="End date (YYYY-MM-DD, inclusive)")
    p_export.add_argument("--competency", default=None, type=parse_competency,
                          help="Filter by competency")

    sub.add_parser("stats", help="Show evidence statistics")
    sub.add_parser("status", help="Unified Valor status view")
    sub.add_parser("backup", help="Backup the database")
    sub.add_parser("schema-version", help="Show schema version history")

    p_fb_add = sub.add_parser("feedback-add", help="Record feedback on an evidence entry")
    p_fb_add.add_argument("--evidence-id", default="",
                          help="ID of the evidence entry (optional)")
    p_fb_add.add_argument("--agent", required=True, help="Agent providing feedback")
    p_fb_add.add_argument("--type", required=True, help="Feedback type (e.g., helpful, not_relevant)")

    p_fb_stats = sub.add_parser("feedback-stats", help="Show feedback statistics")
    p_fb_stats.add_argument("--agent", default="", help="Filter by agent")

    p_ws_save = sub.add_parser("weekly-summary-save",
                               help="Save a weekly reflection summary")
    p_ws_save.add_argument("--week-start", required=True, type=parse_ymd_date,
                           help="Monday of the reflection week (YYYY-MM-DD)")
    p_ws_save.add_argument("--week-end", required=True, type=parse_ymd_date,
                           help="Sunday of the reflection week (YYYY-MM-DD)")
    p_ws_save.add_argument("--summary", required=True, type=json.loads,
                           help="JSON object with competency counts/notes")
    p_ws_save.add_argument("--gaps", type=json.loads, default=[],
                           help="JSON array of gap descriptions")
    p_ws_save.add_argument("--narrative", default="",
                           help="Free-text reflection narrative")

    p_ws_list = sub.add_parser("weekly-summary-list",
                               help="List recent weekly summaries")
    p_ws_list.add_argument("--limit", type=int, default=8)

    p_ws_get = sub.add_parser("weekly-summary-get",
                              help="Get a single weekly summary by week start date")
    p_ws_get.add_argument("--week-start", required=True, type=parse_ymd_date,
                          help="Monday of the week (YYYY-MM-DD)")

    args = parser.parse_args()
    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "search": cmd_search,
        "export": cmd_export,
        "stats": cmd_stats,
        "status": cmd_status,
        "backup": cmd_backup,
        "schema-version": cmd_schema_version,
        "feedback-add": cmd_feedback_add,
        "feedback-stats": cmd_feedback_stats,
        "weekly-summary-save": cmd_weekly_summary_save,
        "weekly-summary-list": cmd_weekly_summary_list,
        "weekly-summary-get": cmd_weekly_summary_get,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
