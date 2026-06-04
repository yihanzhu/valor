#!/usr/bin/env python3
"""Valor project-focus resolver.

Some users rotate which project they focus on week to week — often driven by a
recurring per-project sync meeting (you work on whichever project's sync is
coming up next, so you walk in prepared). When that's the case the briefing
should plan around the *current* project and hide the others, so the day-plan
doesn't mix in work the user has deliberately deferred to a later cycle.

This is opt-in customization: it does nothing unless `project_focus.enabled` is
set in state.json (a one-project user never sees it). Like plan.py / verify.py
it is pure logic + a CLI — the AGENT reads the calendar (matching event titles
to the configured syncs) and passes the dated upcoming syncs here; this module
only derives the current focus and the next transition. It never touches the
network.

Two modes:
  * meeting_derived (default): focus = the project whose sync is the next one
    at or after today. After a sync passes, the next sync's project takes over,
    so the focus "flips" the day after each sync. `transition_today` is true on
    a flip day (a sync fell yesterday) so the briefing can show a one-time
    "focus now shifts to X" hand-off; `days_since_last_sync` lets the prompt be
    lenient across weekends / skipped briefings.
  * manual: focus = `project_focus.current`, unchanged until the user edits it.

Ticket -> project classification is NOT done here (it needs to read the ticket).
The agent does that semantically against the resolved current project. If the
focus can't be determined (enabled but no syncs configured), `current_project`
is "" and the briefing should fail OPEN (no filtering) rather than hide
everything.

CLI:
    focus.py resolve --syncs <json|-> [--today YYYY-MM-DD]
        # syncs: [{"project": "platform", "date": "2026-06-08"}, ...]
    focus.py config            # print the project_focus block (or {enabled:false})

All output is JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

VALOR_HOME = Path.home() / ".valor"

DEFAULTS = {
    "enabled": False,
    "mode": "meeting_derived",  # or "manual"
    "current": "",              # used by manual mode
    "flip": "after_sync",       # when focus changes relative to a sync
    "syncs": [],                # [{"project","match"}] — agent matches titles
}


def _read_state() -> dict:
    try:
        return json.loads((VALOR_HOME / "state.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def focus_config() -> dict:
    cfg = dict(DEFAULTS)
    state_cfg = _read_state().get("project_focus", {})
    if isinstance(state_cfg, dict):
        for k in DEFAULTS:
            if k in state_cfg:
                cfg[k] = state_cfg[k]
    return cfg


def _parse_day(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value)
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text)


def meeting_focus(syncs, today=None, flip="after_sync") -> dict:
    """syncs: list of {"project","date"}. Derive the focus from sync dates.

    current = the next sync at or after today (you work toward the upcoming
    sync). The day after a sync passes, the following sync becomes the next one,
    so the focus flips. Fails OPEN (current_project="") when no syncs are known.
    """
    today = _parse_day(today) if today else date.today()

    dated = []
    for s in syncs or []:
        try:
            dated.append({"project": s["project"], "date": _parse_day(s["date"])})
        except (KeyError, ValueError, TypeError):
            continue
    dated.sort(key=lambda s: s["date"])

    upcoming = [s for s in dated if s["date"] >= today]
    past = [s for s in dated if s["date"] < today]

    current = upcoming[0] if upcoming else (past[-1] if past else None)
    nxt = upcoming[1] if len(upcoming) > 1 else None

    most_recent_past = past[-1]["date"] if past else None
    days_since = (today - most_recent_past).days if most_recent_past else None
    days_until = (current["date"] - today).days if current and current["date"] >= today else None
    transition_today = (flip == "after_sync" and days_since == 1)

    return {
        "enabled": True,
        "mode": "meeting_derived",
        "today": today.isoformat(),
        "current_project": current["project"] if current else "",
        "basis_sync": (
            {"project": current["project"], "date": current["date"].isoformat()}
            if current else None
        ),
        "next_project": nxt["project"] if nxt else None,
        "next_sync_date": nxt["date"].isoformat() if nxt else None,
        "transition_today": transition_today,
        "days_since_last_sync": days_since,
        "days_until_next_sync": days_until,
    }


def decide(config, syncs, today=None) -> dict:
    """Top-level: dispatch on mode. Returns {enabled:false} when off."""
    if not config.get("enabled"):
        return {"enabled": False}
    if config.get("mode") == "manual":
        return {
            "enabled": True,
            "mode": "manual",
            "current_project": config.get("current", ""),
            "transition_today": False,
            "next_project": None,
            "next_sync_date": None,
        }
    return meeting_focus(syncs, today, flip=config.get("flip", "after_sync"))


# --- CLI -----------------------------------------------------------------
def _load_json_arg(value: str):
    if value == "-":
        return json.loads(sys.stdin.read() or "[]")
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text())
    return json.loads(value)


def cmd_resolve(args: argparse.Namespace) -> None:
    syncs = _load_json_arg(args.syncs) if args.syncs else []
    print(json.dumps(decide(focus_config(), syncs, today=args.today), indent=2))


def cmd_config(args: argparse.Namespace) -> None:
    print(json.dumps(focus_config(), indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Valor project-focus resolver")
    sub = ap.add_subparsers(dest="command", required=True)

    p_res = sub.add_parser("resolve", help="Resolve the current project focus")
    p_res.add_argument(
        "--syncs", default="[]",
        help='Dated syncs JSON: [{"project","date"}] (or @file or -)',
    )
    p_res.add_argument("--today", default=None, help="YYYY-MM-DD override (testing)")

    sub.add_parser("config", help="Print the project_focus config block")

    args = ap.parse_args()
    {"resolve": cmd_resolve, "config": cmd_config}[args.command](args)


if __name__ == "__main__":
    main()
