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
    # Periodic mapping re-check: every N days the briefing re-scans for sync
    # meetings and confirms whether the user's project set changed.
    "sync_scan_interval_days": 14,
    "last_sync_scan": "",       # YYYY-MM-DD of the last re-check
    # Catalog of known recurring meetings, each categorized (project_sync, 1:1,
    # standup, social, ...). A meeting NOT in the catalog is a "new — research
    # it" signal. Entries: {"title", "category", "project"}.
    "meeting_catalog": [],
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


# --- periodic mapping re-check -------------------------------------------
def scan_due(config, today=None) -> bool:
    """True when the sync->project mapping is due for a re-check (projects may
    have changed). False when focus is off. A never-scanned or unparseable
    last_sync_scan is treated as due."""
    if not config.get("enabled"):
        return False
    last = config.get("last_sync_scan") or ""
    if not last:
        return True
    try:
        last_d = _parse_day(last)
    except (ValueError, TypeError):
        return True
    today = _parse_day(today) if today else date.today()
    return (today - last_d).days >= int(config.get("sync_scan_interval_days", 14))


def diff_syncs(configured, observed_titles) -> dict:
    """Compare the configured syncs to recurring sync-like meeting titles the
    agent observed on the calendar. Returns:
      * new     — observed titles matching no configured pattern (a project may
                  have been added; the agent should pre-filter to plausible
                  rotation syncs, then the user confirms before anything changes)
      * missing — configured syncs with no upcoming occurrence (a project may
                  have ended)
    Pure set logic; never mutates state."""
    pairs = [(c.get("project", ""), (c.get("match") or "")) for c in (configured or [])]
    obs = [t for t in (observed_titles or []) if t]
    new = [t for t in obs if not any(m and m.lower() in t.lower() for _, m in pairs)]
    missing = [
        {"project": p, "match": m}
        for p, m in pairs
        if m and not any(m.lower() in t.lower() for t in obs)
    ]
    return {"new": new, "missing": missing}


def mark_scanned(today=None) -> str:
    """Stamp project_focus.last_sync_scan = today in state.json (best-effort,
    preserving the rest of state). Returns the date written, or "" if state
    couldn't be read/written."""
    state_path = VALOR_HOME / "state.json"
    try:
        state = json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        return ""
    pf = state.get("project_focus")
    if not isinstance(pf, dict):
        pf = {}
        state["project_focus"] = pf
    stamp = _parse_day(today).isoformat() if today else date.today().isoformat()
    pf["last_sync_scan"] = stamp
    try:
        state_path.write_text(json.dumps(state, indent=2))
    except OSError:
        return ""
    return stamp


# --- recurring-meeting catalog (categorized; proactive drift detection) --
def _norm(title: str) -> str:
    return " ".join(str(title or "").lower().split())


def catalog_diff(catalog, current_titles) -> dict:
    """Compare the categorized meeting catalog to the recurring-meeting titles the
    agent observed now. Returns:
      * seed — True when the catalog is empty (cold start): categorize all current
               meetings and surface project-syncs not in the focus mapping, but
               don't alert on every meeting as "new."
      * new  — current titles not in the catalog (research + categorize these).
      * gone — catalog entries (with category/project) that no longer occur.
    Pure logic; never mutates state."""
    entries = [e for e in (catalog or []) if isinstance(e, dict) and e.get("title")]
    cat_norm = {_norm(e["title"]) for e in entries}
    cur = [t for t in (current_titles or []) if t]
    cur_norm = {_norm(t) for t in cur}
    return {
        "seed": not entries,
        "new": [t for t in cur if _norm(t) not in cat_norm],
        "gone": [e for e in entries if _norm(e["title"]) not in cur_norm],
    }


def catalog_sync(entries) -> int:
    """Set project_focus.meeting_catalog to the given categorized entries
    ({"title","category","project"} plus an optional "source" — "signals" if the
    agent categorized it from the free calendar payload, "fetch" if it had to open
    a doc/Confluence/Slack; surfaces where the name/signal heuristic is weak),
    deduped by normalized title. Best-effort write preserving the rest of state.
    Returns the count, or -1 on failure."""
    state_path = VALOR_HOME / "state.json"
    try:
        state = json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        return -1
    pf = state.get("project_focus")
    if not isinstance(pf, dict):
        pf = {}
        state["project_focus"] = pf
    out, seen = [], set()
    for e in (entries or []):
        if not isinstance(e, dict):
            continue
        title = _norm(e.get("title"))
        if not title or title in seen:
            continue
        seen.add(title)
        entry = {"title": title,
                 "category": e.get("category") or "unknown",
                 "project": e.get("project")}
        if e.get("source") in ("signals", "fetch"):
            entry["source"] = e["source"]
        out.append(entry)
    out.sort(key=lambda x: x["title"])
    pf["meeting_catalog"] = out
    try:
        state_path.write_text(json.dumps(state, indent=2))
    except OSError:
        return -1
    return len(out)


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


def cmd_scan_due(args: argparse.Namespace) -> None:
    cfg = focus_config()
    print(json.dumps({
        "due": scan_due(cfg, today=args.today),
        "last_sync_scan": cfg.get("last_sync_scan", ""),
        "interval_days": cfg.get("sync_scan_interval_days", 14),
    }, indent=2))


def cmd_diff(args: argparse.Namespace) -> None:
    observed = _load_json_arg(args.observed) if args.observed else []
    print(json.dumps(diff_syncs(focus_config().get("syncs", []), observed), indent=2))


def cmd_mark_scanned(args: argparse.Namespace) -> None:
    print(json.dumps({"last_sync_scan": mark_scanned(today=args.today)}))


def cmd_catalog_diff(args: argparse.Namespace) -> None:
    current = _load_json_arg(args.current) if args.current else []
    print(json.dumps(catalog_diff(focus_config().get("meeting_catalog", []), current), indent=2))


def cmd_catalog_sync(args: argparse.Namespace) -> None:
    entries = _load_json_arg(args.entries) if args.entries else []
    print(json.dumps({"catalog_size": catalog_sync(entries)}))


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

    p_due = sub.add_parser("scan-due", help="Is the sync->project mapping due for a re-check?")
    p_due.add_argument("--today", default=None, help="YYYY-MM-DD override (testing)")

    p_diff = sub.add_parser("diff", help="Compare configured syncs to observed meeting titles")
    p_diff.add_argument("--observed", default="[]",
                        help='Observed sync-like titles JSON: ["title", ...] (or @file or -)')

    p_mark = sub.add_parser("mark-scanned", help="Stamp project_focus.last_sync_scan = today")
    p_mark.add_argument("--today", default=None, help="YYYY-MM-DD override (testing)")

    p_cdiff = sub.add_parser("catalog-diff", help="New/gone recurring meetings vs the catalog")
    p_cdiff.add_argument("--current", default="[]",
                         help='Current recurring-meeting titles JSON: ["title", ...] (or @file or -)')

    p_csync = sub.add_parser("catalog-sync", help="Set the meeting catalog to categorized entries")
    p_csync.add_argument("--entries", default="[]",
                         help='Entries JSON: [{"title","category","project"}, ...] (or @file or -)')

    args = ap.parse_args()
    {"resolve": cmd_resolve, "config": cmd_config, "scan-due": cmd_scan_due,
     "diff": cmd_diff, "mark-scanned": cmd_mark_scanned,
     "catalog-diff": cmd_catalog_diff, "catalog-sync": cmd_catalog_sync}[args.command](args)


if __name__ == "__main__":
    main()
