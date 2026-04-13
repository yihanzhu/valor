
from src.competency import Competency
from src.evidence_store import EvidenceEntry, FeedbackEntry, WeeklySummary, EvidenceStore


# --- EvidenceEntry dataclass ---

def test_evidence_entry_auto_generates_id():
    e = EvidenceEntry(
        activity="code_written",
        competency=Competency.SUBJECT_MATTER,
        evidence_statement="Wrote tests",
        source_agent="test",
    )
    assert e.id
    assert len(e.id) == 36  # UUID4 format


def test_evidence_entry_auto_generates_date():
    e = EvidenceEntry(
        activity="code_written",
        competency=Competency.SUBJECT_MATTER,
        evidence_statement="Wrote tests",
        source_agent="test",
    )
    assert e.date
    assert len(e.date) == 10  # YYYY-MM-DD


def test_evidence_entry_auto_generates_created_at():
    e = EvidenceEntry(
        activity="code_written",
        competency=Competency.SUBJECT_MATTER,
        evidence_statement="Wrote tests",
        source_agent="test",
    )
    assert e.created_at
    assert "T" in e.created_at  # ISO format


def test_evidence_entry_respects_explicit_values():
    e = EvidenceEntry(
        activity="code_written",
        competency=Competency.SUBJECT_MATTER,
        evidence_statement="Wrote tests",
        source_agent="test",
        id="my-id",
        date="2026-01-01",
        created_at="2026-01-01T00:00:00+00:00",
        metadata={"pr": 42},
    )
    assert e.id == "my-id"
    assert e.date == "2026-01-01"
    assert e.created_at == "2026-01-01T00:00:00+00:00"
    assert e.metadata == {"pr": 42}


# --- FeedbackEntry dataclass ---

def test_feedback_entry_auto_generates_id_and_created_at():
    f = FeedbackEntry(agent="agent-x", feedback_type="positive")
    assert f.id
    assert f.created_at
    assert "T" in f.created_at


# --- WeeklySummary dataclass ---

def test_weekly_summary_auto_generates_id_and_created_at():
    ws = WeeklySummary(
        week_start="2026-03-16",
        week_end="2026-03-22",
        summary={},
        gaps=[],
        narrative="",
    )
    assert ws.id
    assert ws.created_at


# --- EvidenceStore init/schema ---

def test_store_creates_db_file(tmp_db_path):
    store = EvidenceStore(tmp_db_path)
    assert tmp_db_path.exists()
    store.close()


def test_store_creates_parent_directories(tmp_path):
    nested_path = tmp_path / "a" / "b" / "c" / "test.sqlite"
    store = EvidenceStore(nested_path)
    assert nested_path.exists()
    store.close()


def test_store_creates_required_tables(store):
    tables = {
        row[0]
        for row in store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "evidence" in tables
    assert "feedback" in tables
    assert "weekly_summary" in tables


def test_store_conn_is_reused(store):
    conn1 = store.conn
    conn2 = store.conn
    assert conn1 is conn2


# --- add/get evidence ---

def test_add_evidence_returns_id(store, sample_evidence):
    returned_id = store.add_evidence(sample_evidence)
    assert returned_id == sample_evidence.id


def test_add_get_evidence_round_trip(store, sample_evidence):
    store.add_evidence(sample_evidence)
    retrieved = store.get_evidence(sample_evidence.id)
    assert retrieved is not None
    assert retrieved.id == sample_evidence.id
    assert retrieved.activity == sample_evidence.activity
    assert retrieved.competency == sample_evidence.competency
    assert retrieved.evidence_statement == sample_evidence.evidence_statement
    assert retrieved.source_agent == sample_evidence.source_agent


def test_get_evidence_nonexistent_returns_none(store):
    result = store.get_evidence("00000000-0000-0000-0000-000000000000")
    assert result is None


def test_add_evidence_upsert_replaces_existing(store, sample_evidence):
    store.add_evidence(sample_evidence)
    sample_evidence.evidence_statement = "Updated statement"
    store.add_evidence(sample_evidence)
    retrieved = store.get_evidence(sample_evidence.id)
    assert retrieved.evidence_statement == "Updated statement"


def test_add_evidence_metadata_serialized_correctly(store):
    entry = EvidenceEntry(
        activity="code_written",
        competency=Competency.SUBJECT_MATTER,
        evidence_statement="Test",
        source_agent="test",
        metadata={"pr_number": 99, "repo": "valor"},
    )
    store.add_evidence(entry)
    retrieved = store.get_evidence(entry.id)
    assert retrieved.metadata == {"pr_number": 99, "repo": "valor"}


# --- evidence_for_week ---

def test_evidence_for_week_includes_entries_in_range(store):
    in_week = EvidenceEntry(
        activity="code_written", competency=Competency.SUBJECT_MATTER,
        evidence_statement="In week", source_agent="test", date="2026-03-17",
    )
    out_of_week = EvidenceEntry(
        activity="code_written", competency=Competency.SUBJECT_MATTER,
        evidence_statement="Out of week", source_agent="test", date="2026-03-10",
    )
    store.add_evidence(in_week)
    store.add_evidence(out_of_week)
    results = store.evidence_for_week("2026-03-16")
    ids = [e.id for e in results]
    assert in_week.id in ids
    assert out_of_week.id not in ids


def test_evidence_for_week_empty(store):
    results = store.evidence_for_week("2026-03-16")
    assert results == []


def test_evidence_for_week_ordered_by_date(store):
    e1 = EvidenceEntry(
        activity="code_written", competency=Competency.SUBJECT_MATTER,
        evidence_statement="Earlier", source_agent="test", date="2026-03-17",
    )
    e2 = EvidenceEntry(
        activity="code_debugged", competency=Competency.SUBJECT_MATTER,
        evidence_statement="Later", source_agent="test", date="2026-03-18",
    )
    store.add_evidence(e1)
    store.add_evidence(e2)
    results = store.evidence_for_week("2026-03-16")
    assert len(results) == 2
    assert results[0].date <= results[1].date


# --- evidence_counts_for_week ---

def test_evidence_counts_for_week_counts_correctly(store):
    for _ in range(3):
        entry = EvidenceEntry(
            activity="code_written", competency=Competency.SUBJECT_MATTER,
            evidence_statement="Test", source_agent="test", date="2026-03-17",
        )
        store.add_evidence(entry)
    counts = store.evidence_counts_for_week("2026-03-16")
    assert counts.get(Competency.SUBJECT_MATTER, 0) == 3


# --- all_evidence ---

def test_all_evidence_returns_entries(populated_store):
    results = populated_store.all_evidence()
    assert len(results) == 3


def test_all_evidence_default_limit_at_most_200(populated_store):
    results = populated_store.all_evidence()
    assert len(results) <= 200


def test_all_evidence_custom_limit(populated_store):
    results = populated_store.all_evidence(limit=1)
    assert len(results) == 1


def test_all_evidence_ordered_newest_first(populated_store):
    results = populated_store.all_evidence()
    assert len(results) >= 2
    for i in range(len(results) - 1):
        assert results[i].date >= results[i + 1].date


# --- feedback ---

def test_add_feedback_returns_id(store, sample_feedback):
    returned_id = store.add_feedback(sample_feedback)
    assert returned_id == sample_feedback.id


def test_feedback_stats_all_agents(store):
    store.add_feedback(FeedbackEntry(agent="agent-a", feedback_type="positive"))
    store.add_feedback(FeedbackEntry(agent="agent-b", feedback_type="positive"))
    store.add_feedback(FeedbackEntry(agent="agent-a", feedback_type="negative"))
    stats = store.feedback_stats()
    assert stats["positive"] == 2
    assert stats["negative"] == 1


def test_feedback_stats_filtered_by_agent(store):
    store.add_feedback(FeedbackEntry(agent="agent-a", feedback_type="positive"))
    store.add_feedback(FeedbackEntry(agent="agent-b", feedback_type="positive"))
    stats = store.feedback_stats(agent="agent-a")
    assert stats.get("positive", 0) == 1
    # agent-b's entry should not be counted
    assert sum(stats.values()) == 1


def test_feedback_stats_empty_returns_empty_dict(store):
    stats = store.feedback_stats()
    assert stats == {}


# --- weekly summary ---

def test_save_get_weekly_summary_round_trip(store, sample_weekly_summary):
    store.save_weekly_summary(sample_weekly_summary)
    retrieved = store.get_weekly_summary(sample_weekly_summary.week_start)
    assert retrieved is not None
    assert retrieved.week_start == sample_weekly_summary.week_start
    assert retrieved.week_end == sample_weekly_summary.week_end
    assert retrieved.summary == sample_weekly_summary.summary
    assert retrieved.gaps == sample_weekly_summary.gaps
    assert retrieved.narrative == sample_weekly_summary.narrative


def test_get_weekly_summary_nonexistent_returns_none(store):
    result = store.get_weekly_summary("2020-01-01")
    assert result is None


def test_save_weekly_summary_upsert_replaces_existing(store, sample_weekly_summary):
    store.save_weekly_summary(sample_weekly_summary)
    sample_weekly_summary.narrative = "Updated narrative"
    store.save_weekly_summary(sample_weekly_summary)
    retrieved = store.get_weekly_summary(sample_weekly_summary.week_start)
    assert retrieved.narrative == "Updated narrative"


def test_recent_summaries_ordered_newest_first(store):
    summaries = [
        WeeklySummary(
            week_start=f"2026-03-{day:02d}",
            week_end=f"2026-03-{day + 6:02d}",
            summary={}, gaps=[], narrative="",
        )
        for day in [2, 9, 16]
    ]
    for s in summaries:
        store.save_weekly_summary(s)
    results = store.recent_summaries()
    assert len(results) == 3
    assert results[0].week_start >= results[1].week_start >= results[2].week_start


def test_recent_summaries_respects_limit(store):
    for day in [2, 9, 16]:
        s = WeeklySummary(
            week_start=f"2026-03-{day:02d}",
            week_end=f"2026-03-{day + 6:02d}",
            summary={}, gaps=[], narrative="",
        )
        store.save_weekly_summary(s)
    results = store.recent_summaries(limit=2)
    assert len(results) == 2


def test_recent_summaries_empty_returns_empty_list(store):
    results = store.recent_summaries()
    assert results == []


# --- close ---

def test_close_sets_conn_to_none(store):
    _ = store.conn  # force connection open
    store.close()
    assert store._conn is None


def test_close_is_idempotent(store):
    store.close()
    store.close()  # should not raise
