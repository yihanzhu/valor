#!/usr/bin/env python3
"""Valor day-planning pass.

The briefing emits a ranked list of priorities, but a list is not a plan: a
1.5h pre-meeting gap and a no-meeting afternoon get treated identically, so the
user re-slots everything by hand each morning. This module fits the priorities
to the day's actual calendar gaps.

It is pure logic + a CLI, like verify.py: the AGENT fetches the calendar
(read) and, if enabled, writes the resulting blocks back as events (the
"Day Planning & Calendar Write" protocol in utilities.md). This module never
touches the network.

Model:
  * Compute free gaps in the workday = [max(now, workday_start), workday_end]
    minus busy (accepted/tentative) meetings.
  * Classify each gap: `deep` if >= deep_min_hours of contiguous time, else
    `fragmented`. A gap ending at a meeting is flagged `pre_meeting`.
    A no-meeting day is naturally one big deep gap.
  * Tag each priority by task shape: merge/review/publish/nudge -> fragmented_ok;
    code/design/research/draft -> deep_only; otherwise -> either.
  * Assign greedily in priority order, respecting shape: deep_only only lands in
    deep gaps; fragmented_ok prefers fragmented gaps (preserving deep blocks for
    deep work); either prefers fragmented then falls back. Each task consumes an
    estimated duration; multiple tasks can pack into one gap.
  * Anything that doesn't fit is returned as `unassigned` (the agent surfaces it
    as "push to your next deep block").

CLI:
    plan.py fit --events <json|-> --priorities <json|-> [--now ISO]
                [--workday-start HH:MM] [--workday-end HH:MM] [--deep-hours N]
    plan.py shape --text "..."        # classify a single priority (debug)

All output is JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

VALOR_HOME = Path.home() / ".valor"

DEFAULTS = {
    "workday_start": "09:00",
    "workday_end": "18:00",
    "deep_min_hours": 2.0,
    "est_minutes": {"fragmented_ok": 30, "deep_only": 90, "either": 45},
}

# Task-shape keyword rules. Order matters: deep_only wins ties (a "design review"
# is deep work, not a quick review).
DEEP_ONLY_KW = (
    "design", "research", "investigat", "implement", "refactor", "debug",
    "prototype", "spec", "architect", "rca", "root cause", "analy", "write-up",
    "writeup", "1-pager", "one-pager", "draft", "build ", "develop", "explore",
    "deep dive", "deep-dive",
)
FRAGMENTED_KW = (
    "merge", "review", "nudge", "publish", "post ", "reply", "respond", "send",
    "ping", "approve", "comment", "follow up", "follow-up", "rebase",
    "cherry-pick", "bump", "tag ", "release", "close ", "triage", "stand-up",
    "standup", "sync", "check ", "update status", "respond to",
)


def _read_state() -> dict:
    try:
        return json.loads((VALOR_HOME / "state.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def planning_config() -> dict:
    cfg = dict(DEFAULTS)
    state_cfg = _read_state().get("planning", {})
    if isinstance(state_cfg, dict):
        for k in ("workday_start", "workday_end", "deep_min_hours"):
            if k in state_cfg:
                cfg[k] = state_cfg[k]
        if isinstance(state_cfg.get("est_minutes"), dict):
            cfg["est_minutes"] = {**DEFAULTS["est_minutes"], **state_cfg["est_minutes"]}
    return cfg


def calendar_auto_write_enabled() -> bool:
    cfg = _read_state().get("planning", {})
    return bool(cfg.get("calendar_auto_write", True)) if isinstance(cfg, dict) else True


# --- time helpers --------------------------------------------------------
def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _now(now: str | datetime | None) -> datetime:
    if isinstance(now, datetime):
        return now
    if now:
        return _parse_iso(now)
    return datetime.now().astimezone()


def _at(day: datetime, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def _minutes(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)


# --- shape classification ------------------------------------------------
def classify_shape(text: str) -> str:
    low = text.lower()
    if any(kw in low for kw in DEEP_ONLY_KW):
        return "deep_only"
    if any(kw in low for kw in FRAGMENTED_KW):
        return "fragmented_ok"
    return "either"


# --- gaps ----------------------------------------------------------------
def compute_gaps(busy, window_start, window_end, deep_min_hours):
    """busy: list of (start, end) aware datetimes. Returns gap dicts."""
    # Normalize, clip to window, sort, merge overlaps.
    clipped = []
    for s, e in busy:
        s = max(s, window_start)
        e = min(e, window_end)
        if e > s:
            clipped.append((s, e))
    clipped.sort()
    merged = []
    for s, e in clipped:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    gaps = []
    cursor = window_start
    deep_min = deep_min_hours * 60
    for s, e in merged:
        if s > cursor:
            gaps.append(_make_gap(cursor, s, deep_min, pre_meeting=True))
        cursor = max(cursor, e)
    if cursor < window_end:
        # Terminal gap (end of workday): not bounded by a later meeting.
        gaps.append(_make_gap(cursor, window_end, deep_min, pre_meeting=False))
    return gaps


def _make_gap(start, end, deep_min, pre_meeting):
    mins = _minutes(start, end)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "minutes": mins,
        "type": "deep" if mins >= deep_min else "fragmented",
        "pre_meeting": pre_meeting,
        "_start": start,  # internal, stripped before output
        "_cursor": start,
    }


# --- assignment ----------------------------------------------------------
def _candidate_order(shape, gaps):
    """Return gaps in the order this shape should try them."""
    if shape == "deep_only":
        return [g for g in gaps if g["type"] == "deep"]
    if shape == "fragmented_ok":
        # prefer fragmented (save deep blocks), then deep
        return [g for g in gaps if g["type"] == "fragmented"] + \
               [g for g in gaps if g["type"] == "deep"]
    # either
    return [g for g in gaps if g["type"] == "fragmented"] + \
           [g for g in gaps if g["type"] == "deep"]


def assign(priorities, gaps, est_minutes):
    """priorities: list of {"text", "shape"}. Mutates gap cursors. Returns
    (blocks, unassigned)."""
    blocks, unassigned = [], []
    for p in priorities:
        shape = p["shape"]
        need = est_minutes.get(shape, 45)
        placed = False
        for g in _candidate_order(shape, gaps):
            remaining = _minutes(g["_cursor"], _parse_iso(g["end"]))
            if remaining >= need:
                blk_start = g["_cursor"]
                blk_end = blk_start + timedelta(minutes=need)
                blocks.append({
                    "start": blk_start.isoformat(),
                    "end": blk_end.isoformat(),
                    "minutes": need,
                    "priority": p["text"],
                    "shape": shape,
                    "gap_type": g["type"],
                })
                g["_cursor"] = blk_end
                placed = True
                break
        if not placed:
            unassigned.append({
                "priority": p["text"],
                "shape": shape,
                "reason": "no deep block today" if shape == "deep_only" else "day is full",
            })
    return blocks, unassigned


# --- top-level fit -------------------------------------------------------
def fit(events, priorities, *, now=None, workday_start=None, workday_end=None,
        deep_min_hours=None):
    cfg = planning_config()
    workday_start = workday_start or cfg["workday_start"]
    workday_end = workday_end or cfg["workday_end"]
    deep_min_hours = deep_min_hours if deep_min_hours is not None else cfg["deep_min_hours"]
    est = cfg["est_minutes"]

    now_dt = _now(now)
    day_start = _at(now_dt, workday_start)
    day_end = _at(now_dt, workday_end)
    # Don't plan in the past: the usable window starts at max(now, workday_start).
    window_start = max(now_dt, day_start)
    if window_start >= day_end:
        window_start = day_end  # workday over -> no gaps

    busy = []
    for ev in events:
        try:
            busy.append((_parse_iso(ev["start"]), _parse_iso(ev["end"])))
        except (KeyError, ValueError):
            continue

    gaps = compute_gaps(busy, window_start, day_end, deep_min_hours)

    norm_priorities = []
    for p in priorities:
        if isinstance(p, str):
            norm_priorities.append({"text": p, "shape": classify_shape(p)})
        else:
            text = p.get("text", "")
            norm_priorities.append({"text": text, "shape": p.get("shape") or classify_shape(text)})

    blocks, unassigned = assign(norm_priorities, gaps, est)

    public_gaps = [{k: v for k, v in g.items() if not k.startswith("_")} for g in gaps]
    return {
        "date": now_dt.date().isoformat(),
        "workday": {"start": day_start.isoformat(), "end": day_end.isoformat()},
        "now": now_dt.isoformat(),
        "no_meeting_day": len(busy) == 0,
        "gaps": public_gaps,
        "deep_gap_count": sum(1 for g in public_gaps if g["type"] == "deep"),
        "blocks": blocks,
        "unassigned": unassigned,
    }


# --- CLI -----------------------------------------------------------------
def _load_json_arg(value: str):
    if value == "-":
        return json.loads(sys.stdin.read() or "[]")
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text())
    return json.loads(value)


def cmd_fit(args: argparse.Namespace) -> None:
    events = _load_json_arg(args.events) if args.events else []
    priorities = _load_json_arg(args.priorities) if args.priorities else []
    result = fit(
        events, priorities, now=args.now,
        workday_start=args.workday_start, workday_end=args.workday_end,
        deep_min_hours=args.deep_hours,
    )
    print(json.dumps(result, indent=2))


def cmd_shape(args: argparse.Namespace) -> None:
    print(json.dumps({"text": args.text, "shape": classify_shape(args.text)}))


def main() -> None:
    ap = argparse.ArgumentParser(description="Valor day-planning (gap-fit) pass")
    sub = ap.add_subparsers(dest="command", required=True)

    p_fit = sub.add_parser("fit", help="Fit priorities to today's calendar gaps")
    p_fit.add_argument("--events", default="[]",
                       help='Busy blocks JSON: [{"start","end","summary"}] (or @file or -)')
    p_fit.add_argument("--priorities", default="[]",
                       help='Priorities JSON: ["text", ...] or [{"text","shape"}] (or @file or -)')
    p_fit.add_argument("--now", default=None, help="ISO timestamp override (testing)")
    p_fit.add_argument("--workday-start", default=None, help="HH:MM (default from state/09:00)")
    p_fit.add_argument("--workday-end", default=None, help="HH:MM (default from state/18:00)")
    p_fit.add_argument("--deep-hours", type=float, default=None,
                       help="Min contiguous hours for a deep block (default 2)")

    p_shape = sub.add_parser("shape", help="Classify a single priority's task shape")
    p_shape.add_argument("--text", required=True)

    args = ap.parse_args()
    {"fit": cmd_fit, "shape": cmd_shape}[args.command](args)


if __name__ == "__main__":
    main()
