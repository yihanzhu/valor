#!/usr/bin/env python3
"""Seed a self-contained Valor demo profile into a throwaway HOME.

Valor resolves its state through `Path.home()`, so pointing HOME at a scratch
directory gives the demo a complete parallel universe: its own career
framework, evidence store, state, and agent config. The real `~/.valor` is not
hidden from the demo -- it is unreachable, which is the point. Nothing in this
profile is real: the persona, tickets, PRs, calendar, and colleagues are all
invented (see `fixtures/`).

Usage (from the repo root):

    HOME=~/valor-demo bash install.sh          # install Valor into the demo home
    python3 examples/demo/seed.py ~/valor-demo # seed framework, state, evidence, fixtures
    HOME=~/valor-demo claude                   # run the demo

Re-seeding is a `--force` away, and `rm -rf ~/valor-demo` is the teardown.
Stdlib only, like the rest of Valor's runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FIXTURES_DIR = HERE / "fixtures"
EVIDENCE_FILE = HERE / "evidence.jsonl"
DEMO_MODE_FILE = HERE / "demo-mode.md"
FRAMEWORK_FILE = REPO / "examples" / "frameworks" / "software-engineer-ic-ladder.md"
CLI = REPO / "src" / "evidence_cli.py"
VERIFY = REPO / "src" / "verify.py"

DEMO_BEGIN = "# --- BEGIN VALOR DEMO MODE ---"
DEMO_END = "# --- END VALOR DEMO MODE ---"
VALOR_RULE_MARKER = "BEGIN VALOR"

# The demo's review cycle: half a year back, so any cycle the presenter picks in
# /valor-reflection has material in it.
CYCLE_DAYS = 182

# Fixtures that are state files rather than stand-ins for an integration, so
# they land somewhere other than ~/.valor/demo/.
SPECIAL_FIXTURES = {"carry_forward.md"}

TOKEN_RE = re.compile(r"\{\{(TODAY|MONDAY|LAST_MONDAY|CYCLE_START|TZ|YEAR)([+-]\d+)?\}\}")


# --------------------------------------------------------------------------
# dates & tokens


def build_context(today: date) -> dict:
    """Resolve the base dates the fixtures interpolate."""
    monday = today - timedelta(days=today.weekday())
    offset = datetime.now().astimezone().strftime("%z") or "+0000"
    return {
        "TODAY": today,
        "MONDAY": monday,
        "LAST_MONDAY": monday - timedelta(days=7),
        "CYCLE_START": today - timedelta(days=CYCLE_DAYS),
        "TZ": f"{offset[:3]}:{offset[3:]}",
        "YEAR": str(today.year),
    }


def render(text: str, ctx: dict) -> str:
    """Substitute `{{TODAY}}` / `{{TODAY-7}}` / `{{TZ}}` style tokens."""

    def sub(match):
        name, delta = match.group(1), match.group(2)
        base = ctx[name]
        if not isinstance(base, date):
            return base  # TZ / YEAR carry no offset
        return (base + timedelta(days=int(delta or 0))).isoformat()

    return TOKEN_RE.sub(sub, text)


# --------------------------------------------------------------------------
# safety


def resolve_target(raw: str, force: bool) -> Path:
    """Resolve the demo home, refusing anything that could be the real one."""
    target = Path(raw).expanduser().resolve()
    real_home = Path.home().resolve()

    if target == real_home:
        sys.exit(
            f"refusing to seed into your real home ({real_home}).\n"
            "Pass a throwaway directory, e.g. ~/valor-demo."
        )
    if target in real_home.parents or target == Path(target.anchor):
        sys.exit(f"refusing to seed into {target}: pick a dedicated directory.")
    if (target / ".valor").exists() and not force:
        sys.exit(
            f"{target / '.valor'} already exists. Re-seed with --force, "
            f"or start clean with: rm -rf {target}"
        )
    return target


# --------------------------------------------------------------------------
# CLI plumbing (every call runs against the demo HOME, never the real one)


def run(argv: list[str], home: Path, *, tolerate=False) -> str:
    env = dict(os.environ, HOME=str(home))
    env.pop("VALOR_HOME", None)
    proc = subprocess.run(
        [sys.executable, *argv], env=env, capture_output=True, text=True
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout).strip()
        if tolerate:
            print(f"  ! skipped ({argv[1] if len(argv) > 1 else argv[0]}): {message}")
            return ""
        sys.exit(f"command failed: {' '.join(argv)}\n{message}")
    return proc.stdout


def schema_version() -> int:
    """Read STATE_SCHEMA_VERSION from the source of truth."""
    match = re.search(
        r"STATE_SCHEMA_VERSION\s*=\s*(\d+)", (REPO / "src" / "evidence_cli.py").read_text()
    )
    if not match:
        sys.exit("could not read STATE_SCHEMA_VERSION from src/evidence_cli.py")
    return int(match.group(1))


# --------------------------------------------------------------------------
# the profile


def write_framework(valor: Path) -> None:
    shutil.copyfile(FRAMEWORK_FILE, valor / "career_framework.md")
    print(f"  framework: {FRAMEWORK_FILE.name} (L3 -> L4, ceiling L5)")


def write_state(valor: Path, ctx: dict) -> None:
    """The demo's state.json.

    Two settings matter more than the rest for a live demo: every integration
    is off (nothing reaches a real system) and `calendar_auto_write` is false
    (the day plan is shown, never written anywhere).
    """
    demo_dir = valor / "demo"
    state = {
        "state_schema_version": schema_version(),
        "current_level": "L3",
        "target_level": "L4",
        "ceiling_level": "L5",
        "last_briefing_date": "",
        "last_briefing_timestamp": "",
        "briefing_count": 41,
        "coaching_mode": "ambient",
        "user_work_areas": [
            "checkout",
            "payments provider integration",
            "retry and idempotency",
            "webhook delivery",
            "on-call reliability",
        ],
        "user_work_areas_pinned": [],
        "github_owner": "example-org",
        "jira_projects": ["PROJ"],
        "manager": {"name": "Sam", "email": "sam@example.com"},
        "integrations": {"github": False, "jira": False, "calendar": False, "news": False},
        # Pinned: no update check should interrupt a demo.
        "last_update_check": datetime.now().astimezone().isoformat(timespec="seconds"),
        "update_check_interval_hours": 0,
        "installed_version": (REPO / "VERSION").read_text().strip(),
        "verification": {"enabled": True, "escalation_threshold": 3, "ttl_overrides": {}},
        "escalate_in_one_on_one": [],
        "planning": {
            "calendar_auto_write": False,
            "workday_start": "09:00",
            "workday_end": "18:00",
            "deep_min_hours": 2.0,
            "post_meeting_break_minutes": 15,
            "block_granularity_minutes": 15,
            "morning_buffer_minutes": 15,
            "pre_meeting_prep_minutes": 30,
        },
        "one_on_one": {
            "doc": str(demo_dir / "one_on_one_doc.md"),
            "format_notes": (
                "Pinned block at the top, then one dated entry per week (## YYYY-MM-DD), "
                "newest first. Inside an entry: Goals this week, Progress, Blockers, Asks, "
                "Feedback as plain lines - no bold, no nested headers."
            ),
        },
        "project_focus": {
            "enabled": True,
            "mode": "meeting_derived",
            "current": "Checkout reliability",
            "flip": "after_sync",
            "syncs": [{"project": "Checkout reliability", "match": "Checkout weekly sync"}],
            "auto_sync_prep": True,
            "parked_projects": [],
            "meeting_catalog": [
                {"title": "Checkout standup", "category": "standup", "project": ""},
                {"title": "Alex / Sam 1:1", "category": "one_on_one", "project": ""},
                {
                    "title": "Checkout weekly sync",
                    "category": "project_sync",
                    "project": "Checkout reliability",
                },
                {
                    "title": "Payments provider integration call",
                    "category": "external",
                    "project": "Checkout reliability",
                },
            ],
        },
        "prioritization": {
            "week_goals": [
                "Land the refund idempotency fix (PROJ-231) - the one that matters",
                "Get the retry backoff PR (#418) merged, with a rollback note",
                "Start the p99 investigation (PROJ-259) if there's room",
            ],
            "week_start": ctx["MONDAY"].isoformat(),
            "goals_source": "1:1 doc (demo fixture)",
        },
        "standing_rules": [
            "PROJ-248 (platform's transport migration) is blocked until #418 merges - "
            "treat #418 as ahead of any new work",
            "Never plan deep work before 09:30 - standup and the morning buffer own that slot",
        ],
    }
    (valor / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    print("  state.json: L3 -> L4, all integrations OFF, calendar writes OFF")


def seed_evidence(home: Path, ctx: dict, limit: int | None) -> int:
    entries = []
    for line in EVIDENCE_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if "_comment" in record:
            continue
        entries.append(record)
    if limit is not None:
        entries = entries[:limit]

    for index, record in enumerate(entries, start=1):
        day = ctx["TODAY"] - timedelta(days=int(record["day_offset"]))
        argv = [
            str(CLI), "add",
            "--activity", record["activity"],
            "--competency", record["competency"],
            "--statement", record["statement"],
            "--date", day.isoformat(),
            "--agent", record.get("agent", "valor-ambient"),
        ]
        for flag in ("status", "role", "value"):
            if record.get(flag):
                argv += [f"--{flag}", record[flag]]
        if record.get("ai_tier"):
            argv += ["--ai-tier", record["ai_tier"]]
        run(argv, home)
        if index % 10 == 0:
            print(f"  evidence: {index}/{len(entries)}")
    print(f"  evidence: {len(entries)} entries over the last {CYCLE_DAYS} days")
    return len(entries)


def seed_weekly_summaries(home: Path, ctx: dict) -> None:
    """A few past weekly reflections, so /valor-prep and /valor-reflection have
    prior summaries to build on rather than starting from an empty table."""
    weeks = [
        (
            1,
            {"subject_matter": 6, "collaboration": 4, "autonomy_scope": 3, "leadership": 2,
             "industry_knowledge": 0},
            ["No industry-knowledge signal this week", "All reviews were inside my own tickets"],
            "Shipped the error-code logging and wrote the retry contract down. The contract "
            "landed after the code again - Sam's point from the 1:1 stands.",
        ),
        (
            2,
            {"subject_matter": 5, "collaboration": 5, "autonomy_scope": 2, "leadership": 3,
             "industry_knowledge": 1},
            ["Refund fix slipped a week"],
            "The cross-team review on the platform transport skeleton changed their design "
            "before it was built. Strongest signal of the cycle so far.",
        ),
        (
            3,
            {"subject_matter": 7, "collaboration": 2, "autonomy_scope": 4, "leadership": 2,
             "industry_knowledge": 0},
            ["Heads-down week, little cross-team contact"],
            "On-call week: provider degradation handled, workaround replaced with a real "
            "ticket instead of being left in.",
        ),
    ]
    for weeks_ago, summary, gaps, narrative in weeks:
        start = ctx["MONDAY"] - timedelta(days=7 * weeks_ago)
        run([
            str(CLI), "weekly-summary-save",
            "--week-start", start.isoformat(),
            "--week-end", (start + timedelta(days=6)).isoformat(),
            "--summary", json.dumps(summary),
            "--gaps", json.dumps(gaps),
            "--narrative", narrative,
        ], home)
    print(f"  weekly summaries: {len(weeks)}")


def seed_claims(home: Path) -> None:
    """Two open claims, so the verification gate has something real to check on
    the first briefing instead of an empty worklist."""
    claims = [
        ([
            str(VERIFY), "register",
            "--type", "github_pr",
            "--id", "example-org/checkout-service#418",
            "--assert-state", "open, one review round answered, needs a rollback note",
        ], "github_pr #418"),
        ([
            str(VERIFY), "register",
            "--type", "slack",
            "--id", "<#checkout>: rate-limit date from the provider",
            "--assert-state", "not sent",
            "--recipe", json.dumps({
                "channel": "#checkout",
                "keywords": "provider rate limit date",
                "drafted_at": "yesterday",
            }),
        ], "slack follow-up (asserted 'not sent')"),
    ]
    for argv, label in claims:
        if run(argv, home, tolerate=True):
            print(f"  claim registered: {label}")


def render_fixtures(valor: Path, ctx: dict) -> list[str]:
    demo_dir = valor / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for path in sorted(FIXTURES_DIR.iterdir()):
        if not path.is_file():
            continue
        body = render(path.read_text(), ctx)
        if path.name in SPECIAL_FIXTURES:
            continue
        (demo_dir / path.name).write_text(body)
        written.append(path.name)
    print(f"  fixtures: {len(written)} -> {demo_dir}")
    return written


def write_carry_forward(valor: Path, ctx: dict) -> None:
    """Yesterday's carry-forward, so the first briefing has something to carry
    (and something for the verification gate to check)."""
    source = FIXTURES_DIR / "carry_forward.md"
    if not source.exists():
        return
    yesterday = ctx["TODAY"] - timedelta(days=1)
    out_dir = valor / "carry-forward"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"carry-forward-{yesterday.isoformat()}.md"
    out.write_text(render(source.read_text(), ctx))
    print(f"  carry-forward: {out.name}")


def install_demo_block(home: Path, ctx: dict) -> None:
    """Append (or refresh) the demo-mode instructions in the demo home's
    CLAUDE.md. Idempotent: the block is replaced, never duplicated."""
    block = render(DEMO_MODE_FILE.read_text().strip(), ctx)
    payload = f"{DEMO_BEGIN}\n{block}\n{DEMO_END}\n"
    claude_md = home / ".claude" / "CLAUDE.md"
    claude_md.parent.mkdir(parents=True, exist_ok=True)

    existing = claude_md.read_text() if claude_md.exists() else ""
    if DEMO_BEGIN in existing and DEMO_END in existing:
        head, _, rest = existing.partition(DEMO_BEGIN)
        _, _, tail = rest.partition(DEMO_END)
        claude_md.write_text(head.rstrip("\n") + "\n\n" + payload + tail.lstrip("\n"))
        print("  demo-mode block: refreshed in .claude/CLAUDE.md")
    else:
        prefix = existing.rstrip("\n") + "\n\n" if existing.strip() else ""
        claude_md.write_text(prefix + payload)
        print("  demo-mode block: added to .claude/CLAUDE.md")

    if VALOR_RULE_MARKER not in existing:
        print(
            "  ! Valor's own rule is not in that CLAUDE.md yet. Run the installer\n"
            f"    against this home first, then re-run with --force:\n"
            f"      HOME={home} bash {REPO / 'install.sh'}"
        )


# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed the Valor demo profile into a throwaway HOME."
    )
    parser.add_argument("home", help="demo home directory, e.g. ~/valor-demo")
    parser.add_argument("--date", help="pin the demo's 'today' (YYYY-MM-DD); defaults to today")
    parser.add_argument("--force", action="store_true", help="re-seed over an existing profile")
    parser.add_argument(
        "--max-evidence", type=int, default=None,
        help="seed only the first N evidence entries (used by the test suite)",
    )
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    ctx = build_context(today)
    home = resolve_target(args.home, args.force)
    valor = home / ".valor"

    if args.force and valor.exists():
        for stale in ("evidence.sqlite", "state.json", "career_framework.md"):
            (valor / stale).unlink(missing_ok=True)
        shutil.rmtree(valor / "demo", ignore_errors=True)
        shutil.rmtree(valor / "carry-forward", ignore_errors=True)

    valor.mkdir(parents=True, exist_ok=True)
    print(f"Seeding the Valor demo profile into {home} (demo day: {today})")

    write_framework(valor)
    write_state(valor, ctx)
    run([str(CLI), "state-migrate"], home)
    seed_evidence(home, ctx, args.max_evidence)
    seed_weekly_summaries(home, ctx)
    seed_claims(home)
    render_fixtures(valor, ctx)
    write_carry_forward(valor, ctx)
    install_demo_block(home, ctx)

    print(
        "\nDone. Start the demo with:\n"
        f"  HOME={home} claude\n"
        "Then follow examples/demo/DEMO.md. Teardown is: rm -rf " + str(home)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
