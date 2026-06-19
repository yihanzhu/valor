"""Tests for the project-focus resolver (src/focus.py)."""

import importlib.util
import json
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


def test_manual_mode_comparison_is_case_and_whitespace_insensitive():
    # L6: a hand-edited 'Manual' / ' manual ' must still dispatch to manual mode
    # and honor the user's set current_project, not silently fall through to
    # meeting-derived (which would resolve to the next upcoming sync instead).
    for raw in ("Manual", "MANUAL", " manual "):
        out = focus.decide(
            {"enabled": True, "mode": raw, "current": "payments"},
            SYNCS, today="2026-06-04",
        )
        assert out["mode"] == "manual", raw
        assert out["current_project"] == "payments", raw  # not 'platform'
        assert out["transition_today"] is False, raw


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


def test_flip_after_weekend_fires_on_monday():
    # M0: a Friday sync's hand-off must fire on the following Monday (Sat+Sun
    # gap, days_since==3), not be silently skipped because it wasn't days_since==1.
    syncs = [{"project": "platform", "date": "2026-06-05"},   # a Friday
             {"project": "payments", "date": "2026-06-12"}]   # the next Friday
    out = focus.meeting_focus(syncs, today="2026-06-08")       # the Monday
    assert out["current_project"] == "payments"
    assert out["days_since_last_sync"] == 3
    assert out["transition_today"] is True


def test_flip_does_not_fire_on_weekend_day():
    # The hand-off waits for the first working day -- it must not fire on the
    # Saturday immediately after a Friday sync.
    syncs = [{"project": "platform", "date": "2026-06-05"}]   # Friday
    out = focus.meeting_focus(syncs, today="2026-06-06")       # Saturday
    assert out["transition_today"] is False


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


def test_diff_syncs_flags_new_and_missing():
    configured = [{"project": "platform", "match": "Platform Sync"},
                  {"project": "payments", "match": "Payments Sync"}]
    observed = ["Weekly Platform Sync", "New Thing Biweekly Sync"]
    d = focus.diff_syncs(configured, observed)
    assert d["new"] == ["New Thing Biweekly Sync"]                       # unmatched observed
    assert d["missing"] == [{"project": "payments", "match": "Payments Sync"}]  # no occurrence


def test_diff_syncs_all_matched():
    d = focus.diff_syncs([{"project": "platform", "match": "platform sync"}],
                         ["Platform Sync (biweekly)"])
    assert d["new"] == [] and d["missing"] == []


def test_config_defaults_include_new_keys(tmp_path, monkeypatch):
    # schema-16: throttle fields gone; auto_sync_prep + parked_projects added.
    monkeypatch.setattr(focus, "VALOR_HOME", tmp_path / "empty")
    cfg = focus.focus_config()
    assert cfg["auto_sync_prep"] is True
    assert cfg["parked_projects"] == []
    assert "sync_scan_interval_days" not in cfg
    assert "last_sync_scan" not in cfg


# --- recurring-meeting catalog (categorized; proactive drift) -----------
def test_catalog_diff_seed_when_empty():
    d = focus.catalog_diff([], ["Standup", "Platform Sync"])
    assert d["seed"] is True                         # cold start
    assert d["new"] == ["Standup", "Platform Sync"]  # categorize all, surface unmapped
    assert d["gone"] == []


def test_catalog_diff_detects_new_and_gone():
    catalog = [{"title": "weekly standup", "category": "standup", "project": None},
               {"title": "platform sync", "category": "project_sync", "project": "platform"}]
    current = ["Weekly Standup", "New Project Kickoff"]  # platform sync gone; kickoff new
    d = focus.catalog_diff(catalog, current)
    assert d["seed"] is False
    assert d["new"] == ["New Project Kickoff"]
    assert [e["title"] for e in d["gone"]] == ["platform sync"]
    assert d["gone"][0]["project"] == "platform"  # gone carries category/project


def test_catalog_diff_normalizes_case_and_whitespace():
    d = focus.catalog_diff([{"title": "team   sync", "category": "project_sync", "project": "x"}], ["Team Sync"])
    assert d["new"] == [] and d["gone"] == []


def test_catalog_sync_writes_normalized_deduped(tmp_path, monkeypatch):
    home = tmp_path / ".valor"
    home.mkdir()
    (home / "state.json").write_text(json.dumps({"project_focus": {"enabled": True}}))
    monkeypatch.setattr(focus, "VALOR_HOME", home)
    n = focus.catalog_sync([
        {"title": "Beta  Sync", "category": "project_sync", "project": "beta"},
        {"title": "Alpha Standup", "category": "standup"},
        {"title": "Beta Sync", "category": "project_sync", "project": "beta"},  # dup by norm title
    ])
    assert n == 2
    cat = json.loads((home / "state.json").read_text())["project_focus"]["meeting_catalog"]
    assert [e["title"] for e in cat] == ["alpha standup", "beta sync"]  # normalized + sorted
    assert cat[0]["category"] == "standup" and cat[0]["project"] is None  # missing project -> None
    assert cat[1]["project"] == "beta"
    assert json.loads((home / "state.json").read_text())["project_focus"]["enabled"] is True


def test_catalog_sync_missing_state_returns_negative(tmp_path, monkeypatch):
    monkeypatch.setattr(focus, "VALOR_HOME", tmp_path / "nope")
    assert focus.catalog_sync([{"title": "X", "category": "other"}]) == -1


def test_catalog_sync_preserves_valid_source_only(tmp_path, monkeypatch):
    # The optional "source" (how the agent categorized: "signals" vs "fetch")
    # is persisted when valid, absent when missing, and dropped when bogus.
    home = tmp_path / ".valor"
    home.mkdir()
    (home / "state.json").write_text(json.dumps({"project_focus": {}}))
    monkeypatch.setattr(focus, "VALOR_HOME", home)
    focus.catalog_sync([
        {"title": "Signals Mtg", "category": "standup", "source": "signals"},
        {"title": "Fetched Mtg", "category": "project_sync", "project": "p",
         "source": "fetch"},
        {"title": "Bare Mtg", "category": "other"},                    # no source
        {"title": "Bad Mtg", "category": "other", "source": "guess"},   # invalid
    ])
    cat = json.loads((home / "state.json").read_text())["project_focus"]["meeting_catalog"]
    by = {e["title"]: e for e in cat}
    assert by["signals mtg"]["source"] == "signals"
    assert by["fetched mtg"]["source"] == "fetch"
    assert "source" not in by["bare mtg"]    # absent stays absent
    assert "source" not in by["bad mtg"]     # invalid value dropped, not stored


def test_catalog_sync_merges_with_existing_by_default(tmp_path, monkeypatch):
    # Regression: passing only the changed entries must NOT wipe the rest of the
    # catalog. The daily drift-check passes just the `new` meetings, so the
    # default has to be an upsert, not a full overwrite.
    home = tmp_path / ".valor"
    home.mkdir()
    (home / "state.json").write_text(json.dumps({"project_focus": {"meeting_catalog": [
        {"title": "alpha standup", "category": "standup", "project": None},
        {"title": "beta sync", "category": "project_sync", "project": "beta"},
    ]}}))
    monkeypatch.setattr(focus, "VALOR_HOME", home)
    # Add one new entry and update an existing one's category.
    n = focus.catalog_sync([
        {"title": "Gamma 1-1", "category": "1:1"},
        {"title": "Beta Sync", "category": "team_planning", "project": "beta"},
    ])
    assert n == 3  # alpha kept, beta updated, gamma added
    cat = json.loads((home / "state.json").read_text())["project_focus"]["meeting_catalog"]
    by = {e["title"]: e for e in cat}
    assert set(by) == {"alpha standup", "beta sync", "gamma 1-1"}
    assert by["beta sync"]["category"] == "team_planning"  # upsert overwrote
    assert by["alpha standup"]["category"] == "standup"    # untouched, not wiped


def test_catalog_sync_replace_resets_whole_catalog(tmp_path, monkeypatch):
    home = tmp_path / ".valor"
    home.mkdir()
    (home / "state.json").write_text(json.dumps({"project_focus": {"meeting_catalog": [
        {"title": "alpha standup", "category": "standup", "project": None},
        {"title": "beta sync", "category": "project_sync", "project": "beta"},
    ]}}))
    monkeypatch.setattr(focus, "VALOR_HOME", home)
    n = focus.catalog_sync([{"title": "Only Mtg", "category": "other"}], replace=True)
    assert n == 1
    cat = json.loads((home / "state.json").read_text())["project_focus"]["meeting_catalog"]
    assert [e["title"] for e in cat] == ["only mtg"]


def test_catalog_sync_remove_drops_entries(tmp_path, monkeypatch):
    home = tmp_path / ".valor"
    home.mkdir()
    (home / "state.json").write_text(json.dumps({"project_focus": {"meeting_catalog": [
        {"title": "alpha standup", "category": "standup", "project": None},
        {"title": "beta sync", "category": "project_sync", "project": "beta"},
    ]}}))
    monkeypatch.setattr(focus, "VALOR_HOME", home)
    # `remove` matches on normalized title; a miss is a harmless no-op.
    n = focus.catalog_sync([], remove=["Beta Sync", "never existed"])
    assert n == 1
    cat = json.loads((home / "state.json").read_text())["project_focus"]["meeting_catalog"]
    assert [e["title"] for e in cat] == ["alpha standup"]


# --- empty-input tripwires (guard the dropped-data failure class) ---
def test_empty_current_warning_fires_when_catalog_nonempty_but_no_current():
    catalog = [{"title": "alpha sync", "category": "project_sync", "project": "alpha"}]
    assert focus._empty_current_warning(catalog, [])             # all would look "gone"
    assert focus._empty_current_warning(catalog, ["alpha sync"]) is None  # have current
    assert focus._empty_current_warning([], []) is None          # empty catalog = seed, fine


def test_empty_syncs_warning_fires_when_focus_on_but_no_syncs():
    on = {"enabled": True, "mode": "meeting_derived"}
    assert focus._empty_syncs_warning(on, [])                    # focus on, no syncs
    assert focus._empty_syncs_warning(on, SYNCS) is None          # have syncs
    assert focus._empty_syncs_warning({"enabled": False}, []) is None      # focus off
    assert focus._empty_syncs_warning(
        {"enabled": True, "mode": "manual"}, []) is None           # manual needs no syncs
