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
  * Workday bounds (workday_start/end) come from state.planning; the agent
    should override them with the user's calendar working-hours setting if the
    calendar tool exposes it.
  * Compute free gaps in the workday = [max(now, workday_start), workday_end]
    minus blocking events. Blocking = accepted real meetings and out-of-office.
    NOT blocking = focus time (a deep-work slot to fill) and working-location
    (see NON_BLOCKING_EVENT_TYPES); the agent also excludes declined / tentative
    / optional-attendee events before passing them here (free to schedule over).
  * Classify each gap: `deep` if >= deep_min_hours of contiguous time, else
    `fragmented`. A gap ending at a meeting is flagged `pre_meeting`.
    A no-meeting day is naturally one big deep gap.
  * Tag each priority by task shape: merge/review/publish/nudge -> fragmented_ok;
    code/design/research/draft -> deep_only; otherwise -> either.
  * A gap that immediately follows a real meeting (attendees > 1, or the agent
    set is_meeting) has its start pushed back by post_meeting_break_minutes -- a
    breather between back-to-backs. No break after lunch / a personal hold / OOO.
  * Assign greedily in priority order, respecting shape: deep_only only lands in
    deep gaps; fragmented_ok prefers fragmented gaps (preserving deep blocks for
    deep work); either prefers fragmented then falls back. Each task consumes its
    own estimated duration -- the priority's `est_minutes` when the agent
    provides one (it should estimate per task and lean generous), else a per-
    shape fallback; multiple tasks can pack into one gap.
  * No task starts before workday_start + morning_buffer_minutes (an AM-ritual
    buffer), deep_only tasks prefer gaps overlapping a focus-time block, and
    block starts/ends snap to block_granularity_minutes (clean clock boundaries).
  * Anything that doesn't fit is returned as `unassigned` (the agent surfaces it
    as "push to your next deep block").

CLI:
    plan.py fit --events <json|-> --priorities <json|-> [--now ISO]
                [--workday-start HH:MM] [--workday-end HH:MM] [--deep-hours N]
                [--break-minutes N] [--granularity N] [--morning-buffer N]
    plan.py shape --text "..."        # classify a single priority (debug)

All output is JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

VALOR_HOME = Path.home() / ".valor"

DEFAULTS = {
    "workday_start": "09:00",
    "workday_end": "18:00",
    "deep_min_hours": 2.0,
    # 15-min breather after a real meeting before the next block is scheduled.
    "post_meeting_break_minutes": 15,
    # Snap block start/end to this clock granularity (minutes) so blocks line up
    # with meetings (:00/:15/:30/:45). Durations round up to a multiple of it.
    "block_granularity_minutes": 15,
    # No tasks scheduled until this many minutes after workday_start — a morning
    # ritual buffer (Slack catch-up, planning). 0 = tasks from workday_start.
    "morning_buffer_minutes": 0,
    # Minutes reserved immediately before a prep-worthy meeting (project_sync /
    # external) to gather docs and organize talking points. 0 = no prep blocks.
    "pre_meeting_prep_minutes": 30,
    # Per-shape FALLBACK durations. The briefing should estimate each task's
    # duration from its nature (a publish is ~15 min; a pipeline change is hours)
    # and pass it as the priority's `est_minutes`; these are only used when it
    # doesn't. Estimate generously — the user would rather finish early.
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

# Calendar event types that do NOT block planning. Focus time is a deep-work
# slot you WANT to fill (so it becomes available, not busy); working-location is
# informational. Out-of-office and regular meetings (default) DO block. The
# caller tags each event with its type (Google Calendar `eventType`); untyped
# events default to blocking, preserving older behavior.
NON_BLOCKING_EVENT_TYPES = ("focusTime", "workingLocation")


def _read_state() -> dict:
    try:
        return json.loads((VALOR_HOME / "state.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def planning_config() -> dict:
    cfg = dict(DEFAULTS)
    state_cfg = _read_state().get("planning", {})
    if isinstance(state_cfg, dict):
        for k in ("workday_start", "workday_end", "deep_min_hours",
                  "post_meeting_break_minutes", "block_granularity_minutes",
                  "morning_buffer_minutes", "pre_meeting_prep_minutes"):
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
        # Calendar event times are local wall-clock; interpret a naive value as
        # LOCAL (attach the local zone), not UTC. Coercing naive->UTC shifts the
        # time by the local offset, which can push a meeting out of the day-plan
        # window so it vanishes from the plan.
        dt = dt.astimezone()
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


def _attendee_count(ev) -> int:
    """Best-effort attendee count for 'is this a real meeting?' detection."""
    a = ev.get("attendees")
    if isinstance(a, bool):
        return 0
    if isinstance(a, int):
        return a
    if isinstance(a, (list, tuple)):
        return len(a)
    return 0


def _is_real_meeting(ev) -> bool:
    """A real (collaborative) meeting earns a post-meeting break; a personal hold
    (lunch, a solo focus block kept as `default`) does not. Out-of-office blocks
    the day but isn't a meeting. The agent can pass `is_meeting` explicitly;
    otherwise we infer from attendee count > 1."""
    if ev.get("type") == "outOfOffice":
        return False
    if "is_meeting" in ev:
        return bool(ev["is_meeting"])
    return _attendee_count(ev) > 1


def _ceil_to(dt: datetime, gran: int) -> datetime:
    """Round dt UP to the next clean clock boundary that is a multiple of `gran`
    minutes past the hour (so blocks line up with meetings). No-op if gran<=0."""
    if gran <= 0:
        return dt
    rem = dt.minute % gran
    if rem == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt
    return (dt - timedelta(minutes=rem, seconds=dt.second, microseconds=dt.microsecond)
            + timedelta(minutes=gran))


def _round_up_minutes(n: int, gran: int) -> int:
    """Round a duration up to a whole multiple of gran (so block ends are clean)."""
    if gran <= 0:
        return n
    return ((n + gran - 1) // gran) * gran


# --- shape classification ------------------------------------------------
def classify_shape(text: str) -> str:
    low = text.lower()
    if any(kw in low for kw in DEEP_ONLY_KW):
        return "deep_only"
    if any(kw in low for kw in FRAGMENTED_KW):
        return "fragmented_ok"
    return "either"


# --- gaps ----------------------------------------------------------------
def compute_gaps(busy, window_start, window_end, deep_min_hours, break_minutes=0):
    """busy: list of (start, end, is_meeting) aware datetimes. Returns gap dicts.

    A gap that immediately follows a real meeting has its start pushed back by
    `break_minutes` (a post-meeting breather). The break is applied ONLY after
    real meetings — never after lunch / a personal hold / out-of-office, and
    never at the start of the workday.
    """
    # Normalize, clip to window, sort, merge overlaps (carrying is_meeting).
    clipped = []
    for item in busy:
        s, e = item[0], item[1]
        is_mtg = bool(item[2]) if len(item) > 2 else False
        s = max(s, window_start)
        e = min(e, window_end)
        if e > s:
            clipped.append((s, e, is_mtg))
    clipped.sort(key=lambda t: (t[0], t[1]))
    merged = []
    for s, e, is_mtg in clipped:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e), merged[-1][2] or is_mtg)
        else:
            merged.append((s, e, is_mtg))

    gaps = []
    cursor = window_start
    prev_was_meeting = False
    deep_min = deep_min_hours * 60
    for s, e, is_mtg in merged:
        if s > cursor:
            start = cursor
            if prev_was_meeting and break_minutes:
                start = min(start + timedelta(minutes=break_minutes), s)
            if s > start:
                gaps.append(_make_gap(start, s, deep_min, pre_meeting=True))
        cursor = max(cursor, e)
        prev_was_meeting = is_mtg
    if cursor < window_end:
        # Terminal gap (end of workday): not bounded by a later meeting.
        start = cursor
        if prev_was_meeting and break_minutes:
            start = min(start + timedelta(minutes=break_minutes), window_end)
        if window_end > start:
            gaps.append(_make_gap(start, window_end, deep_min, pre_meeting=False))
    return gaps


def _make_gap(start, end, deep_min, pre_meeting):
    mins = _minutes(start, end)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "minutes": mins,
        "type": "deep" if mins >= deep_min else "fragmented",
        "pre_meeting": pre_meeting,
        "has_focus": False,  # set in fit(): True if the gap overlaps focus-time
        "_start": start,  # internal, stripped before output
        "_cursor": start,
    }


def _find_prep_slot(gaps, meeting_start, minutes):
    """Latest free slot of `minutes` ending at or before a meeting, preferring the
    slot ending exactly at the meeting start (immediately before it). Returns a
    (start, end) datetime pair, or None if no gap before the meeting is big
    enough. Reserves the tail of the chosen gap — the part closest to the
    meeting — so prep stays as late (as fresh) as possible."""
    need = timedelta(minutes=minutes)
    cand = sorted([g for g in gaps if _parse_iso(g["end"]) <= meeting_start],
                  key=lambda g: _parse_iso(g["end"]), reverse=True)
    for g in cand:
        gs, ge = _parse_iso(g["start"]), _parse_iso(g["end"])
        if ge - gs >= need:
            return (ge - need, ge)
    return None


# --- assignment ----------------------------------------------------------
def _candidate_order(shape, gaps):
    """Return gaps in the order this shape should try them."""
    if shape == "deep_only":
        deep = [g for g in gaps if g["type"] == "deep"]
        # Prefer focus-time blocks for deep work — that's what they're reserved for.
        return [g for g in deep if g.get("has_focus")] + [g for g in deep if not g.get("has_focus")]
    if shape == "fragmented_ok":
        # prefer fragmented (save deep blocks), then deep
        return [g for g in gaps if g["type"] == "fragmented"] + \
               [g for g in gaps if g["type"] == "deep"]
    # either
    return [g for g in gaps if g["type"] == "fragmented"] + \
           [g for g in gaps if g["type"] == "deep"]


def assign(priorities, gaps, est_minutes, granularity=0):
    """priorities: list of {"text", "shape"}. Mutates gap cursors. Returns
    (blocks, unassigned). Block starts snap up to `granularity` and durations
    round up to it, so blocks land on clean clock boundaries like meetings."""
    blocks, unassigned = [], []
    for p in priorities:
        shape = p["shape"]
        # Per-task estimate (agent-provided) wins; shape default is the fallback.
        need = _round_up_minutes(int(p.get("est_minutes") or est_minutes.get(shape, 45)), granularity)
        placed = False
        for g in _candidate_order(shape, gaps):
            blk_start = _ceil_to(g["_cursor"], granularity)
            remaining = _minutes(blk_start, _parse_iso(g["end"]))
            if remaining >= need:
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
        deep_min_hours=None, break_minutes=None, granularity=None, morning_buffer=None,
        pre_meeting_prep=None):
    cfg = planning_config()
    workday_start = workday_start or cfg["workday_start"]
    workday_end = workday_end or cfg["workday_end"]
    deep_min_hours = deep_min_hours if deep_min_hours is not None else cfg["deep_min_hours"]
    break_minutes = break_minutes if break_minutes is not None else cfg["post_meeting_break_minutes"]
    granularity = granularity if granularity is not None else cfg["block_granularity_minutes"]
    morning_buffer = morning_buffer if morning_buffer is not None else cfg["morning_buffer_minutes"]
    pre_meeting_prep = pre_meeting_prep if pre_meeting_prep is not None else cfg["pre_meeting_prep_minutes"]
    est = cfg["est_minutes"]

    now_dt = _now(now)
    day_start = _at(now_dt, workday_start)
    day_end = _at(now_dt, workday_end)
    # No tasks before workday_start + morning_buffer (your AM ritual), and never
    # in the past: the usable window starts at max(now, workday_start + buffer).
    task_floor = day_start + timedelta(minutes=morning_buffer)
    window_start = max(now_dt, task_floor)
    if window_start >= day_end:
        window_start = day_end  # workday over -> no gaps

    busy = []
    focus_windows = []
    prep_meetings = []  # (start, summary) for meetings the agent flagged prep-worthy
    for ev in events:
        if ev.get("type") in NON_BLOCKING_EVENT_TYPES:
            if ev.get("type") == "focusTime":  # a deep-work slot to prefer, not busy
                try:
                    focus_windows.append((_parse_iso(ev["start"]), _parse_iso(ev["end"])))
                except (KeyError, ValueError):
                    pass
            continue  # focus time / working-location: leave free for deep work
        try:
            s, e = _parse_iso(ev["start"]), _parse_iso(ev["end"])
        except (KeyError, ValueError):
            continue
        busy.append((s, e, _is_real_meeting(ev)))
        if ev.get("prep"):
            prep_meetings.append((s, ev.get("summary") or "meeting"))

    # Reserve a prep block immediately before each prep-worthy meeting (or, if
    # that slot isn't free, the nearest earlier gap that day). Prep blocks are
    # non-meeting busy — no post-meeting break after them — so gaps recomputed
    # around them keep that time off-limits to other tasks.
    prep_blocks, prep_unassigned, prep_busy = [], [], []
    if pre_meeting_prep > 0:
        for mstart, summary in sorted(prep_meetings, key=lambda t: t[0]):
            if mstart <= now_dt:
                continue  # meeting already underway / in the past — no prep
            cur_gaps = compute_gaps(busy + prep_busy, window_start, day_end,
                                    deep_min_hours, break_minutes=break_minutes)
            slot = _find_prep_slot(cur_gaps, mstart, pre_meeting_prep)
            if slot:
                bs, be = slot
                prep_blocks.append({
                    "start": bs.isoformat(), "end": be.isoformat(),
                    "minutes": pre_meeting_prep, "for_meeting": summary,
                    "adjacent": be == mstart,
                })
                prep_busy.append((bs, be, False))
            else:
                prep_unassigned.append({
                    "for_meeting": summary,
                    "reason": "no free slot before the meeting today",
                })
        prep_blocks.sort(key=lambda b: b["start"])

    gaps = compute_gaps(busy + prep_busy, window_start, day_end, deep_min_hours,
                        break_minutes=break_minutes)
    # Flag gaps that overlap a focus-time block; deep work prefers these (#2).
    for g in gaps:
        g["has_focus"] = any(fs < _parse_iso(g["end"]) and fe > g["_start"] for fs, fe in focus_windows)

    norm_priorities = []
    for p in priorities:
        if isinstance(p, str):
            norm_priorities.append({"text": p, "shape": classify_shape(p), "est_minutes": None})
        else:
            text = p.get("text", "")
            est_p = p.get("est_minutes")
            norm_priorities.append({
                "text": text,
                "shape": p.get("shape") or classify_shape(text),
                "est_minutes": est_p if isinstance(est_p, (int, float)) and est_p > 0 else None,
            })

    blocks, unassigned = assign(norm_priorities, gaps, est, granularity)

    public_gaps = [{k: v for k, v in g.items() if not k.startswith("_")} for g in gaps]
    return {
        "date": now_dt.date().isoformat(),
        "workday": {"start": day_start.isoformat(), "end": day_end.isoformat()},
        "now": now_dt.isoformat(),
        "no_meeting_day": len(busy) == 0,
        "gaps": public_gaps,
        "deep_gap_count": sum(1 for g in public_gaps if g["type"] == "deep"),
        "prep_blocks": prep_blocks,
        "prep_unassigned": prep_unassigned,
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


def _empty_calendar_warning(events, priorities):
    """Warn when asked to schedule tasks against *no* calendar at all.

    The failure this guards: a caller reads "the day's open / nothing on the
    calendar" as an empty day and passes zero events, so tasks get packed from
    `now` forward — landing on top of real but un-supplied commitments while the
    genuinely free gaps go unused. We can't see the true calendar from here, but
    "priorities to place + zero events" is almost always a dropped-calendar
    mistake, not a truly empty day (accepted meetings and holds are busy). High
    precision, near-zero false-positive cost — it's only a stderr note, the fit
    still runs."""
    if priorities and not events:
        n = len(priorities)
        return (
            "plan.py: scheduling against an EMPTY calendar — 0 events, "
            f"{n} priorit{'y' if n == 1 else 'ies'}. If the day isn't truly "
            "empty, pass the real events (accepted meetings + holds are busy); "
            "'open day' means no syncs, not no calendar."
        )
    return None


def cmd_fit(args: argparse.Namespace) -> None:
    events = _load_json_arg(args.events) if args.events else []
    priorities = _load_json_arg(args.priorities) if args.priorities else []
    warning = _empty_calendar_warning(events, priorities)
    if warning:
        print(f"⚠️  {warning}", file=sys.stderr)
    result = fit(
        events, priorities, now=args.now,
        workday_start=args.workday_start, workday_end=args.workday_end,
        deep_min_hours=args.deep_hours, break_minutes=args.break_minutes,
        granularity=args.granularity, morning_buffer=args.morning_buffer,
        pre_meeting_prep=args.pre_meeting_prep,
    )
    print(json.dumps(result, indent=2))


def cmd_shape(args: argparse.Namespace) -> None:
    print(json.dumps({"text": args.text, "shape": classify_shape(args.text)}))


def main() -> None:
    ap = argparse.ArgumentParser(description="Valor day-planning (gap-fit) pass")
    sub = ap.add_subparsers(dest="command", required=True)

    p_fit = sub.add_parser("fit", help="Fit priorities to today's calendar gaps")
    p_fit.add_argument("--events", default="[]",
                       help='Busy blocks JSON: [{"start","end","type","is_meeting"|"attendees"}] (or @file or -)')
    p_fit.add_argument("--priorities", default="[]",
                       help='Priorities JSON: ["text", ...] or [{"text","shape","est_minutes"}] (or @file or -)')
    p_fit.add_argument("--now", default=None, help="ISO timestamp override (testing)")
    p_fit.add_argument("--workday-start", default=None, help="HH:MM (default from state/09:00)")
    p_fit.add_argument("--workday-end", default=None, help="HH:MM (default from state/18:00)")
    p_fit.add_argument("--deep-hours", type=float, default=None,
                       help="Min contiguous hours for a deep block (default 2)")
    p_fit.add_argument("--break-minutes", type=int, default=None,
                       help="Minutes reserved after a real meeting (default from state/15)")
    p_fit.add_argument("--granularity", type=int, default=None,
                       help="Snap block start/end to this clock granularity (default from state/15)")
    p_fit.add_argument("--morning-buffer", type=int, default=None,
                       help="Minutes after workday_start before tasks may start (default from state/0)")
    p_fit.add_argument("--pre-meeting-prep", type=int, default=None,
                       help="Minutes reserved before a prep-worthy meeting (default from state/30)")

    p_shape = sub.add_parser("shape", help="Classify a single priority's task shape")
    p_shape.add_argument("--text", required=True)

    args = ap.parse_args()
    {"fit": cmd_fit, "shape": cmd_shape}[args.command](args)


if __name__ == "__main__":
    main()
