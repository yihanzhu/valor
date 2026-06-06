"""Tests for the artifact-verification gate (src/verify.py).

The headline test is `test_phantom_claim_demotes_by_run_2`: it replays the real
phantom-propagation chain that motivated this work and asserts the claim is
demoted (not blindly re-incremented) within two gated runs.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


UTC = timezone.utc
T0 = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)


def _write_state(state_path, **overrides):
    base = json.loads(state_path.read_text())
    base.update(overrides)
    state_path.write_text(json.dumps(base))


# --- TTL policy (locked decision #1: per-type) ---------------------------
def test_ttl_per_type(verify_db):
    verify, _, _ = verify_db
    assert verify.ttl_hours_for("github_pr") == 4
    assert verify.ttl_hours_for("jira") == 4
    assert verify.ttl_hours_for("confluence") == 24
    assert verify.ttl_hours_for("drive") == 24
    assert verify.ttl_hours_for("slack") == 24 * 7


def test_ttl_override_from_state(verify_db):
    verify, _, state_path = verify_db
    _write_state(state_path, verification={
        "enabled": True, "escalation_threshold": 3,
        "ttl_overrides": {"confluence": 1},
    })
    assert verify.ttl_hours_for("confluence") == 1
    assert verify.ttl_hours_for("slack") == 24 * 7  # untouched


# --- Identity ------------------------------------------------------------
def test_claim_hash_stable_across_wording(verify_db):
    verify, _, _ = verify_db
    a = verify.claim_hash("confluence", "PROJ-42")
    b = verify.claim_hash("confluence", "  proj-42  ")
    c = verify.claim_hash("confluence", "PROJ-42\t")
    assert a == b == c


def test_claim_hash_differs_by_type(verify_db):
    verify, _, _ = verify_db
    assert verify.claim_hash("confluence", "PROJ-42") != verify.claim_hash("jira", "PROJ-42")


# --- State machine (locked decision #3: cumulative) ----------------------
def test_unresolved_increments_once_per_day(verify_db, monkeypatch):
    # Pin UTC so the local-day dedup boundary is deterministic regardless of the
    # CI runner's timezone (T0 is 09:00 UTC; +6h stays the same UTC/local day).
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    try:
        verify, _, _ = verify_db
        r = verify.record_result("confluence", "X", "unresolved", now=T0)
        assert r["day_count"] == 1 and r["miss_count"] == 1
        # Same calendar day -> no double-count (briefing + wrapup both run).
        r = verify.record_result("confluence", "X", "unresolved", now=T0 + timedelta(hours=6))
        assert r["day_count"] == 1 and r["miss_count"] == 1
        # Next day -> increments.
        r = verify.record_result("confluence", "X", "unresolved", now=T0 + timedelta(days=1))
        assert r["day_count"] == 2 and r["miss_count"] == 2
    finally:
        time.tzset()  # monkeypatch restores TZ env; re-sync libc


def test_unresolved_dedup_uses_local_day_not_utc(verify_db, monkeypatch):
    # M13: the per-day dedup must key on the user's LOCAL day, not the UTC day.
    # Pin a western zone so local midnight != UTC midnight, then straddle UTC
    # midnight within a single local day.
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        verify, _, _ = verify_db
        # Both instants are the SAME local day (June 5 evening, EDT -04:00) but
        # straddle UTC midnight: 23:00Z (local 19:00) and next-UTC-day 01:00Z.
        t_eve = datetime(2026, 6, 5, 23, 0, tzinfo=UTC)
        t_late = datetime(2026, 6, 6, 1, 0, tzinfo=UTC)
        r = verify.record_result("confluence", "Y", "unresolved", now=t_eve)
        assert r["day_count"] == 1 and r["miss_count"] == 1
        # Same LOCAL day -> must NOT double-count (the bug counted this as 2).
        r = verify.record_result("confluence", "Y", "unresolved", now=t_late)
        assert r["day_count"] == 1 and r["miss_count"] == 1
        assert r["last_counted_date"] == "2026-06-05"
        # A genuinely new local day still increments.
        t_next = datetime(2026, 6, 7, 1, 0, tzinfo=UTC)  # local June 6, 21:00
        r = verify.record_result("confluence", "Y", "unresolved", now=t_next)
        assert r["day_count"] == 2 and r["miss_count"] == 2
    finally:
        time.tzset()


def test_resolved_clears_counters(verify_db):
    verify, _, _ = verify_db
    verify.record_result("confluence", "X", "unresolved", now=T0)
    verify.record_result("confluence", "X", "unresolved", now=T0 + timedelta(days=1))
    r = verify.record_result("confluence", "X", "resolved", now=T0 + timedelta(days=2))
    assert r["verified"] == 1
    assert r["day_count"] == 0 and r["miss_count"] == 0
    assert r["frozen"] == 0
    assert r["resolved_at"] is not None
    assert "done" in r["display"]


def test_unverified_freezes_counter(verify_db):
    verify, _, _ = verify_db
    verify.record_result("confluence", "X", "unresolved", now=T0)
    verify.record_result("confluence", "X", "unresolved", now=T0 + timedelta(days=1))
    # day_count == 2 now. An unverified verdict must NOT advance it.
    r = verify.record_result("confluence", "X", "unverified", now=T0 + timedelta(days=2))
    assert r["frozen"] == 1
    assert r["verified"] is None
    assert r["day_count"] == 2  # frozen, not 3
    assert r["miss_count"] == 2
    assert "confirm or drop" in r["display"]


# --- check_artifact decisions -------------------------------------------
def test_disabled_skips_gate(verify_db):
    verify, _, state_path = verify_db
    _write_state(state_path, verification={"enabled": False})
    r = verify.check_artifact("confluence", "X", now=T0)
    assert r["action"] == "skip" and r["status"] == "disabled"


def test_never_checked_mcp_type_needs_lookup(verify_db):
    verify, _, _ = verify_db
    r = verify.check_artifact("confluence", "PROJ-42", now=T0)
    assert r["action"] == "perform_lookup"
    assert r["status"] == "needs_lookup"
    assert r["lookup"]["method"] == "cql"
    assert "PROJ-42" in r["lookup"]["query"]


def test_fresh_cached_verdict_is_trusted(verify_db):
    verify, _, _ = verify_db
    verify.record_result("confluence", "X", "unresolved", now=T0)
    r = verify.check_artifact("confluence", "X", now=T0 + timedelta(hours=2))  # < 24h TTL
    assert r["action"] == "trust" and r["status"] == "cached" and r["fresh"] is True
    assert r["verdict"] == "unresolved"


def test_stale_verdict_triggers_relookup(verify_db):
    verify, _, _ = verify_db
    verify.record_result("confluence", "X", "unresolved", now=T0)
    r = verify.check_artifact("confluence", "X", now=T0 + timedelta(hours=25))  # > 24h TTL
    assert r["action"] == "perform_lookup"


def test_unverified_is_not_fresh(verify_db):
    verify, _, _ = verify_db
    # An unverified verdict never counts as a trustworthy cache hit.
    verify.record_result("confluence", "X", "unverified", now=T0)
    r = verify.check_artifact("confluence", "X", now=T0 + timedelta(minutes=1))
    assert r["action"] == "perform_lookup"


# --- GitHub auto-resolution ---------------------------------------------
def test_github_merged_auto_resolves(verify_db, monkeypatch):
    verify, _, _ = verify_db
    monkeypatch.setattr(verify, "gh_available", lambda: True)
    monkeypatch.setattr(verify, "_run_gh", lambda args: {
        "state": "MERGED", "title": "rollback DAG", "url": "http://x", "mergedAt": "t"})
    r = verify.check_artifact("github_pr", "ExampleOrg/repo#123", now=T0)
    assert r["action"] == "checked" and r["verdict"] == "resolved"
    assert r["detail"]["state"] == "MERGED"


def test_github_open_is_unresolved(verify_db, monkeypatch):
    verify, _, _ = verify_db
    monkeypatch.setattr(verify, "gh_available", lambda: True)
    monkeypatch.setattr(verify, "_run_gh", lambda args: {"state": "OPEN", "title": "t", "url": "u"})
    r = verify.check_artifact("github_pr", "repo#456", now=T0)
    assert r["verdict"] == "unresolved" and r["day_count"] == 1


def test_github_missing_gh_is_unverified(verify_db, monkeypatch):
    verify, _, _ = verify_db
    monkeypatch.setattr(verify, "gh_available", lambda: False)
    r = verify.check_artifact("github_pr", "repo#456", now=T0)
    assert r["verdict"] == "unverified"
    assert r["frozen"] is True
    # M12: an unconfirmable lookup must not masquerade as a definitive "checked";
    # it is demoted to a lookup directive so the agent confirms instead.
    assert r["status"] == "needs_lookup"
    assert r["action"] == "perform_lookup"
    assert r["fresh"] is False
    assert r["lookup"]["method"] == "gh"


def test_github_lookup_failure_is_unverified_not_checked(verify_db, monkeypatch):
    # gh is present but the lookup itself fails (returns None) -> unverified, and
    # demoted to perform_lookup rather than reported as a real check (M12).
    verify, _, _ = verify_db
    monkeypatch.setattr(verify, "gh_available", lambda: True)
    monkeypatch.setattr(verify, "_run_gh", lambda args: None)
    r = verify.check_artifact("github_pr", "repo#789", now=T0)
    assert r["verdict"] == "unverified"
    assert r["status"] == "needs_lookup"
    assert r["action"] == "perform_lookup"
    assert r["frozen"] is True


def test_github_expect_state_merged(verify_db, monkeypatch):
    verify, _, _ = verify_db
    monkeypatch.setattr(verify, "gh_available", lambda: True)
    monkeypatch.setattr(verify, "_run_gh", lambda args: {"state": "CLOSED", "title": "t", "url": "u"})
    # CLOSED-but-not-merged should be unresolved when we specifically expect merged.
    r = verify.check_artifact("github_pr", "repo#9", now=T0, expect_state="merged")
    assert r["verdict"] == "unresolved"


def test_parse_pr_identifier_forms(verify_db):
    verify, _, _ = verify_db
    assert verify._parse_pr_identifier("owner/repo#123") == ("owner/repo", "123")
    assert verify._parse_pr_identifier("repo#123", "deflt") == ("deflt/repo", "123")
    assert verify._parse_pr_identifier("#123") == ("", "123")
    assert verify._parse_pr_identifier("123") == ("", "123")  # bare int still works
    assert verify._parse_pr_identifier(
        "https://github.com/o/r/pull/55") == ("o/r", "55")


def test_parse_pr_identifier_rejects_non_numeric(verify_db):
    # L16: a non-integer number segment yields no PR number (rather than stripping
    # non-digits and fabricating one), so a mis-routed Jira key can't look up a
    # bogus PR. The repo portion's own digits are untouched.
    verify, _, _ = verify_db
    assert verify._parse_pr_identifier("PROJ-42") == ("", "")
    assert verify._parse_pr_identifier("repo#12a", "deflt") == ("deflt/repo", "")
    assert verify._parse_pr_identifier("repo-123#45", "deflt") == ("deflt/repo-123", "45")


def test_github_jira_key_misrouted_is_unverified(verify_db, monkeypatch):
    # A Jira-style key wrongly given to a github_pr claim must be reported
    # unverified (-> perform_lookup) WITHOUT ever consulting gh against a
    # fabricated PR number.
    verify, _, _ = verify_db
    monkeypatch.setattr(verify, "gh_available", lambda: True)
    def _must_not_run(args):  # noqa: ANN001
        raise AssertionError("gh must not be consulted for a non-numeric identifier")
    monkeypatch.setattr(verify, "_run_gh", _must_not_run)
    r = verify.check_artifact("github_pr", "PROJ-42", now=T0)
    assert r["verdict"] == "unverified"
    assert r["action"] == "perform_lookup"
    assert r["detail"]["reason"] == "no PR number in identifier"


# --- Escalation eligibility (Phase 3 reads this) -------------------------
def test_escalation_eligible_after_threshold(verify_db):
    verify, _, _ = verify_db
    for i in range(3):
        r = verify.record_result("slack", "spec review follow-up", "unresolved", now=T0 + timedelta(days=i))
    assert r["miss_count"] == 3
    assert r["escalate_eligible"] is True


def test_escalation_resets_on_resolved(verify_db):
    verify, _, _ = verify_db
    for i in range(3):
        verify.record_result("slack", "m", "unresolved", now=T0 + timedelta(days=i))
    r = verify.record_result("slack", "m", "resolved", now=T0 + timedelta(days=3))
    assert r["escalate_eligible"] is False and r["miss_count"] == 0


# --- ACCEPTANCE: the real PROJ-42 phantom chain --------------------------
def test_phantom_claim_demotes_by_run_2(verify_db):
    """Replay the actual evidence chain.

    Before the gate: the "PROJ-42 1-pager unposted" claim rode 14 daily
    increments (week ~14) with zero Confluence checks. After the gate, an
    unverifiable claim must be demoted to 'confirm or drop?' and its counter
    frozen within two gated runs -- never silently advanced.
    """
    verify, _, _ = verify_db
    CLAIM = ("confluence", "PROJ-42")

    # History: the claim arrives already carried for 13 days of confirmed-missing
    # (the pre-gate reality), so day_count reflects the real chronic streak.
    for i in range(13):
        verify.record_result(*CLAIM, "unresolved", now=T0 + timedelta(days=i))
    seeded = verify.get_claim(*CLAIM, now=T0 + timedelta(days=12))
    assert seeded["day_count"] == 13

    # --- RUN 1 (gated briefing/wrapup, day 14): the gate fires. ---
    run1_day = T0 + timedelta(days=13)
    chk1 = verify.check_artifact(*CLAIM, now=run1_day)
    # TTL is 24h and last check was "yesterday" -> stale -> must re-verify.
    assert chk1["action"] == "perform_lookup", "gate must force a live lookup"

    # The bug was that nobody did the lookup. The gate makes that explicit: an
    # agent that cannot confirm records 'unverified' rather than re-asserting.
    rec1 = verify.record_result(*CLAIM, "unverified", now=run1_day)
    assert rec1["frozen"] == 1
    assert rec1["day_count"] == 13, "counter must FREEZE, not advance to 14"
    assert "confirm or drop" in rec1["display"]

    # --- RUN 2 (next day): still demoted, still frozen, never 'fact'. ---
    run2_day = T0 + timedelta(days=14)
    chk2 = verify.check_artifact(*CLAIM, now=run2_day)
    assert chk2["action"] == "perform_lookup"
    assert chk2["frozen"] is True
    assert chk2["day_count"] == 13, "still frozen on run 2 -- no blind 14->15 march"
    # Demoted, by run 2 at the latest. Phantom propagation is broken.
    assert chk2["verdict"] == "unverified"


def test_phantom_resolves_when_artifact_found(verify_db):
    """The positive path: the day the page is actually posted, the gate sees
    it, clears the claim, and the chronic streak ends."""
    verify, _, _ = verify_db
    CLAIM = ("confluence", "PROJ-42")
    for i in range(13):
        verify.record_result(*CLAIM, "unresolved", now=T0 + timedelta(days=i))

    # Agent runs the CQL lookup and finds the page.
    rec = verify.record_result(*CLAIM, "resolved", now=T0 + timedelta(days=13))
    assert rec["verified"] == 1 and rec["day_count"] == 0 and rec["frozen"] == 0

    # Next briefing trusts the fresh resolved verdict and would drop the claim.
    chk = verify.check_artifact(*CLAIM, now=T0 + timedelta(days=13, hours=2))
    assert chk["action"] == "trust" and chk["verdict"] == "resolved"
    assert "done" in chk["display"]


# --- list / get ----------------------------------------------------------
def test_list_filters(verify_db):
    verify, _, _ = verify_db
    verify.record_result("confluence", "frozen-one", "unverified", now=T0)
    verify.record_result("slack", "missing-one", "unresolved", now=T0)
    verify.record_result("jira", "done-one", "resolved", now=T0)

    assert {c["identifier"] for c in verify.list_claims(frozen=True)} == {"frozen-one"}
    assert {c["identifier"] for c in verify.list_claims(status="unresolved")} == {"missing-one"}
    assert {c["identifier"] for c in verify.list_claims(claim_type="jira")} == {"done-one"}


def test_get_missing_returns_none(verify_db):
    verify, _, _ = verify_db
    assert verify.get_claim("confluence", "nope") is None


# --- CLI end-to-end (argparse wiring) ------------------------------------
def test_cli_check_record_check(tmp_path):
    """Drive the real CLI via subprocess, redirecting HOME to a temp .valor so
    we exercise argparse -> functions -> JSON without touching the real DB."""
    import os
    import subprocess
    import sys

    home = tmp_path
    valor = home / ".valor"
    valor.mkdir(parents=True)
    (valor / "state.json").write_text(json.dumps({
        "verification": {"enabled": True, "escalation_threshold": 3, "ttl_overrides": {}},
    }))
    env = {**os.environ, "HOME": str(home)}
    repo_root = str(Path(__file__).parent.parent)

    def run(*args):
        proc = subprocess.run(
            [sys.executable, "src/verify.py", *args],
            capture_output=True, text=True, cwd=repo_root, env=env,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    now = T0.isoformat()
    r = run("check", "--type", "confluence", "--id", "PROJ-42", "--now", now)
    assert r["action"] == "perform_lookup"

    r = run("record", "--type", "confluence", "--id", "PROJ-42",
            "--result", "unverified", "--now", now)
    assert r["frozen"] == 1

    r = run("check", "--type", "confluence", "--id", "PROJ-42", "--now", now)
    assert r["action"] == "perform_lookup" and r["frozen"] is True
