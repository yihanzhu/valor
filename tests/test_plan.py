"""Tests for the day-planning gap-fit pass (src/plan.py)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src import plan

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "src" / "plan.py"

# A fixed Wednesday; all times in one offset so the workday window aligns.
TZ = "-04:00"
def T(hhmm):  # noqa: E302
    return f"2026-06-03T{hhmm}:00{TZ}"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Point plan at an empty ~/.valor so config falls back to DEFAULTS."""
    monkeypatch.setattr(plan, "VALOR_HOME", tmp_path / ".valor")


def _ev(start, end, summary="mtg"):
    return {"start": T(start), "end": T(end), "summary": summary}


# --- shape classification ---
def test_shape_fragmented():
    for t in ["Merge PR #123", "Review #45 from a teammate", "Nudge review on #9",
              "Publish the notes", "Sync with the team"]:
        assert plan.classify_shape(t) == "fragmented_ok", t


def test_shape_deep():
    for t in ["Design the matching system", "Investigate the flaky test",
              "Draft the 1-pager", "Refactor the parser", "Research options"]:
        assert plan.classify_shape(t) == "deep_only", t


def test_shape_either():
    assert plan.classify_shape("Think about the roadmap") == "either"


def test_shape_deep_wins_tie():
    # "design review" contains both 'review' and 'design' -> deep work, not quick.
    assert plan.classify_shape("Design review for the new API") == "deep_only"


# --- gaps ---
def test_no_meeting_day_is_one_deep_gap():
    r = plan.fit([], ["Design X"], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["no_meeting_day"] is True
    assert len(r["gaps"]) == 1
    assert r["gaps"][0]["type"] == "deep"
    assert r["deep_gap_count"] == 1


def test_meeting_splits_into_pre_and_terminal_gaps():
    r = plan.fit([_ev("12:00", "13:00")], [], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    # 09:00-12:00 (pre-meeting, 3h deep) and 13:00-18:00 (terminal, 5h deep)
    assert len(r["gaps"]) == 2
    assert r["gaps"][0]["pre_meeting"] is True
    assert r["gaps"][1]["pre_meeting"] is False
    assert all(g["type"] == "deep" for g in r["gaps"])


def test_window_starts_at_now_not_workday_start():
    r = plan.fit([], ["Design X"], now=T("14:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    # only 14:00-18:00 is usable; morning is in the past
    assert r["gaps"][0]["start"] == T("14:00")


# --- event types (focus time / OOO / working-location) ---
def test_focus_time_is_not_busy():
    # Focus time is a deep-work slot to fill, not a meeting that blocks.
    ev = [{**_ev("10:00", "12:00"), "type": "focusTime"}]
    r = plan.fit(ev, [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    assert r["no_meeting_day"] is True
    assert len(r["gaps"]) == 1 and r["gaps"][0]["type"] == "deep"


def test_working_location_is_not_busy():
    ev = [{**_ev("09:00", "18:00"), "type": "workingLocation"}]
    r = plan.fit(ev, [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    assert r["no_meeting_day"] is True


def test_out_of_office_blocks_the_day():
    ev = [{**_ev("09:00", "18:00"), "type": "outOfOffice"}]
    r = plan.fit(ev, ["Merge PR #1"], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    assert r["gaps"] == []
    assert r["unassigned"]


def test_real_meeting_blocks_even_when_focus_time_overlaps():
    # Focus 10-12 (free) overlapping a real meeting 11-12 (busy): 11-12 stays busy.
    ev = [{**_ev("10:00", "12:00"), "type": "focusTime"},
          {**_ev("11:00", "12:00"), "type": "default"}]
    r = plan.fit(ev, [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    # busy = [11:00-12:00] -> gaps 09:00-11:00 and 12:00-18:00
    assert len(r["gaps"]) == 2
    assert r["gaps"][0]["end"][11:16] == "11:00"


def test_untyped_event_still_blocks():
    # Backward compat: an event with no `type` is treated as blocking.
    r = plan.fit([_ev("10:00", "12:00")], [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    assert r["no_meeting_day"] is False


# --- assignment ---
def test_deep_only_unassigned_on_fragmented_day():
    # Meetings chop the day so no gap reaches 2h.
    events = [_ev("10:30", "11:00"), _ev("12:30", "13:30"),
              _ev("14:30", "15:00"), _ev("16:00", "16:30")]
    r = plan.fit(events, ["Design the system"], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["deep_gap_count"] == 0
    assert not r["blocks"]
    assert r["unassigned"][0]["reason"] == "no deep block today"


def test_fragmented_task_assigned_and_preserves_deep_block():
    # One fragmented gap (09:00-10:00) + one deep gap (16:00-18:00).
    events = [_ev("10:00", "10:30"), _ev("10:30", "16:00")]
    r = plan.fit(events, ["Merge PR #1", "Design the system"], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    by_priority = {b["priority"]: b for b in r["blocks"]}
    assert by_priority["Merge PR #1"]["gap_type"] == "fragmented"   # took the small gap
    assert by_priority["Design the system"]["gap_type"] == "deep"   # deep block preserved for it
    assert not r["unassigned"]


def test_packs_multiple_tasks_into_one_gap():
    r = plan.fit([], ["Merge PR #1", "Review #2", "Nudge #3"], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    # three 30-min fragmented tasks pack into the morning of the big gap, sequentially
    assert len(r["blocks"]) == 3
    starts = [b["start"] for b in r["blocks"]]
    assert starts == [T("09:00"), T("09:30"), T("10:00")]


def test_workday_over_no_gaps():
    r = plan.fit([], ["Merge PR #1"], now=T("19:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["gaps"] == []
    assert r["unassigned"]


# --- CLI ---
def test_cli_fit(tmp_path):
    events = json.dumps([_ev("12:00", "13:00")])
    priorities = json.dumps(["Design the system", "Merge PR #1"])
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "fit", "--events", events,
         "--priorities", priorities, "--now", T("09:00"),
         "--workday-start", "09:00", "--workday-end", "18:00", "--deep-hours", "2"],
        capture_output=True, text=True, env={"HOME": str(tmp_path)},
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert len(out["blocks"]) == 2
    assert out["no_meeting_day"] is False


def test_cli_shape():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "shape", "--text", "Merge PR #1"],
        capture_output=True, text=True,
    )
    assert json.loads(r.stdout)["shape"] == "fragmented_ok"
