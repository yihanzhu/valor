"""Tests for the day-planning gap-fit pass (src/plan.py)."""

import json
import subprocess
import sys
import time
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


def _mtg(start, end, summary="standup"):
    # A real (collaborative) meeting — earns a post-meeting break.
    return {**_ev(start, end, summary), "is_meeting": True}


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
def test_no_busy_events_is_one_deep_gap():
    r = plan.fit([], ["Design X"], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["no_busy_events"] is True
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


def test_naive_event_time_is_local_not_utc(monkeypatch):
    # M1: a naive (offset-less) event time must be read as LOCAL wall-clock, not
    # UTC. Pin the local zone to EDT (-04:00, matching the suite's TZ constant)
    # so a naive 12:00 behaves identically to an explicit 12:00-04:00 -- i.e. the
    # meeting stays in the plan instead of being shifted out of the workday window.
    monkeypatch.setenv("TZ", "America/New_York")  # June -> EDT -04:00
    time.tzset()
    try:
        naive = {"start": "2026-06-03T12:00:00", "end": "2026-06-03T13:00:00", "summary": "mtg"}
        explicit = _ev("12:00", "13:00")  # carries -04:00 via T()
        a = plan.fit([naive], ["Design X"], now=T("09:00"),
                     workday_start="09:00", workday_end="18:00", deep_min_hours=2)
        b = plan.fit([explicit], ["Design X"], now=T("09:00"),
                     workday_start="09:00", workday_end="18:00", deep_min_hours=2)
        # Naive == explicit-local: the meeting does NOT shift or vanish.
        assert a["gaps"] == b["gaps"]
        assert a["no_busy_events"] is False and b["no_busy_events"] is False
        # The 12:00-13:00 meeting is honored: a pre-meeting gap exists.
        assert any(g.get("pre_meeting") for g in a["gaps"])
    finally:
        time.tzset()


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
    assert r["no_busy_events"] is True
    assert len(r["gaps"]) == 1 and r["gaps"][0]["type"] == "deep"


def test_working_location_is_not_busy():
    ev = [{**_ev("09:00", "18:00"), "type": "workingLocation"}]
    r = plan.fit(ev, [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    assert r["no_busy_events"] is True


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
    assert r["no_busy_events"] is False


# --- assignment ---
def test_long_deep_task_gets_partial_start_when_no_window_fits_whole():
    # Meetings chop the day so no gap fits a 150-min deep task whole. The task
    # must still START in a largest-size window (partial block, remainder
    # pushed) rather than waiting whole for a deep block that never comes.
    # Several gaps tie at 90m; strict > keeps the first in candidate order.
    events = [_ev("10:30", "11:00"), _ev("12:30", "13:30"),
              _ev("14:30", "15:00"), _ev("16:00", "16:30")]
    r = plan.fit(events, [{"text": "Design the system", "est_minutes": 150}], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["deep_gap_count"] == 0
    assert r["unassigned"] == []
    blk = r["blocks"][0]
    assert blk["partial"] is True
    assert blk["minutes"] == 90
    assert blk["remaining_minutes"] == 60


def test_short_deep_task_falls_back_to_fitting_fragment_window():
    # No 2h block all day, but a deep task that FITS a smaller window is placed
    # there rather than pushed -- otherwise a usable 90-min gap sits idle while
    # the task waits for a deep block that never comes. (The fix for the misshaped
    # "publish the 1-pager" case: a short task shouldn't be stranded by its shape.)
    events = [_ev("10:30", "11:00"), _ev("12:30", "13:30"),
              _ev("14:30", "15:00"), _ev("16:00", "16:30")]
    r = plan.fit(events, [{"text": "Design the system", "est_minutes": 60}], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["deep_gap_count"] == 0
    assert len(r["blocks"]) == 1
    assert r["blocks"][0]["gap_type"] == "fragmented"
    assert not r["unassigned"]


def test_fragmented_task_avoids_focus_window():
    # A focus-time gap (09:00-10:00) and a plain fragment window (11:15-12:00,
    # after a real meeting's break). A quick task should take the plain window and
    # leave the focus block free for deep work.
    events = [{"start": T("09:00"), "end": T("10:00"), "type": "focusTime"},
              _mtg("10:00", "11:00"),          # real meeting -> 15m break after
              _ev("12:00", "18:00")]           # fills the rest of the day
    r = plan.fit(events, ["Merge PR #1"], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert len(r["blocks"]) == 1
    blk = r["blocks"][0]
    assert blk["priority"] == "Merge PR #1"
    assert blk["start"] == T("11:15")                     # the plain window
    assert not (T("09:00") <= blk["start"] < T("10:00"))  # NOT the focus block


def test_open_windows_surface_unfilled_free_time():
    # Free time the planner couldn't auto-fill is surfaced (>= 15 min), including
    # the leftover of a gap a task only partially consumed.
    events = [_ev("10:00", "10:30"), _ev("12:00", "12:30")]   # two short holds
    r = plan.fit(events, [{"text": "Merge PR #1", "est_minutes": 30}], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["open_windows"]
    assert all(w["minutes"] >= 15 for w in r["open_windows"])
    # the 30m task consumed 09:00-09:30; its gap's leftover 09:30-10:00 is surfaced
    assert any(w["start"] == T("09:30") and w["minutes"] == 30 for w in r["open_windows"])


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


# --- per-task estimates ---
def test_per_task_est_minutes_overrides_shape_default():
    # Agent-provided durations win over the shape fallbacks (30/45/90).
    prios = [{"text": "Big pipeline change", "est_minutes": 120},
             {"text": "Quick publish", "est_minutes": 20}]
    # granularity=0 isolates the est-override from clock snapping (tested separately).
    r = plan.fit([], prios, now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2, granularity=0)
    by = {b["priority"]: b for b in r["blocks"]}
    assert by["Big pipeline change"]["minutes"] == 120
    assert by["Quick publish"]["minutes"] == 20
    # packed sequentially from the top of the gap
    assert by["Big pipeline change"]["start"] == T("09:00")
    assert by["Quick publish"]["start"] == T("11:00")


def test_invalid_est_minutes_falls_back_to_shape_default():
    r = plan.fit([], [{"text": "Merge PR #1", "est_minutes": 0}], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["blocks"][0]["minutes"] == 30  # fragmented_ok fallback, not 0


# --- post-meeting break ---
def test_break_after_real_meeting_only_not_at_day_start():
    # Meeting 11:00-12:00: the gap BEFORE it starts on time (no break at the
    # day's start); the gap AFTER it is pushed back 15 min.
    r = plan.fit([_mtg("11:00", "12:00")], [], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["gaps"][0]["start"] == T("09:00")   # pre-meeting gap not clipped
    assert r["gaps"][1]["start"] == T("12:15")   # post-meeting breather


def test_no_break_after_personal_hold():
    # A plain blocking event (no attendees, not flagged) is a personal hold, not
    # a meeting — no break after it.
    r = plan.fit([_ev("10:00", "11:00")], [], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["gaps"][1]["start"] == T("11:00")


def test_attendees_over_one_inferred_as_meeting():
    ev = [{**_ev("10:00", "11:00"), "attendees": ["a@example.com", "b@example.com"]}]
    r = plan.fit(ev, [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    assert r["gaps"][1]["start"] == T("11:15")  # break after the 10:00–11:00 meeting


def test_is_meeting_false_overrides_attendees():
    ev = [{**_ev("10:00", "11:00"), "attendees": ["a", "b", "c"], "is_meeting": False}]
    r = plan.fit(ev, [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2)
    assert r["gaps"][1]["start"] == T("11:00")  # explicit flag wins, no break


def test_break_can_erase_a_tiny_between_meeting_gap():
    # 10-min gap between two meetings, swallowed by the 15-min break.
    r = plan.fit([_mtg("10:00", "11:00"), _mtg("11:10", "12:00")], [], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    starts = [g["start"] for g in r["gaps"]]
    assert starts == [T("09:00"), T("12:15")]  # 11:00-11:10 erased


def test_break_minutes_zero_disables_break():
    r = plan.fit([_mtg("10:00", "11:00")], [], now=T("09:00"), workday_start="09:00",
                 workday_end="18:00", deep_min_hours=2, break_minutes=0)
    assert r["gaps"][1]["start"] == T("11:00")


# --- clock-granularity snapping ---
def test_block_start_snaps_up_to_granularity():
    # now 14:09 -> first block snaps up to 14:15 (clean, like a meeting)
    r = plan.fit([], [{"text": "Merge PR #1", "est_minutes": 30}], now=T("14:09"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["blocks"][0]["start"] == T("14:15")
    assert r["blocks"][0]["end"] == T("14:45")


def test_duration_rounds_up_to_granularity():
    r = plan.fit([], [{"text": "Quick publish", "est_minutes": 20}], now=T("09:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert r["blocks"][0]["minutes"] == 30          # 20 -> next 15-multiple
    assert r["blocks"][0]["end"] == T("09:30")


def test_packed_blocks_stay_on_clean_boundaries():
    r = plan.fit([], [{"text": "Merge #1", "est_minutes": 20}, {"text": "Review #2", "est_minutes": 25}],
                 now=T("14:09"), workday_start="09:00", workday_end="18:00", deep_min_hours=2)
    assert [b["start"] for b in r["blocks"]] == [T("14:15"), T("14:45")]


def test_granularity_zero_disables_snapping():
    r = plan.fit([], [{"text": "Merge PR #1", "est_minutes": 20}], now=T("14:09"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2, granularity=0)
    assert r["blocks"][0]["start"] == T("14:09")     # exact now, not snapped
    assert r["blocks"][0]["minutes"] == 20           # exact duration


def test_granularity_30_snaps_to_half_hours():
    r = plan.fit([], [{"text": "Merge PR #1", "est_minutes": 20}], now=T("14:09"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2, granularity=30)
    assert r["blocks"][0]["start"] == T("14:30")     # next :00/:30
    assert r["blocks"][0]["minutes"] == 30


# --- morning buffer + focus-time preference ---
def test_morning_buffer_delays_task_start():
    r = plan.fit([], [{"text": "Design X", "shape": "deep_only", "est_minutes": 120}],
                 now=T("09:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, morning_buffer=60)
    assert r["blocks"][0]["start"] == T("10:00")  # 09:00 + 60m AM-ritual buffer


def test_morning_buffer_zero_starts_at_workday():
    r = plan.fit([], [{"text": "Merge PR #1", "est_minutes": 30}],
                 now=T("09:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, morning_buffer=0)
    assert r["blocks"][0]["start"] == T("09:00")


def test_morning_buffer_ignored_when_now_is_later():
    r = plan.fit([], [{"text": "Merge PR #1", "est_minutes": 30}],
                 now=T("11:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, morning_buffer=60)
    assert r["blocks"][0]["start"] == T("11:00")  # now already past the floor


def test_deep_work_prefers_focus_time_gap():
    # A plain morning deep gap + an afternoon deep gap containing focus-time.
    # Deep work should prefer the focus gap, even though the morning one is earlier.
    ev = [_ev("12:00", "13:00"),  # personal hold (no attendees): splits the day, no break
          {"start": T("14:00"), "end": T("16:30"), "type": "focusTime"}]
    r = plan.fit(ev, [{"text": "Design the system", "shape": "deep_only", "est_minutes": 120}],
                 now=T("09:00"), workday_start="09:00", workday_end="17:00",
                 deep_min_hours=2, morning_buffer=0)
    assert r["blocks"][0]["start"] == T("13:00")  # the focus gap, not the 09:00 one


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
    assert out["no_busy_events"] is False


def test_cli_shape():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "shape", "--text", "Merge PR #1"],
        capture_output=True, text=True,
    )
    assert json.loads(r.stdout)["shape"] == "fragmented_ok"


def test_cli_fit_break_minutes(tmp_path):
    events = json.dumps([_mtg("10:00", "11:00")])
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "fit", "--events", events, "--priorities", "[]",
         "--now", T("09:00"), "--workday-start", "09:00", "--workday-end", "18:00",
         "--deep-hours", "2", "--break-minutes", "30"],
        capture_output=True, text=True, env={"HOME": str(tmp_path)},
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["gaps"][1]["start"] == T("11:30")  # 30-min break applied via CLI


# --- empty-calendar sanity warning (guards the dropped-calendar bug) ---
def test_empty_calendar_warning_fires_for_priorities_without_events():
    w = plan._empty_calendar_warning([], ["Publish the 1-pager"])
    assert w and "EMPTY calendar" in w


def test_no_warning_when_events_present():
    assert plan._empty_calendar_warning(
        [_ev("12:00", "13:00")], ["Publish the 1-pager"]) is None


def test_no_warning_when_no_priorities():
    # A genuinely empty day with nothing to schedule is fine — no false alarm.
    assert plan._empty_calendar_warning([], []) is None


def test_cmd_fit_emits_warning_on_stderr_only(capsys):
    import types
    args = types.SimpleNamespace(
        events="[]", priorities='["Publish the 1-pager"]', now=T("09:00"),
        workday_start="09:00", workday_end="18:00", deep_hours=2,
        break_minutes=None, granularity=None, morning_buffer=None,
        pre_meeting_prep=None,
    )
    plan.cmd_fit(args)
    out = capsys.readouterr()
    assert "EMPTY calendar" in out.err       # warning -> stderr
    assert "EMPTY calendar" not in out.out    # stdout stays clean JSON
    json.loads(out.out)                       # stdout still parses


# --- regression: a real (social + lunch) day never plans over busy events ---
def test_blocks_never_overlap_busy_events():
    # Mirrors the bug report: a focus block, an accepted 2h social, lunch, and a
    # late hold. The one free window is 14:00-15:30 — tasks must land there and
    # never on top of a busy event (the original bug packed them over the social
    # because the caller passed an empty event list).
    events = [
        {**_ev("10:00", "12:00"), "type": "focusTime"},   # fillable, not busy
        _ev("12:00", "14:00", "Team social"),             # accepted -> busy
        _ev("13:00", "13:45", "Lunch"),                   # personal hold -> busy
        _ev("15:30", "17:00", "Hold"),                    # busy
    ]
    priorities = [
        {"text": "Publish the 1-pager", "shape": "either", "est_minutes": 30},
        {"text": "Close out the ticket", "shape": "either", "est_minutes": 30},
        {"text": "Prep the sync", "shape": "either", "est_minutes": 30},
    ]
    r = plan.fit(events, priorities, now=T("12:00"),
                 workday_start="09:00", workday_end="18:00", deep_min_hours=2)

    assert r["unassigned"] == []
    assert len(r["blocks"]) == 3

    busy = [("12:00", "14:00"), ("13:00", "13:45"), ("15:30", "17:00")]
    for b in r["blocks"]:
        bs, be = plan._parse_iso(b["start"]), plan._parse_iso(b["end"])
        # every block sits inside the only real gap, 14:00-15:30 ...
        assert bs >= plan._parse_iso(T("14:00"))
        assert be <= plan._parse_iso(T("15:30"))
        # ... and overlaps none of the busy events
        for s, e in busy:
            assert not (bs < plan._parse_iso(T(e)) and plan._parse_iso(T(s)) < be), \
                f"{b['priority']} overlaps busy {s}-{e}"


# --- pre-meeting prep blocks ---
def _prep(start, end, summary="Proj Sync"):
    # a prep-worthy meeting (project_sync / external)
    return {**_mtg(start, end, summary), "prep": True}


def test_prep_block_reserved_immediately_before_meeting():
    r = plan.fit([_prep("14:30", "15:00", "Metadata Sync")], [],
                 now=T("09:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, pre_meeting_prep=30)
    assert len(r["prep_blocks"]) == 1
    b = r["prep_blocks"][0]
    assert b["start"] == T("14:00") and b["end"] == T("14:30")
    assert b["for_meeting"] == "Metadata Sync" and b["adjacent"] is True
    assert r["prep_unassigned"] == []


def test_no_prep_block_without_prep_flag():
    # a plain meeting (no prep flag) earns no prep block -- back-compat
    r = plan.fit([_mtg("14:30", "15:00", "Standup")], [],
                 now=T("09:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, pre_meeting_prep=30)
    assert r["prep_blocks"] == [] and r["prep_unassigned"] == []


def test_prep_unplaceable_is_flagged():
    # a future sync at workday start with no room before it -> flagged, not dropped
    r = plan.fit([_prep("09:00", "09:30", "Early Sync")], [],
                 now=T("08:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, pre_meeting_prep=30)
    assert r["prep_blocks"] == []
    assert len(r["prep_unassigned"]) == 1
    assert r["prep_unassigned"][0]["for_meeting"] == "Early Sync"


def test_prep_falls_back_to_earlier_gap_when_back_to_back():
    # a prep sync right after another meeting -> prep lands in the earlier gap
    r = plan.fit([_mtg("13:00", "14:00", "Team Mtg"), _prep("14:00", "14:30", "Proj Sync")],
                 [], now=T("09:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, pre_meeting_prep=30)
    assert len(r["prep_blocks"]) == 1
    b = r["prep_blocks"][0]
    assert b["adjacent"] is False
    assert b["end"] == T("13:00")  # tail of the morning gap, before the 13:00 mtg


def test_prep_reservation_shrinks_the_gap():
    # the reserved prep time is removed from the gaps tasks can use
    r = plan.fit([_prep("11:00", "11:30", "Sync")], [],
                 now=T("09:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, pre_meeting_prep=30)
    ends = [g["end"] for g in r["gaps"]]
    assert T("10:30") in ends      # morning gap now ends at the prep start
    assert T("11:00") not in ends  # not at the meeting start


def test_pre_meeting_prep_zero_disables():
    r = plan.fit([_prep("14:30", "15:00", "Sync")], [],
                 now=T("09:00"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, pre_meeting_prep=0)
    assert r["prep_blocks"] == [] and r["prep_unassigned"] == []


def test_cli_fit_pre_meeting_prep(tmp_path):
    events = json.dumps([{"start": T("14:30"), "end": T("15:00"),
                          "summary": "Sync", "is_meeting": True, "prep": True}])
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "fit", "--events", events, "--priorities", "[]",
         "--now", T("09:00"), "--workday-start", "09:00", "--workday-end", "18:00",
         "--deep-hours", "2", "--pre-meeting-prep", "30"],
        capture_output=True, text=True, env={"HOME": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert len(out["prep_blocks"]) == 1
    assert out["prep_blocks"][0]["start"] == T("14:00")


# --- L3: malformed planning config in state.json falls back to defaults ---
def _write_planning_state(tmp_path, planning):
    home = tmp_path / ".valor"
    home.mkdir(parents=True, exist_ok=True)
    (home / "state.json").write_text(json.dumps({"planning": planning}))


def test_bad_config_types_fall_back_to_defaults(tmp_path):
    # A hand-edited state.json with wrong-typed planning values must not crash
    # fit(); each bad value falls back to its default.
    _write_planning_state(tmp_path, {
        "workday_start": 9, "deep_min_hours": "two",
        "block_granularity_minutes": "15", "est_minutes": {"fragmented_ok": "lots"},
    })
    cfg = plan.planning_config()
    assert cfg["workday_start"] == "09:00"
    assert cfg["deep_min_hours"] == 2.0
    assert cfg["block_granularity_minutes"] == 15
    assert cfg["est_minutes"]["fragmented_ok"] == 30


def test_good_config_types_are_honored(tmp_path):
    _write_planning_state(tmp_path, {
        "workday_start": "08:30", "deep_min_hours": 3,
        "morning_buffer_minutes": 45, "est_minutes": {"deep_only": 120},
    })
    cfg = plan.planning_config()
    assert cfg["workday_start"] == "08:30"
    assert cfg["deep_min_hours"] == 3
    assert cfg["morning_buffer_minutes"] == 45
    assert cfg["est_minutes"]["deep_only"] == 120


def test_bad_config_does_not_crash_fit(tmp_path):
    _write_planning_state(tmp_path, {
        "workday_start": 9, "deep_min_hours": "two", "block_granularity_minutes": "15",
    })
    # No explicit kwargs -> fit() pulls from planning_config(), which must absorb
    # the bad types and return a usable plan rather than raising.
    r = plan.fit([], ["Design X"], now=T("09:00"))
    assert isinstance(r, dict) and r["gaps"]


# --- L4: junk priority entries are skipped, not crash the whole plan ---
def test_junk_priority_entries_are_skipped():
    r = plan.fit(
        [], ["Design X", None, 42, {"text": "Merge PR #1", "est_minutes": 30}],
        now=T("09:00"), workday_start="09:00", workday_end="18:00", deep_min_hours=2,
    )
    # The None and 42 produced no blocks and no crash; the str + dict survived.
    assert {b["priority"] for b in r["blocks"]} == {"Design X", "Merge PR #1"}


# --- Partial deep-work starts (don't leave focus time empty) ---------------

def test_deep_task_too_big_gets_partial_start_in_focus_window():
    """A 150m deep task whose only real window is the focus block must START
    there (partial block, remainder pushed) — not leave it empty (the
    2026-06-12 incident: a focus window sat open while the task waited)."""
    events = [
        _mtg("09:00", "10:00"),
        {**_ev("10:00", "12:00", "Focus time"), "type": "focusTime"},
        _ev("12:00", "17:30", "busy"),
    ]
    r = plan.fit(events, [{"text": "Pre-prod pipeline test implementation",
                           "est_minutes": 150}],
                 now=T("08:30"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, granularity=15)
    assert r["unassigned"] == []
    blk = next(b for b in r["blocks"] if "Pre-prod" in b["priority"])
    assert blk["partial"] is True
    assert blk["minutes"] >= plan.PARTIAL_MIN_MINUTES
    assert blk["remaining_minutes"] == 150 - blk["minutes"]


def test_deep_task_stays_unassigned_below_partial_minimum():
    """No window >= PARTIAL_MIN_MINUTES -> unassigned as before (a sub-hour
    'start' isn't worth the context switch)."""
    events = [_ev("09:00", "16:45", "busy")]  # leaves only 17:00-18:00? no: 45m + tail
    r = plan.fit(events, [{"text": "Pre-prod pipeline test implementation",
                           "est_minutes": 150}],
                 now=T("08:30"), workday_start="09:00", workday_end="17:30",
                 deep_min_hours=2, granularity=15)
    assert [u["priority"] for u in r["unassigned"]] == ["Pre-prod pipeline test implementation"]
    assert all(not b.get("partial") for b in r["blocks"])


def test_whole_fit_still_preferred_over_partial():
    """A task that fits a window whole is placed whole — partial is a fallback."""
    events = [_mtg("13:00", "14:00")]
    r = plan.fit(events, [{"text": "Design the migration", "est_minutes": 120}],
                 now=T("08:30"), workday_start="09:00", workday_end="18:00",
                 deep_min_hours=2, granularity=15)
    blk = next(b for b in r["blocks"] if "Design" in b["priority"])
    assert not blk.get("partial")
    assert blk["minutes"] == 120
