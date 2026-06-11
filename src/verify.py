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

Claims lifecycle (the mechanical layer added after the 2026-06 phantom-send
incident — see register_claim/reconcile/carry_write):

    draft time   -> register   (claim born with a search recipe; slack claims
                                must pin a destination or be --confirm-only)
    wrap-up      -> reconcile  (runtime-enumerated worklist; agent executes it),
                    record, carry-write (file statuses stamped from the cache)
    session start-> evidence_cli context embeds context_claims_summary() so the
                    briefing receives the open worklist without asking.

CLI:
    verify.py check       --type T --id ID [--expect-state S] [--no-auto] [--now ISO]
    verify.py record      --type T --id ID --result resolved|unresolved|unverified [--now ISO]
    verify.py get         --type T --id ID
    verify.py list        [--frozen] [--status resolved|unresolved|unverified] [--type T]
    verify.py types       (print supported claim types + TTLs)
    verify.py register    --type T --id ID [--recipe JSON] [--assert-state S] [--confirm-only]
    verify.py reconcile   [--no-auto] [--now ISO]
    verify.py carry-write --date YYYY-MM-DD --items-json JSON|--items-file PATH [--narrative-file PATH]

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
# TTLs are VERDICT-AWARE. A `resolved` verdict describes an immutable event (a
# sent Slack message stays sent; a merged PR stays merged) so it can cache long.
# An `unresolved` verdict describes a mutable ABSENCE ("not sent yet", "still
# open") that can flip at any moment — a long unresolved TTL is how a "not sent"
# claim coasted for 6 days on a stale cache while the message sat in the channel.
TTL_HOURS = {
    "github_pr": 4,
    "jira": 4,
    "confluence": 24,
    "drive": 24,
    "slack": 24 * 7,
}
UNRESOLVED_TTL_HOURS = {
    "github_pr": 4,
    "jira": 4,
    "confluence": 24,
    "drive": 24,
    "slack": 12,
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


def ttl_hours_for(claim_type: str, verdict: str | None = None) -> int:
    """Per-type, verdict-aware TTL, overridable via state.verification.ttl_overrides.

    An integer override applies to both verdicts (backwards compatible).
    `verdict` of "unresolved" selects the short table; anything else (including
    None and "resolved") selects the long one.
    """
    cfg = _read_state().get("verification", {})
    overrides = cfg.get("ttl_overrides", {}) if isinstance(cfg, dict) else {}
    if isinstance(overrides, dict) and claim_type in overrides:
        try:
            return int(overrides[claim_type])
        except (TypeError, ValueError):
            pass
    if verdict == "unresolved":
        return UNRESOLVED_TTL_HOURS.get(claim_type, DEFAULT_TTL_HOURS)
    return TTL_HOURS.get(claim_type, DEFAULT_TTL_HOURS)


# --- Identity ------------------------------------------------------------
_JIRA_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]+-\d+$")


def canonical_identifier(claim_type: str, identifier: str) -> str:
    """Collapse the per-type identifier variants the spec used to tolerate.

    The live cache proved that offering formats invites fragmentation
    (`github_pr|1411` and `github_pr|ExampleOrg/example-repo#1411` forked
    separate day-counters for the same PR). Canonicalize in the runtime so
    wording drift can't fork a counter, whatever the spec says:

      github_pr -> 'owner/repo#N' when a repo is known (bare 'repo' gains
                   `github_owner` from state), else '#N'. Non-PR-shaped ids
                   fall through to the generic fold.
      jira      -> the key uppercased ('proj-42' == 'PROJ-42').
      others    -> whitespace/case fold (unchanged).
    """
    ident = re.sub(r"\s+", " ", identifier.strip())
    if claim_type == "github_pr":
        owner = _read_state().get("github_owner", "")
        repo_spec, num = _parse_pr_identifier(ident, owner)
        if num:
            return f"{repo_spec}#{num}" if repo_spec else f"#{num}"
    elif claim_type == "jira" and _JIRA_KEY_RE.match(ident):
        return ident.upper()
    return ident


def normalize_identifier(claim_type: str, identifier: str) -> str:
    """Stable, case-insensitive identity so the same claim accumulates across
    runs instead of forking a new counter every time the wording drifts."""
    norm = canonical_identifier(claim_type, identifier).lower()
    return f"{claim_type}|{norm}"


def claim_hash(claim_type: str, identifier: str) -> str:
    key = normalize_identifier(claim_type, identifier)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _row_metadata(row: dict | None) -> dict:
    if not row:
        return {}
    try:
        meta = json.loads(row.get("metadata") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _merge_metadata(conn: sqlite3.Connection, chash: str, updates: dict) -> dict:
    """Dict-merge `updates` into a row's metadata JSON (row must exist)."""
    row = _fetch_row(conn, chash)
    meta = _row_metadata(dict(row) if row else None)
    meta.update(updates)
    conn.execute(
        "UPDATE claim_verifications SET metadata = ?, updated_at = ? WHERE claim_hash = ?",
        (json.dumps(meta), _now().isoformat(), chash),
    )
    return meta


def _heal_fragments(conn: sqlite3.Connection) -> list[dict]:
    """Merge rows whose stored hash predates canonicalization, plus bare-'#N'
    github_pr rows that match exactly one repo-qualified sibling.

    Merge policy: keep the canonical row; take max counters (the chronic streak
    is the signal), earliest first_seen, and the verdict fields of whichever row
    was checked most recently. Idempotent — safe to run at the top of every
    reconcile.
    """
    healed: list[dict] = []
    rows = [dict(r) for r in conn.execute("SELECT * FROM claim_verifications").fetchall()]

    def _merge(src: dict, dst_hash: str, dst: dict | None, canonical_id: str) -> None:
        if dst is None:
            conn.execute(
                "UPDATE claim_verifications SET claim_hash = ?, identifier = ? WHERE claim_hash = ?",
                (dst_hash, canonical_id, src["claim_hash"]),
            )
        else:
            src_checked = _parse_iso(src.get("last_checked"))
            dst_checked = _parse_iso(dst.get("last_checked"))
            newer = src if (src_checked or datetime.min.replace(tzinfo=timezone.utc)) > (
                dst_checked or datetime.min.replace(tzinfo=timezone.utc)) else dst
            meta = _row_metadata(dst)
            meta.update(_row_metadata(src))
            conn.execute(
                """
                UPDATE claim_verifications SET
                    verified = ?, last_verdict = ?, last_checked = ?,
                    last_counted_date = ?, frozen = ?, resolved_at = ?,
                    miss_count = ?, day_count = ?, first_seen = ?, metadata = ?
                WHERE claim_hash = ?
                """,
                (
                    newer.get("verified"), newer.get("last_verdict"), newer.get("last_checked"),
                    newer.get("last_counted_date"), newer.get("frozen"), newer.get("resolved_at"),
                    max(src.get("miss_count") or 0, dst.get("miss_count") or 0),
                    max(src.get("day_count") or 0, dst.get("day_count") or 0),
                    min(src.get("first_seen") or "9999", dst.get("first_seen") or "9999"),
                    json.dumps(meta), dst_hash,
                ),
            )
            conn.execute("DELETE FROM claim_verifications WHERE claim_hash = ?", (src["claim_hash"],))
        healed.append({"from": src["identifier"], "into": canonical_id})

    # Pass 1: re-hash every row under current canonicalization.
    for row in rows:
        canonical_id = canonical_identifier(row["claim_type"], row["identifier"])
        chash = claim_hash(row["claim_type"], row["identifier"])
        if chash != row["claim_hash"]:
            dst = _fetch_row(conn, chash)
            _merge(row, chash, dict(dst) if dst else None, canonical_id)

    # Pass 2: a bare '#N' github_pr row adopts its repo-qualified sibling when
    # exactly one exists (ambiguous numbers stay separate — never guess).
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM claim_verifications WHERE claim_type = 'github_pr'").fetchall()]
    bare = [r for r in rows if r["identifier"].startswith("#")]
    for row in bare:
        suffix = row["identifier"].lower()
        qualified = [r for r in rows
                     if not r["identifier"].startswith("#")
                     and r["identifier"].lower().endswith(suffix)]
        if len(qualified) == 1:
            dst = qualified[0]
            _merge(row, dst["claim_hash"], dst, dst["identifier"])

    if healed:
        conn.commit()
    return healed


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
    if _row_metadata(row).get("confirm_only"):
        return "unverified — confirm or drop? (no destination pinned; cannot be checked)"
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
def lookup_directive(claim_type: str, identifier: str, metadata: dict | None = None) -> dict:
    """What the agent should run to verify an MCP-backed claim type.

    When the claim was registered with a recipe (channel/recipient/keywords
    captured at draft time), the directive is built from it — a scoped Slack
    search instead of a bare-keywords guess.
    """
    ident = identifier.strip()
    recipe = (metadata or {}).get("recipe") or {}
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
        if recipe.get("channel") or recipe.get("recipient"):
            scope = f"in:{recipe['channel']}" if recipe.get("channel") else f"to:{recipe['recipient']}"
            parts = [scope, "from:me"]
            if recipe.get("keywords"):
                parts.append(f'"{recipe["keywords"]}"')
            if recipe.get("drafted_at"):
                parts.append(f"after:{str(recipe['drafted_at'])[:10]}")
            return {
                "method": "search",
                "query": " ".join(parts),
                "tool_hint": "Slack MCP message search (recipe-scoped; match channel/recipient AND content)",
                "resolved_if": "a real (non-draft) sent message matching the recipe exists",
            }
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

    base = {
        "claim_hash": chash,
        "claim_type": claim_type,
        "identifier": identifier,
    }

    if not verification_enabled():
        return {**base, "status": "disabled", "action": "skip", "verdict": None,
                "display": "verification disabled"}

    conn = get_conn()
    ensure_table(conn)
    row = _fetch_row(conn, chash)
    existing = dict(row) if row is not None else None
    conn.close()
    meta = _row_metadata(existing)

    # TTL depends on the cached verdict: "resolved" describes an immutable
    # event (long), "unresolved" a mutable absence (short).
    ttl = ttl_hours_for(claim_type, (existing or {}).get("last_verdict"))
    base["ttl_hours"] = ttl

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

    # A confirm-only claim (registered with no destination/recipe) has no
    # automated path by definition: the only valid move is asking the user.
    # It can never be asserted as fact.
    if meta.get("confirm_only") and not fresh:
        return {
            **base,
            "status": "confirm_only",
            "action": "ask_user",
            "verdict": existing["last_verdict"] if existing else None,
            "display": make_display(existing, now_dt),
            "day_count": existing["day_count"] if existing else 0,
            "miss_count": existing["miss_count"] if existing else 0,
            "frozen": bool(existing["frozen"]) if existing else False,
            "fresh": False,
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
                "lookup": lookup_directive(claim_type, identifier, meta),
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
        "lookup": lookup_directive(claim_type, identifier, meta),
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


# --- Claims lifecycle: register -> reconcile -> carry-write ---------------
# The 2026-06 phantom-send incident (a "not sent" claim carried 6 days after
# the message was sent and answered) proved that verification-as-diligence
# fails: the gate only saw claims the agent volunteered, and it never
# volunteered one. These three entry points invert control: claims are
# REGISTERED at draft time with a search recipe, RECONCILED into a runtime-
# enumerated worklist (the agent executes a checklist instead of remembering
# one), and the carry-forward is WRITTEN with statuses stamped from the cache
# so a skipped check renders as "unverified — confirm or drop?", never as fact.

# Lines that assert an artifact state. Used to flag claim-shaped prose that
# carries no registered claim (the tripwire for a bypassed lifecycle).
_SUSPECT_RE = re.compile(
    r"(?i)\b(not sent|unsent|unposted|not posted|drafted|awaiting reply|"
    r"still open|not merged|unpublished)\b"
)
_CLAIM_REF_MARK = "(claim:"

# A confirm-only claim surfaces as a question at most this many distinct days;
# after that it is "parked" — the weekly owns it, the daily stops nagging.
CONFIRM_ONLY_SURFACE_DAYS = 3


def register_claim(
    claim_type: str,
    identifier: str,
    *,
    recipe: dict | None = None,
    asserted_state: str | None = None,
    confirm_only: bool = False,
    now: datetime | None = None,
) -> dict:
    """Register a claim at draft/carry time so the gate can enumerate it later.

    Validation is the forcing function — a claim must be born verifiable:
      * github_pr ids must name a repo ('owner/repo#N'); bare numbers fork
        counters and cannot be checked outside one repo's context.
      * jira ids must be a real issue key.
      * slack claims must pin a destination (recipe.channel or recipe.recipient)
        — the only moment that's reliably known is draft time — unless
        explicitly registered --confirm-only, which can ONLY ever surface as a
        user question, never as an asserted fact.
    """
    if claim_type not in CLAIM_TYPES:
        raise ValueError(f"unknown claim_type '{claim_type}' (valid: {', '.join(CLAIM_TYPES)})")
    recipe = recipe or {}
    canonical = canonical_identifier(claim_type, identifier)

    if claim_type == "github_pr":
        repo_spec, num = _parse_pr_identifier(canonical, _read_state().get("github_owner", ""))
        if not num or not repo_spec:
            raise ValueError(
                "github_pr claims must use 'owner/repo#N' (a bare PR number forks "
                "counters and can't be checked) — pass the repo-qualified id"
            )
    elif claim_type == "jira" and not _JIRA_KEY_RE.match(canonical):
        raise ValueError("jira claims must use the issue key, e.g. PROJ-42")
    elif claim_type == "slack" and not confirm_only \
            and not (recipe.get("channel") or recipe.get("recipient")):
        raise ValueError(
            "slack claims need recipe.channel or recipe.recipient (pin the destination "
            "at draft time), or pass --confirm-only to register an unverifiable claim "
            "that can only surface as a user question"
        )

    now_dt = _now(now)
    now_iso = now_dt.isoformat()
    chash = claim_hash(claim_type, canonical)

    conn = get_conn()
    ensure_table(conn)
    row = _fetch_row(conn, chash)
    if row is None:
        conn.execute(
            """
            INSERT INTO claim_verifications
                (claim_hash, claim_type, identifier, verified, last_verdict,
                 last_checked, last_counted_date, miss_count, day_count, frozen,
                 resolved_at, first_seen, created_at, updated_at, metadata)
            VALUES (?,?,?,NULL,NULL,NULL,NULL,0,0,0,NULL,?,?,?,'{}')
            """,
            (chash, claim_type, canonical, now_iso, now_iso, now_iso),
        )
    meta_updates: dict = {"registered_at": now_iso}
    if recipe:
        meta_updates["recipe"] = recipe
    if asserted_state:
        meta_updates["asserted_state"] = asserted_state
    if confirm_only:
        meta_updates["confirm_only"] = True
    meta = _merge_metadata(conn, chash, meta_updates)
    conn.commit()
    existing = dict(_fetch_row(conn, chash))
    conn.close()

    if confirm_only or meta.get("confirm_only"):
        action = "ask_user"
    else:
        checked = check_artifact(claim_type, canonical, now=now_dt, auto=False)
        action = "trust" if checked.get("fresh") else "perform_lookup"

    out = {
        "canonical_id": canonical,
        "claim_hash": chash,
        "claim_type": claim_type,
        "action": action,
        "display": make_display(existing, now_dt),
    }
    if action == "perform_lookup":
        out["lookup"] = lookup_directive(claim_type, canonical, meta)
    return out


def _bucket_open_claims(
    conn: sqlite3.Connection,
    now_dt: datetime,
    *,
    mutate_surfacing: bool,
) -> dict:
    """Bucket every open (non-resolved) claim. Shared by reconcile (which may
    record surfacing for confirm-only claims) and the read-only context summary."""
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM claim_verifications "
        "WHERE last_verdict IS NULL OR last_verdict != 'resolved'"
    ).fetchall()]
    today = now_dt.astimezone().date().isoformat()
    fresh, stale, unverifiable = [], [], []

    for row in rows:
        meta = _row_metadata(row)
        entry = {
            "claim_type": row["claim_type"],
            "identifier": canonical_identifier(row["claim_type"], row["identifier"]),
            "verdict": row["last_verdict"],
            "display": make_display(row, now_dt),
            "day_count": row["day_count"] or 0,
            "last_checked": row["last_checked"],
        }
        if meta.get("confirm_only"):
            surfaced = meta.get("surfaced_dates") or []
            if mutate_surfacing and today not in surfaced:
                surfaced = (surfaced + [today])[-10:]
                _merge_metadata(conn, row["claim_hash"], {"surfaced_dates": surfaced})
            entry["action"] = "ask_user"
            entry["surfaced_count"] = len(surfaced)
            entry["parked"] = len(surfaced) > CONFIRM_ONLY_SURFACE_DAYS
            unverifiable.append(entry)
            continue
        if row["last_verdict"] == "unresolved":
            ttl = ttl_hours_for(row["claim_type"], "unresolved")
            last_dt = _parse_iso(row["last_checked"])
            if last_dt is not None and (now_dt - last_dt) < timedelta(hours=ttl):
                fresh.append(entry)
                continue
        # Stale-unresolved, frozen-unverified, or registered-but-never-checked:
        # all need a real look.
        entry["lookup"] = lookup_directive(row["claim_type"], row["identifier"], meta)
        entry["action"] = "perform_lookup"
        stale.append(entry)

    return {"fresh": fresh, "stale_needs_check": stale, "unverifiable": unverifiable}


def reconcile(*, auto: bool = True, now: datetime | None = None) -> dict:
    """Runtime-enumerated verification worklist over ALL open claims.

    The agent no longer chooses what to verify — it executes this list:
      fresh             -> trust the verdict, no action.
      stale_needs_check -> run each entry's `lookup`, then `record` the verdict.
      unverifiable      -> confirm-only claims: ask the user (skip ones marked
                           `parked` in a daily flow; the weekly owns those).
    With auto=True, stale github_pr claims are checked via `gh` inline.
    """
    now_dt = _now(now)
    conn = get_conn()
    ensure_table(conn)
    healed = _heal_fragments(conn)
    buckets = _bucket_open_claims(conn, now_dt, mutate_surfacing=True)
    conn.commit()
    conn.close()

    if auto:
        still_stale = []
        for entry in buckets["stale_needs_check"]:
            if entry["claim_type"] != "github_pr" or not gh_available():
                still_stale.append(entry)
                continue
            gh_result = check_github_pr(entry["identifier"])
            verdict = gh_result["verdict"]
            if verdict == "unverified":
                entry["auto_check"] = gh_result.get("detail", {})
                still_stale.append(entry)
                continue
            recorded = record_result("github_pr", entry["identifier"], verdict, now=now_dt)
            buckets["fresh"].append({
                "claim_type": "github_pr",
                "identifier": entry["identifier"],
                "verdict": verdict,
                "display": recorded["display"],
                "day_count": recorded["day_count"],
                "last_checked": recorded["last_checked"],
                "auto_checked": True,
            })
        buckets["stale_needs_check"] = still_stale

    return {
        "generated_at": now_dt.isoformat(),
        "enabled": verification_enabled(),
        "healed": healed,
        **buckets,
        "summary": {
            "fresh": len(buckets["fresh"]),
            "stale_needs_check": len(buckets["stale_needs_check"]),
            "unverifiable": len(buckets["unverifiable"]),
            "healed": len(healed),
        },
    }


def _suspect_lines(text: str) -> list[dict]:
    out = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _CLAIM_REF_MARK in line:
            continue
        if _SUSPECT_RE.search(line):
            out.append({"line": i, "excerpt": line.strip()[:120]})
    return out


def carry_write(
    date_str: str,
    items: list[dict],
    narrative: str | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    """Render and write the carry-forward file with claim statuses stamped
    FROM THE CACHE — never from the agent's wording. An item whose claim has no
    fresh verdict physically reads "unverified — confirm or drop?" in the file,
    so a skipped check cannot masquerade as a fact for tomorrow's briefing.

    items: [{"text": str, "claim_type": opt, "claim_id": opt,
             "section": "pickup"|"done"|"held" (default "pickup")}]
    narrative: freeform markdown appended verbatim under "## Notes" — the
    human-readable context (rationale, decisions, week framing) stays yours.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError("date must be YYYY-MM-DD")
    now_dt = _now(now)
    conn = get_conn()
    ensure_table(conn)

    sections: dict[str, list[str]] = {"pickup": [], "done": [], "held": []}
    suspects: list[dict] = []
    verdict_counts = {"resolved": 0, "unresolved": 0, "unchecked": 0}

    for item in items:
        text = str(item.get("text", "")).strip()
        section = item.get("section", "pickup")
        if section not in sections:
            section = "pickup"
        ctype, cid = item.get("claim_type"), item.get("claim_id")
        if ctype and cid:
            row = _fetch_row(conn, claim_hash(ctype, cid))
            row_d = dict(row) if row else None
            display = make_display(row_d, now_dt)
            verdict = (row_d or {}).get("last_verdict")
            if verdict in ("resolved", "unresolved"):
                # Stamp only a FRESH verdict as that verdict; a stale one is
                # demoted in print so it cannot ride the file as fact.
                last_dt = _parse_iso(row_d.get("last_checked"))
                ttl = ttl_hours_for(ctype, verdict)
                if last_dt is None or (now_dt - last_dt) >= timedelta(hours=ttl):
                    display = f"stale — re-verify before trusting (was: {display})"
                    verdict_counts["unchecked"] += 1
                else:
                    verdict_counts[verdict] += 1
            else:
                # Never-checked / frozen / unregistered: the file must carry the
                # question form, whatever the item text asserts.
                if row_d is None:
                    display = "unverified — confirm or drop? (claim not registered)"
                elif verdict is None and not _row_metadata(row_d).get("confirm_only"):
                    display = "unverified — confirm or drop? (never checked)"
                verdict_counts["unchecked"] += 1
            canonical = canonical_identifier(ctype, cid)
            sections[section].append(
                f"{text} — **{display}** *(claim: {ctype}|{canonical})*"
            )
        else:
            sections[section].append(text)
            suspects.extend(
                {"line": 0, "excerpt": s["excerpt"]} for s in _suspect_lines(text)
            )
    conn.close()

    if narrative:
        suspects.extend(_suspect_lines(narrative))

    gate_line = (
        f"Gate: {sum(verdict_counts.values())} claims — "
        f"{verdict_counts['resolved']} resolved · "
        f"{verdict_counts['unresolved']} unresolved · "
        f"{verdict_counts['unchecked']} unverified/unchecked"
    )

    lines = [
        "---",
        f"name: carry-forward-{date_str}",
        f'description: "Evening wrap-up carry-forward items for {date_str}"',
        "type: local",
        "tags: [tomorrow, wrap-up, carry-forward]",
        "---",
        "",
        f"# Carry-Forward Items — {date_str}",
        "",
        f"*{gate_line}*",
        "",
    ]
    if sections["pickup"]:
        lines += ["## Tomorrow's Pickup", ""]
        lines += [f"{i}. {t}" for i, t in enumerate(sections["pickup"], start=1)]
        lines.append("")
    if sections["done"]:
        lines += ["## Done / advanced today", ""]
        lines += [f"- {t}" for t in sections["done"]]
        lines.append("")
    if sections["held"]:
        lines += ["## Held (intentionally parked — do not surface)", ""]
        lines += [f"- {t}" for t in sections["held"]]
        lines.append("")
    if narrative:
        lines += ["## Notes", "", narrative.rstrip(), ""]
    content = "\n".join(lines)

    carry_dir = VALOR_HOME / "carry-forward"
    carry_dir.mkdir(parents=True, exist_ok=True)
    dated = carry_dir / f"carry-forward-{date_str}.md"
    latest = carry_dir / "latest.md"
    for target in (dated, latest):
        tmp = target.with_suffix(".tmp")
        tmp.write_text(content)
        tmp.replace(target)

    return {
        "path": str(dated),
        "latest": str(latest),
        "items": sum(len(v) for v in sections.values()),
        "gate_line": gate_line,
        "unregistered_suspects": suspects,
    }


def context_claims_summary(*, now: datetime | None = None, cap: int = 8) -> dict:
    """Read-only claims snapshot for `evidence_cli.py context` (every session
    start). This is the unskippable delivery channel: even after a wrap-up that
    registered nothing and hand-wrote the file, the next session sees the open
    worklist and any claim-shaped prose with no registered claim behind it.

    Never mutates, never shells out — cache math plus one small file read.
    """
    now_dt = _now(now)
    if not DB_PATH.exists():
        buckets = {"fresh": [], "stale_needs_check": [], "unverifiable": []}
    else:
        conn = get_conn()
        ensure_table(conn)
        buckets = _bucket_open_claims(conn, now_dt, mutate_surfacing=False)
        conn.close()

    def _slim(entry: dict) -> dict:
        slim = {
            "claim_type": entry["claim_type"],
            "identifier": entry["identifier"],
            "display": entry["display"],
        }
        if "lookup" in entry:
            slim["lookup"] = {
                "method": entry["lookup"]["method"],
                "query": str(entry["lookup"]["query"])[:160],
            }
        if entry.get("parked"):
            slim["parked"] = True
        return slim

    stale = buckets["stale_needs_check"]
    unverifiable = buckets["unverifiable"]
    suspects: list[dict] = []
    latest = VALOR_HOME / "carry-forward" / "latest.md"
    if latest.exists():
        try:
            suspects = _suspect_lines(latest.read_text())
        except OSError:
            suspects = []

    open_count = len(stale) + len(unverifiable) + len(buckets["fresh"])
    if open_count == 0 and not suspects:
        return {"open_count": 0}
    return {
        "open_count": open_count,
        "fresh": len(buckets["fresh"]),
        "stale_needs_check": [_slim(e) for e in stale[:cap]],
        "unverifiable": [_slim(e) for e in unverifiable[:cap]],
        "unstamped_assertions": [
            {"line": s["line"], "excerpt": s["excerpt"][:100]} for s in suspects[:5]
        ],
        "counts_truncated": len(stale) > cap or len(unverifiable) > cap or len(suspects) > 5,
    }


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
        "unresolved_ttl_hours": UNRESOLVED_TTL_HOURS,
        "default_ttl_hours": DEFAULT_TTL_HOURS,
        "auto_resolved": list(AUTO_TYPES),
        "verdicts": list(VERDICTS),
        "enabled": verification_enabled(),
        "escalation_threshold": escalation_threshold(),
        "confirm_only_surface_days": CONFIRM_ONLY_SURFACE_DAYS,
    }, indent=2))


def _parse_json_arg(value: str | None, flag: str) -> dict | list | None:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(json.dumps({"error": f"{flag} must be valid JSON: {exc}"}))


def cmd_register(args: argparse.Namespace) -> None:
    recipe = _parse_json_arg(args.recipe, "--recipe")
    if recipe is not None and not isinstance(recipe, dict):
        raise SystemExit(json.dumps({"error": "--recipe must be a JSON object"}))
    try:
        out = register_claim(
            args.type, args.id,
            recipe=recipe, asserted_state=args.assert_state,
            confirm_only=args.confirm_only, now=_cli_now(args.now),
        )
    except ValueError as exc:
        raise SystemExit(json.dumps({"error": str(exc)}))
    print(json.dumps(out, indent=2, default=str))


def cmd_reconcile(args: argparse.Namespace) -> None:
    print(json.dumps(
        reconcile(auto=not args.no_auto, now=_cli_now(args.now)),
        indent=2, default=str,
    ))


def cmd_carry_write(args: argparse.Namespace) -> None:
    if args.items_file:
        items = _parse_json_arg(Path(args.items_file).read_text(), "--items-file")
    else:
        items = _parse_json_arg(args.items_json, "--items-json")
    if not isinstance(items, list):
        raise SystemExit(json.dumps({"error": "items must be a JSON array"}))
    narrative = None
    if args.narrative_file:
        narrative = Path(args.narrative_file).read_text()
    try:
        out = carry_write(args.date, items, narrative, now=_cli_now(args.now))
    except ValueError as exc:
        raise SystemExit(json.dumps({"error": str(exc)}))
    print(json.dumps(out, indent=2, default=str))


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

    p_register = sub.add_parser(
        "register",
        help="Register a claim at draft/carry time with its verification recipe")
    p_register.add_argument("--type", required=True, choices=CLAIM_TYPES)
    p_register.add_argument("--id", required=True,
                            help="Canonical id (github_pr: owner/repo#N; slack: '<#channel-or-recipient>: <topic>')")
    p_register.add_argument("--recipe", default=None,
                            help='JSON search recipe, e.g. {"channel": "#x", "keywords": "...", "drafted_at": "..."}')
    p_register.add_argument("--assert-state", default=None, dest="assert_state",
                            help="What the claim asserts, e.g. 'not sent'")
    p_register.add_argument("--confirm-only", action="store_true",
                            help="No destination known — claim can only surface as a user question")
    p_register.add_argument("--now", default=None, help="ISO timestamp override (testing)")

    p_reconcile = sub.add_parser(
        "reconcile",
        help="Enumerate ALL open claims into a verification worklist (the checklist)")
    p_reconcile.add_argument("--no-auto", action="store_true",
                             help="Do not auto-resolve github_pr claims via gh")
    p_reconcile.add_argument("--now", default=None, help="ISO timestamp override (testing)")

    p_carry = sub.add_parser(
        "carry-write",
        help="Write the carry-forward file with claim statuses stamped from the cache")
    p_carry.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_carry.add_argument("--items-json", default=None,
                         help='JSON array of items: [{"text", "claim_type"?, "claim_id"?, "section"?}]')
    p_carry.add_argument("--items-file", default=None, help="Path to a JSON file of items")
    p_carry.add_argument("--narrative-file", default=None,
                         help="Path to freeform markdown appended verbatim under ## Notes")
    p_carry.add_argument("--now", default=None, help="ISO timestamp override (testing)")

    args = parser.parse_args()
    {
        "check": cmd_check,
        "record": cmd_record,
        "get": cmd_get,
        "list": cmd_list,
        "types": cmd_types,
        "register": cmd_register,
        "reconcile": cmd_reconcile,
        "carry-write": cmd_carry_write,
    }[args.command](args)


if __name__ == "__main__":
    main()
