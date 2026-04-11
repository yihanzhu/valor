import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.competency import Competency
from src.evidence_store import EvidenceEntry, FeedbackEntry, WeeklySummary, EvidenceStore


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "test.sqlite"


@pytest.fixture
def store(tmp_db_path):
    s = EvidenceStore(tmp_db_path)
    yield s
    s.close()


@pytest.fixture
def sample_evidence():
    return EvidenceEntry(
        activity="pr_review_own_scope",
        competency=Competency.AUTONOMY_SCOPE,
        evidence_statement="Reviewed PR #123 for auth module",
        source_agent="test-agent",
    )


@pytest.fixture
def sample_feedback():
    return FeedbackEntry(
        agent="test-agent",
        feedback_type="positive",
        evidence_id="test-evidence-id",
    )


@pytest.fixture
def sample_weekly_summary():
    return WeeklySummary(
        week_start="2026-03-16",
        week_end="2026-03-22",
        summary={"subject_matter": 3, "collaboration": 1},
        gaps=["leadership"],
        narrative="Strong week for technical work.",
    )


@pytest.fixture
def populated_store(store):
    entries = [
        EvidenceEntry(
            activity="pr_review_own_scope",
            competency=Competency.AUTONOMY_SCOPE,
            evidence_statement="Reviewed PR #123 for auth module",
            source_agent="valor-agent",
            date="2026-03-17",
        ),
        EvidenceEntry(
            activity="design_doc_written",
            competency=Competency.SUBJECT_MATTER,
            evidence_statement="Wrote design doc for caching layer",
            source_agent="valor-agent",
            date="2026-03-17",
        ),
        EvidenceEntry(
            activity="cross_team_alignment",
            competency=Competency.COLLABORATION,
            evidence_statement="Aligned with infra team on deployment strategy",
            source_agent="valor-morning",
            date="2026-03-18",
        ),
    ]
    for e in entries:
        store.add_evidence(e)
    return store


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    """Monkeypatches DB_PATH and BACKUP_DIR in evidence_cli to use tmp dirs."""
    import src.evidence_cli as cli_module
    db_path = tmp_path / "cli_test.sqlite"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(cli_module, "DB_PATH", db_path)
    monkeypatch.setattr(cli_module, "BACKUP_DIR", backup_dir)
    return db_path, backup_dir
