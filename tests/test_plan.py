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
        assert a["no_meeting_day"] is False and b["no_meeting_day"] is False
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
    assert out["no_meeting_day"] is False


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
