#!/usr/bin/env python3
"""Valor artifact-verification gate.

Phantom propagation is the failure mode this module exists to stop: wrap-up
writes a carry-forward claim ("PROJ-42 1-pager unposted"), the next briefing
reads it as fact, re-asserts it, bumps a day counter, and the cycle repeats --
nobody ever checks whether the artifact actually exists. A claim can survive
weeks of daily increments without a single live lookup.

This module is the ledger + policy engine that breaks the cycle. It does NOT
itself reach Slack/Confluence/Drive/Jira -- those live behind MCP tools that
only the agent can call during a session. Instead:

  * It owns the verification cache, the per-type TTL policy, the stable
    claim identity (claim_hash), and the demote/freeze/escalate state machine.
  * For GitHub PRs it CAN check directly by shelling out to `gh` (already a
    Valor dependency), so that path is fully automated.
  * For MCP-backed claim types it returns a structured "needs_lookup"
    directive telling the agent exactly what query to run; the agent performs
    the lookup and reports back via `record`.

Verdict semantics -- a carried claim always asserts "task X is not yet done".
Verification answers "has the artifact been produced / task completed?":

  * resolved   -> artifact exists / PR merged / page posted / message sent.
                  The incompleteness claim is FALSE -> clear it, log completion.
  * unresolved -> confirmed still missing/open. Claim holds -> increment the
                  chronic day counter (this is a *real* signal, keep it).
  * unverified -> could not check (no tool, error, declined). Demote the claim
                  to "unverified -- confirm or drop?" and FREEZE the counter so
                  a guess never masquerades as a fact.

CLI:
    verify.py check   --type T --id ID [--expect-state S] [--no-auto] [--now ISO]
    verify.py record  --type T --id ID --result resolved|unresolved|unverified [--now ISO]
    verify.py get     --type T --id ID
    verify.py list    [--frozen] [--status resolved|unresolved|unverified] [--type T]
    verify.py types   (print supported claim types + TTLs)

All commands print JSON to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

VALOR_HOME = Path.home() / ".valor"
DB_PATH = VALOR_HOME / "evidence.sqlite"

# --- Claim types and per-type TTLs (hours) -------------------------------
# TTL = how long a definitive verdict stays trustworthy before re-checking.
# Rationale (locked decision): PR/Jira state churns fast and is cheap to poll;
# Confluence/Drive *absence* needs a short-ish window to catch "posted today";
# a Slack message, once sent, is effectively immutable so it can cache for a week.
TTL_HOURS = {
    "github_pr": 4,
    "jira": 4,
    "confluence": 24,
    "drive": 24,
    "slack": 24 * 7,
}
DEFAULT_TTL_HOURS = 24

CLAIM_TYPES = tuple(TTL_HOURS.keys())

# Claim types verify.py can resolve on its own (no agent/MCP round-trip).
AUTO_TYPES = ("github_pr",)

VERDICTS = ("resolved", "unresolved", "unverified")

# DDL is mirrored in evidence_cli.MIGRATIONS[3]; both use CREATE TABLE IF NOT
# EXISTS so whichever runs first wins and the other is a no-op. Keep in sync.
CLAIM_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS claim_verifications (
    claim_hash        TEXT PRIMARY KEY,
    claim_type        TEXT NOT NULL,
    identifier        TEXT NOT NULL,
    verified          INTEGER,
    last_verdict      TEXT,
    last_checked      TEXT,
    last_counted_date TEXT,
    miss_count        INTEGER NOT NULL DEFAULT 0,
    day_count         INTEGER NOT NULL DEFAULT 0,
    frozen            INTEGER NOT NULL DEFAULT 0,
    resolved_at       TEXT,
    first_seen        TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    metadata          TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_claim_verif_type ON claim_verifications(claim_type);
CREATE INDEX IF NOT EXISTS idx_claim_verif_frozen ON claim_verifications(frozen);
CREATE INDEX IF NOT EXISTS idx_claim_verif_verdict ON claim_verifications(last_verdict);
"""


# --- Time helpers --------------------------------------------------------
def _now(now: datetime | None = None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# --- State / config ------------------------------------------------------
def _read_state() -> dict:
    """Read state.json defensively. Missing/invalid -> empty dict."""
    state_path = VALOR_HOME / "state.json"
    try:
        return json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def verification_enabled() -> bool:
    """Kill switch. Absent config defaults to enabled (gate is opt-out)."""
    cfg = _read_state().get("verification", {})
    if not isinstance(cfg, dict):
        return True
    return bool(cfg.get("enabled", True))


def escalation_threshold() -> int:
    cfg = _read_state().get("verification", {})
    if isinstance(cfg, dict):
        try:
            return int(cfg.get("escalation_threshold", 3))
        except (TypeError, ValueError):
            pass
    return 3


def ttl_hours_for(claim_type: str) -> int:
    """Per-type TTL, overridable via state.verification.ttl_overrides."""
    cfg = _read_state().get("verification", {})
    overrides = cfg.get("ttl_overrides", {}) if isinstance(cfg, dict) else {}
    if isinstance(overrides, dict) and claim_type in overrides:
        try:
            return int(overrides[claim_type])
        except (TypeError, ValueError):
            pass
    return TTL_HOURS.get(claim_type, DEFAULT_TTL_HOURS)


# --- Identity ------------------------------------------------------------
def normalize_identifier(claim_type: str, identifier: str) -> str:
    """Stable, case-insensitive identity so the same claim accumulates across
    runs instead of forking a new counter every time the wording drifts."""
    norm = re.sub(r"\s+", " ", identifier.strip()).lower()
    return f"{claim_type}|{norm}"


def claim_hash(claim_type: str, identifier: str) -> str:
    key = normalize_identifier(claim_type, identifier)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


# --- DB ------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript(CLAIM_TABLE_DDL)
    conn.commit()


def _fetch_row(conn: sqlite3.Connection, chash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM claim_verifications WHERE claim_hash = ?", (chash,)
    ).fetchone()


# --- Display -------------------------------------------------------------
def _ago(last_checked: str | None, now: datetime) -> str:
    dt = _parse_iso(last_checked)
    if dt is None:
        return "never"
    hours = (now - dt).total_seconds() / 3600
    if hours < 1:
        return "just now"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours // 24)}d ago"


def make_display(row: dict | None, now: datetime) -> str:
    if row is None:
        return "new — not yet verified"
    verdict = row.get("last_verdict")
    day_count = row.get("day_count", 0) or 0
    if verdict == "resolved":
        return f"✓ done (verified resolved {_ago(row.get('last_checked'), now)})"
    if verdict == "unresolved":
        return f"unresolved — {day_count}d"
    if verdict == "unverified":
        last = _ago(row.get("last_checked"), now)
        return (
            "unverified — confirm or drop? "
            f"(frozen at {day_count}d, last definitive check {last})"
        )
    return "new — not yet verified"


# --- GitHub auto-check ---------------------------------------------------
def gh_available() -> bool:
    return shutil.which("gh") is not None


def _parse_pr_identifier(identifier: str, default_owner: str = "") -> tuple[str, str]:
    """Return (repo_spec, number). repo_spec may be 'owner/repo', 'repo', or ''.

    Accepts: 'owner/repo#123', 'repo#123', '#123', '123',
    or a full URL '.../owner/repo/pull/123'.
    """
    identifier = identifier.strip()
    url = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", identifier)
    if url:
        return url.group(1), url.group(2)
    if "#" in identifier:
        repo_spec, _, num = identifier.partition("#")
        repo_spec = repo_spec.strip()
    else:
        repo_spec, num = "", identifier
    # A PR number is a bare integer. Reject anything else (e.g. a Jira key like
    # 'PROJ-42' mis-routed here, or 'repo#12a') by returning no number, rather
    # than stripping non-digits and fabricating a bogus PR number to look up.
    num = num.strip()
    num = num if num.isdigit() else ""
    if repo_spec and "/" not in repo_spec and default_owner:
        repo_spec = f"{default_owner}/{repo_spec}"
    return repo_spec, num


def _run_gh(args: list[str]) -> dict | None:
    """Run a `gh` command and return parsed JSON, or None on any failure.

    Isolated so tests can monkeypatch it without a live `gh`.
    """
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def check_github_pr(identifier: str, expect_state: str | None = None) -> dict:
    """Resolve a GitHub PR claim via `gh`.

    Returns {"verdict": ..., "detail": {...}}.
    Default: resolved when the PR is no longer OPEN (merged or closed) -- a
    carried "merge #X" / "nudge review on #X" task is done once it's not open.
    Pass expect_state ('merged'|'closed'|'open') to require a specific state.
    """
    owner = _read_state().get("github_owner", "")
    repo_spec, num = _parse_pr_identifier(identifier, owner)
    if not num:
        return {"verdict": "unverified", "detail": {"reason": "no PR number in identifier"}}
    if not gh_available():
        return {"verdict": "unverified", "detail": {"reason": "gh not installed"}}

    args = ["pr", "view", num, "--json", "state,title,url,mergedAt,closedAt,isDraft"]
    if repo_spec:
        args += ["--repo", repo_spec]
    data = _run_gh(args)
    if data is None:
        return {"verdict": "unverified", "detail": {"reason": "gh lookup failed", "pr": num}}

    state = (data.get("state") or "").upper()  # OPEN | MERGED | CLOSED
    if expect_state:
        resolved = state == expect_state.upper()
    else:
        resolved = state in ("MERGED", "CLOSED")
    return {
        "verdict": "resolved" if resolved else "unresolved",
        "detail": {"state": state, "title": data.get("title"), "url": data.get("url")},
    }


# --- Lookup directives (MCP-backed types) --------------------------------
def lookup_directive(claim_type: str, identifier: str) -> dict:
    """What the agent should run to verify an MCP-backed claim type."""
    ident = identifier.strip()
    if claim_type == "confluence":
        safe = ident.replace('"', " ")
        return {
            "method": "cql",
            "query": f'(text ~ "{safe}" OR title ~ "{safe}") AND type = page',
            "tool_hint": "Atlassian MCP searchConfluenceUsingCql, or a Confluence-capable skill",
            "resolved_if": "a matching published page exists",
        }
    if claim_type == "jira":
        return {
            "method": "jql",
            "query": f'key = "{ident}"' if re.match(r"^[A-Z][A-Z0-9]+-\d+$", ident) else f'text ~ "{ident}"',
            "tool_hint": "Atlassian MCP searchJiraIssuesUsingJql / getJiraIssue",
            "resolved_if": "the issue is in a Done/Closed/Resolved status",
        }
    if claim_type == "slack":
        return {
            "method": "search",
            "query": ident,
            "tool_hint": "Slack MCP search_messages (scope by sender/recipient/topic)",
            "resolved_if": "a real (non-draft) message matching this was actually sent",
        }
    if claim_type == "drive":
        return {
            "method": "search",
            "query": ident,
            "tool_hint": "Google Drive search by name/full-text",
            "resolved_if": "a matching doc exists",
        }
    if claim_type == "github_pr":
        return {
            "method": "gh",
            "query": f"gh pr view {identifier} --json state,mergedAt,closedAt",
            "tool_hint": "gh CLI (verify.py checks this automatically when gh is present)",
            "resolved_if": "the PR is merged or closed",
        }
    return {"method": "manual", "query": ident, "tool_hint": "no automated path", "resolved_if": "n/a"}


# --- Core: record a verdict ---------------------------------------------
def record_result(
    claim_type: str,
    identifier: str,
    result: str,
    *,
    now: datetime | None = None,
    increment: int = 1,
) -> dict:
    """Persist a verdict and advance the state machine. Returns the new state.

    State machine (cumulative counters -- locked decision #3):
      resolved   -> verified=1, clear counters, stamp resolved_at, unfreeze.
      unresolved -> verified=0, +1 day_count & miss_count (once per calendar
                    day), unfreeze. The chronic "Nd" is a real signal; keep it.
      unverified -> verified=NULL, counters UNCHANGED (frozen), set frozen=1.
    """
    if claim_type not in CLAIM_TYPES:
        raise ValueError(f"unknown claim_type '{claim_type}' (valid: {', '.join(CLAIM_TYPES)})")
    if result not in VERDICTS:
        raise ValueError(f"unknown result '{result}' (valid: {', '.join(VERDICTS)})")

    now_dt = _now(now)
    now_iso = now_dt.isoformat()
    # Per-day dedup is a *calendar-day* boundary the user reasons about locally
    # ("did briefing + wrapup both run today?"). Use the local day, not UTC --
    # otherwise a re-check near local midnight lands on a different UTC date and
    # double-counts (or two distinct local days collapse into one).
    today = now_dt.astimezone().date().isoformat()
    chash = claim_hash(claim_type, identifier)

    conn = get_conn()
    ensure_table(conn)
    row = _fetch_row(conn, chash)
    existing = dict(row) if row is not None else None

    if existing is None:
        miss_count = 0
        day_count = 0
        resolved_at = None
        first_seen = now_iso
        created_at = now_iso
        last_counted_date = None
    else:
        miss_count = existing["miss_count"] or 0
        day_count = existing["day_count"] or 0
        resolved_at = existing["resolved_at"]
        first_seen = existing["first_seen"] or now_iso
        created_at = existing["created_at"] or now_iso
        last_counted_date = existing["last_counted_date"]

    if result == "resolved":
        verified = 1
        frozen = 0
        day_count = 0
        miss_count = 0
        if resolved_at is None:
            resolved_at = now_iso
        last_checked = now_iso
    elif result == "unresolved":
        verified = 0
        frozen = 0
        # Increment at most once per calendar day so briefing+wrapup on the
        # same day don't double-count.
        if last_counted_date != today:
            day_count += increment
            miss_count += 1
            last_counted_date = today
        last_checked = now_iso
    else:  # unverified -> freeze
        verified = None
        frozen = 1
        # Counters untouched. last_checked NOT advanced -- the staleness clock
        # keeps running so the next run still knows a real check is overdue.
        last_checked = existing["last_checked"] if existing else None

    conn.execute(
        """
        INSERT INTO claim_verifications
            (claim_hash, claim_type, identifier, verified, last_verdict,
             last_checked, last_counted_date, miss_count, day_count, frozen,
             resolved_at, first_seen, created_at, updated_at, metadata)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(claim_hash) DO UPDATE SET
            identifier=excluded.identifier,
            verified=excluded.verified,
            last_verdict=excluded.last_verdict,
            last_checked=excluded.last_checked,
            last_counted_date=excluded.last_counted_date,
            miss_count=excluded.miss_count,
            day_count=excluded.day_count,
            frozen=excluded.frozen,
            resolved_at=excluded.resolved_at,
            updated_at=excluded.updated_at
        """,
        (
            chash, claim_type, identifier, verified, result,
            last_checked, last_counted_date, miss_count, day_count, frozen,
            resolved_at, first_seen, created_at, now_iso, "{}",
        ),
    )
    conn.commit()
    new_row = dict(_fetch_row(conn, chash))
    conn.close()

    new_row["display"] = make_display(new_row, now_dt)
    new_row["escalate_eligible"] = bool(
        new_row["last_verdict"] == "unresolved"
        and (new_row["miss_count"] or 0) >= escalation_threshold()
    )
    return new_row


# --- Core: check (cache-first, auto-resolve GitHub) ----------------------
def check_artifact(
    claim_type: str,
    identifier: str,
    *,
    now: datetime | None = None,
    auto: bool = True,
    expect_state: str | None = None,
) -> dict:
    """Decide whether a claim can be trusted, needs a live lookup, or is off.

    Returns a dict with an `action` the caller should follow:
      "skip"          -> verification disabled; behave as before (no gate).
      "trust"         -> a fresh verdict exists in cache; use `verdict`/`display`.
      "perform_lookup"-> stale/never-checked MCP-backed claim; run `lookup`,
                         then call record_result with the outcome.
      "checked"       -> verify.py resolved it inline (GitHub) and recorded it.
    """
    if claim_type not in CLAIM_TYPES:
        raise ValueError(f"unknown claim_type '{claim_type}' (valid: {', '.join(CLAIM_TYPES)})")

    now_dt = _now(now)
    chash = claim_hash(claim_type, identifier)
    ttl = ttl_hours_for(claim_type)

    base = {
        "claim_hash": chash,
        "claim_type": claim_type,
        "identifier": identifier,
        "ttl_hours": ttl,
    }

    if not verification_enabled():
        return {**base, "status": "disabled", "action": "skip", "verdict": None,
                "display": "verification disabled"}

    conn = get_conn()
    ensure_table(conn)
    row = _fetch_row(conn, chash)
    existing = dict(row) if row is not None else None
    conn.close()

    # Is the cached verdict still fresh?
    fresh = False
    if existing and existing.get("last_verdict") in ("resolved", "unresolved"):
        last_dt = _parse_iso(existing.get("last_checked"))
        if last_dt is not None and (now_dt - last_dt) < timedelta(hours=ttl):
            fresh = True

    if fresh:
        return {
            **base,
            "status": "cached",
            "action": "trust",
            "verdict": existing["last_verdict"],
            "display": make_display(existing, now_dt),
            "day_count": existing["day_count"],
            "miss_count": existing["miss_count"],
            "frozen": bool(existing["frozen"]),
            "fresh": True,
        }

    # Stale / never-checked / last was unverified. Try to auto-resolve GitHub.
    if claim_type in AUTO_TYPES and auto:
        gh_result = check_github_pr(identifier, expect_state=expect_state)
        verdict = gh_result["verdict"]
        recorded = record_result(claim_type, identifier, verdict, now=now)
        # Only a definitive verdict (resolved/unresolved) counts as "checked".
        # An unverified verdict means the lookup couldn't confirm anything (gh
        # missing, lookup error, no PR number); demote to a needs_lookup so the
        # agent confirms instead of trusting a non-check as fact.
        if verdict == "unverified":
            return {
                **base,
                "status": "needs_lookup",
                "action": "perform_lookup",
                "verdict": "unverified",
                "display": recorded["display"],
                "day_count": recorded["day_count"],
                "miss_count": recorded["miss_count"],
                "frozen": bool(recorded["frozen"]),
                "fresh": False,
                "detail": gh_result.get("detail", {}),
                "lookup": lookup_directive(claim_type, identifier),
            }
        return {
            **base,
            "status": "checked",
            "action": "checked",
            "verdict": verdict,
            "display": recorded["display"],
            "day_count": recorded["day_count"],
            "miss_count": recorded["miss_count"],
            "frozen": bool(recorded["frozen"]),
            "fresh": True,
            "detail": gh_result.get("detail", {}),
            "escalate_eligible": recorded["escalate_eligible"],
        }

    # MCP-backed type, or auto disabled: hand the lookup to the agent.
    return {
        **base,
        "status": "needs_lookup",
        "action": "perform_lookup",
        "verdict": existing["last_verdict"] if existing else None,
        "display": make_display(existing, now_dt),
        "day_count": existing["day_count"] if existing else 0,
        "miss_count": existing["miss_count"] if existing else 0,
        "frozen": bool(existing["frozen"]) if existing else False,
        "fresh": False,
        "lookup": lookup_directive(claim_type, identifier),
    }


def get_claim(claim_type: str, identifier: str, *, now: datetime | None = None) -> dict | None:
    conn = get_conn()
    ensure_table(conn)
    row = _fetch_row(conn, claim_hash(claim_type, identifier))
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["display"] = make_display(d, _now(now))
    return d


def list_claims(*, frozen: bool | None = None, status: str | None = None,
                claim_type: str | None = None, now: datetime | None = None) -> list[dict]:
    conn = get_conn()
    ensure_table(conn)
    conds, params = [], []
    if frozen is not None:
        conds.append("frozen = ?")
        params.append(1 if frozen else 0)
    if status:
        conds.append("last_verdict = ?")
        params.append(status)
    if claim_type:
        conds.append("claim_type = ?")
        params.append(claim_type)
    q = "SELECT * FROM claim_verifications"
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY day_count DESC, updated_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    now_dt = _now(now)
    out = []
    for r in rows:
        d = dict(r)
        d["display"] = make_display(d, now_dt)
        out.append(d)
    return out


# --- CLI -----------------------------------------------------------------
def _cli_now(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = _parse_iso(value)
    if dt is None:
        raise argparse.ArgumentTypeError("--now must be ISO 8601")
    return dt


def cmd_check(args: argparse.Namespace) -> None:
    print(json.dumps(check_artifact(
        args.type, args.id, now=_cli_now(args.now),
        auto=not args.no_auto, expect_state=args.expect_state,
    ), indent=2, default=str))


def cmd_record(args: argparse.Namespace) -> None:
    print(json.dumps(record_result(
        args.type, args.id, args.result, now=_cli_now(args.now),
    ), indent=2, default=str))


def cmd_get(args: argparse.Namespace) -> None:
    res = get_claim(args.type, args.id)
    print(json.dumps(res, indent=2, default=str) if res else json.dumps(
        {"status": "not_found", "claim_type": args.type, "identifier": args.id}))


def cmd_list(args: argparse.Namespace) -> None:
    print(json.dumps(list_claims(
        frozen=(True if args.frozen else None),
        status=args.status, claim_type=args.type,
    ), indent=2, default=str))


def cmd_types(args: argparse.Namespace) -> None:
    print(json.dumps({
        "claim_types": list(CLAIM_TYPES),
        "ttl_hours": TTL_HOURS,
        "default_ttl_hours": DEFAULT_TTL_HOURS,
        "auto_resolved": list(AUTO_TYPES),
        "verdicts": list(VERDICTS),
        "enabled": verification_enabled(),
        "escalation_threshold": escalation_threshold(),
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Valor artifact-verification gate")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Check a claim (cache-first; auto-resolves GitHub)")
    p_check.add_argument("--type", required=True, choices=CLAIM_TYPES)
    p_check.add_argument("--id", required=True, help="Claim identifier (see `types`)")
    p_check.add_argument("--expect-state", default=None,
                         help="GitHub only: require a specific state (merged|closed|open)")
    p_check.add_argument("--no-auto", action="store_true",
                         help="Do not auto-resolve via gh; always return needs_lookup")
    p_check.add_argument("--now", default=None, help="ISO timestamp override (testing)")

    p_record = sub.add_parser("record", help="Record a verdict from an agent lookup")
    p_record.add_argument("--type", required=True, choices=CLAIM_TYPES)
    p_record.add_argument("--id", required=True)
    p_record.add_argument("--result", required=True, choices=VERDICTS)
    p_record.add_argument("--now", default=None, help="ISO timestamp override (testing)")

    p_get = sub.add_parser("get", help="Show a single claim's cached state")
    p_get.add_argument("--type", required=True, choices=CLAIM_TYPES)
    p_get.add_argument("--id", required=True)

    p_list = sub.add_parser("list", help="List cached claims (for audits)")
    p_list.add_argument("--frozen", action="store_true", help="Only frozen (unverified) claims")
    p_list.add_argument("--status", default=None, choices=VERDICTS, help="Filter by last verdict")
    p_list.add_argument("--type", default=None, choices=CLAIM_TYPES, help="Filter by claim type")

    sub.add_parser("types", help="Print supported claim types, TTLs, and config")

    args = parser.parse_args()
    {
        "check": cmd_check,
        "record": cmd_record,
        "get": cmd_get,
        "list": cmd_list,
        "types": cmd_types,
    }[args.command](args)


if __name__ == "__main__":
    main()
