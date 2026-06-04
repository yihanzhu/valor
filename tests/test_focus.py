"""Tests for the project-focus resolver (src/focus.py)."""

import importlib.util
from datetime import date
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "focus", Path(__file__).resolve().parent.parent / "src" / "focus.py"
)
focus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(focus)

# Two biweekly syncs, one week apart in this fixture.
SYNCS = [
    {"project": "platform", "date": "2026-06-08"},   # a Monday
    {"project": "payments", "date": "2026-06-15"},    # the next Monday
]


# --- mode dispatch -------------------------------------------------------
def test_disabled_returns_not_enabled():
    out = focus.decide({"enabled": False}, SYNCS, today="2026-06-04")
    assert out == {"enabled": False}


def test_manual_mode_uses_configured_current():
    out = focus.decide(
        {"enabled": True, "mode": "manual", "current": "platform"},
        SYNCS, today="2026-06-04",
    )
    assert out["mode"] == "manual"
    assert out["current_project"] == "platform"
    assert out["transition_today"] is False


# --- meeting-derived focus ----------------------------------------------
def test_steady_state_focus_is_next_upcoming_sync():
    # Before the first sync: focus the project whose sync is coming up.
    out = focus.meeting_focus(SYNCS, today="2026-06-04")
    assert out["current_project"] == "platform"
    assert out["next_project"] == "payments"
    assert out["transition_today"] is False
    assert out["days_until_next_sync"] == 4


def test_sync_day_itself_keeps_current_focus():
    # On the sync day, focus is still that project (the flip is the day after).
    out = focus.meeting_focus(SYNCS, today="2026-06-08")
    assert out["current_project"] == "platform"
    assert out["transition_today"] is False


def test_flip_day_after_sync():
    # Day after the platform sync: focus flips to the next sync's project,
    # and the one-time transition flag fires.
    out = focus.meeting_focus(SYNCS, today="2026-06-09")
    assert out["current_project"] == "payments"
    assert out["next_project"] is None
    assert out["transition_today"] is True
    assert out["days_since_last_sync"] == 1


def test_all_syncs_past_falls_back_to_most_recent():
    out = focus.meeting_focus(SYNCS, today="2026-06-20")
    assert out["current_project"] == "payments"
    assert out["next_project"] is None
    assert out["transition_today"] is False


def test_no_syncs_fails_open_with_empty_focus():
    # Enabled but nothing configured: never hide everything — fail open.
    out = focus.meeting_focus([], today="2026-06-04")
    assert out["current_project"] == ""
    assert out["basis_sync"] is None


def test_accepts_datetime_strings():
    syncs = [{"project": "platform", "date": "2026-06-08T09:30:00-04:00"}]
    out = focus.meeting_focus(syncs, today="2026-06-04")
    assert out["current_project"] == "platform"


def test_non_after_sync_flip_suppresses_transition():
    out = focus.meeting_focus(SYNCS, today="2026-06-09", flip="manual")
    assert out["transition_today"] is False


def test_today_defaults_to_date_today(monkeypatch):
    # No explicit today -> uses date.today(); just assert it runs and is stable.
    out = focus.meeting_focus(SYNCS)
    assert "current_project" in out
    assert out["today"] == date.today().isoformat()


def test_malformed_sync_entries_are_skipped():
    syncs = [{"project": "platform"}, {"date": "2026-06-15"}, {"project": "payments", "date": "2026-06-15"}]
    out = focus.meeting_focus(syncs, today="2026-06-04")
    assert out["current_project"] == "payments"
