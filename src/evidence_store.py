"""Promotion Evidence Store.

Stores competency evidence, feedback signals, and weekly summaries.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.competency import Competency

logger = logging.getLogger(__name__)


@dataclass
class EvidenceEntry:
    activity: str
    competency: Competency
    evidence_statement: str
    source_agent: str
    date: str = ""
    id: str = ""
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.date:
            self.date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class FeedbackEntry:
    agent: str
    feedback_type: str
    evidence_id: str = ""
    id: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class WeeklySummary:
    week_start: str
    week_end: str
    summary: dict
    gaps: list[str]
    narrative: str
    id: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


_SCHEMA = """
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


class EvidenceStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_schema(self):
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- Evidence CRUD --

    def add_evidence(self, entry: EvidenceEntry) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO evidence "
            "(id, date, activity, competency, evidence_statement, source_agent, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.id,
                entry.date,
                entry.activity,
                entry.competency.value,
                entry.evidence_statement,
                entry.source_agent,
                entry.created_at,
                json.dumps(entry.metadata),
            ),
        )
        self.conn.commit()
        logger.info("Evidence stored: %s [%s]", entry.activity, entry.competency.value)
        return entry.id

    def get_evidence(self, evidence_id: str) -> EvidenceEntry | None:
        row = self.conn.execute(
            "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        if not row:
            return None
        return EvidenceEntry(
            id=row["id"],
            date=row["date"],
            activity=row["activity"],
            competency=Competency(row["competency"]),
            evidence_statement=row["evidence_statement"],
            source_agent=row["source_agent"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata"]),
        )

    def evidence_for_week(self, week_start: str) -> list[EvidenceEntry]:
        rows = self.conn.execute(
            "SELECT * FROM evidence WHERE date >= ? AND date < date(?, '+7 days') "
            "ORDER BY date, created_at",
            (week_start, week_start),
        ).fetchall()
        return [
            EvidenceEntry(
                id=r["id"], date=r["date"], activity=r["activity"],
                competency=Competency(r["competency"]),
                evidence_statement=r["evidence_statement"],
                source_agent=r["source_agent"], created_at=r["created_at"],
                metadata=json.loads(r["metadata"]),
            )
            for r in rows
        ]

    def evidence_counts_for_week(self, week_start: str) -> dict[Competency, int]:
        rows = self.conn.execute(
            "SELECT competency, COUNT(*) as cnt FROM evidence "
            "WHERE date >= ? AND date < date(?, '+7 days') "
            "GROUP BY competency",
            (week_start, week_start),
        ).fetchall()
        return {Competency(r["competency"]): r["cnt"] for r in rows}

    def all_evidence(self, limit: int = 200) -> list[EvidenceEntry]:
        rows = self.conn.execute(
            "SELECT * FROM evidence ORDER BY date DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            EvidenceEntry(
                id=r["id"], date=r["date"], activity=r["activity"],
                competency=Competency(r["competency"]),
                evidence_statement=r["evidence_statement"],
                source_agent=r["source_agent"], created_at=r["created_at"],
                metadata=json.loads(r["metadata"]),
            )
            for r in rows
        ]

    # -- Feedback --

    def add_feedback(self, entry: FeedbackEntry) -> str:
        self.conn.execute(
            "INSERT INTO feedback (id, evidence_id, agent, feedback_type, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (entry.id, entry.evidence_id, entry.agent, entry.feedback_type, entry.created_at),
        )
        self.conn.commit()
        return entry.id

    def feedback_stats(self, agent: str = "") -> dict[str, int]:
        where = "WHERE agent = ?" if agent else ""
        params = (agent,) if agent else ()
        rows = self.conn.execute(
            f"SELECT feedback_type, COUNT(*) as cnt FROM feedback {where} "
            "GROUP BY feedback_type",
            params,
        ).fetchall()
        return {r["feedback_type"]: r["cnt"] for r in rows}

    # -- Weekly Summaries --

    def save_weekly_summary(self, summary: WeeklySummary) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO weekly_summary "
            "(id, week_start, week_end, summary, gaps, narrative, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                summary.id,
                summary.week_start,
                summary.week_end,
                json.dumps(summary.summary),
                json.dumps(summary.gaps),
                summary.narrative,
                summary.created_at,
            ),
        )
        self.conn.commit()
        return summary.id

    def get_weekly_summary(self, week_start: str) -> WeeklySummary | None:
        row = self.conn.execute(
            "SELECT * FROM weekly_summary WHERE week_start = ?", (week_start,)
        ).fetchone()
        if not row:
            return None
        return WeeklySummary(
            id=row["id"],
            week_start=row["week_start"],
            week_end=row["week_end"],
            summary=json.loads(row["summary"]),
            gaps=json.loads(row["gaps"]),
            narrative=row["narrative"],
            created_at=row["created_at"],
        )

    def recent_summaries(self, limit: int = 8) -> list[WeeklySummary]:
        rows = self.conn.execute(
            "SELECT * FROM weekly_summary ORDER BY week_start DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            WeeklySummary(
                id=r["id"], week_start=r["week_start"], week_end=r["week_end"],
                summary=json.loads(r["summary"]), gaps=json.loads(r["gaps"]),
                narrative=r["narrative"], created_at=r["created_at"],
            )
            for r in rows
        ]
