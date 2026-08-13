#!/usr/bin/env python3
"""Build the website's replay transcripts from the committed capture files.

The captures in `captures/` are the editable source of truth: one file per
workflow, each a short front-matter block plus the output that command produced
against the seeded demo profile. This script folds them into the single JSON the
demo page fetches, so the page never carries hand-written "example output".

    python3 examples/demo/build_transcripts.py

Re-capturing: replace a file in `captures/`, bump CAPTURED_ON if the run date
changed, re-run this, and commit both. CI asserts the JSON matches the captures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CAPTURES = HERE / "captures"
OUT = REPO / "website" / "demo" / "transcripts.json"

# The demo day these captures were recorded against. The profile's fixtures are
# seeded relative to the run date, so the transcripts are internally consistent
# with this one date.
CAPTURED_ON = "2026-08-13"

REQUIRED = ("id", "command", "phrase", "label", "act", "blurb")
# Act order on the page — a narrative, not the file order.
ACT_ORDER = ("A day", "A week", "A review cycle", "Setup")

# How the demo page threads the transcripts into something that behaves like a
# session: which inputs it offers at the start, and what it offers next after
# each one. Flow config rather than capture content, so it lives here instead of
# being smeared across eighteen front-matter blocks.
#
# `tools` are the steps that genuinely ran during the capture. A `fixture:` entry
# is the demo profile standing in for an integration — shown rather than hidden,
# because the page's whole claim is that it isn't pretending to be live.
SESSION = {
    "briefing": {
        "start": True,
        "tools": [
            "python3 ~/.valor/evidence_cli.py context",
            "python3 ~/.valor/verify.py reconcile",
            "python3 ~/.valor/focus.py resolve",
            "python3 ~/.valor/plan.py fit",
            "fixture: jira.json · github.json · calendar.json · news.json",
        ],
        "suggests": ["why-first", "ambient", "pr-review", "wrapup"],
    },
    "why-first": {
        "tools": [],
        "suggests": ["ambient", "pr-review", "evidence-stats"],
    },
    "ambient": {
        "tools": ["python3 ~/.valor/evidence_cli.py add --activity code_written"],
        "suggests": ["pr-review", "evidence-stats", "quiet"],
    },
    "pr-review": {
        "tools": [
            "python3 ~/.valor/evidence_cli.py add --activity pr_review_own_scope",
            "fixture: pr_meta.json · pr_diff.diff",
        ],
        "suggests": ["pr-console", "design-doc", "wrapup"],
    },
    "pr-console": {
        "tools": [
            "Workflow: generate.js — analyze → graph → quiz → verify",
            "python3 ~/.valor/pr-console/assemble.py",
            "Artifact: publish",
            "fixture: pr_meta.json · pr_diff.diff",
        ],
        "suggests": ["console-gate", "design-doc", "sync-prep"],
    },
    "console-gate": {
        "tools": [],
        "suggests": ["sync-prep", "wrapup"],
    },
    "design-doc": {
        "tools": ["python3 ~/.valor/evidence_cli.py add --activity design_doc_written"],
        "suggests": ["wrapup", "sync-prep"],
    },
    "wrapup": {
        "start": True,
        "tools": [
            "git log --since=midnight",
            "python3 ~/.valor/evidence_cli.py list --days 1",
            "python3 ~/.valor/verify.py reconcile",
            "python3 ~/.valor/verify.py carry-write",
            "fixture: calendar.json · meeting_notes.md · git_activity.txt",
        ],
        "suggests": ["carry-file", "prep", "weekly"],
    },
    "carry-file": {
        "tools": ["cat ~/.valor/carry-forward/carry-forward-2026-08-13.md"],
        "suggests": ["prep", "weekly", "reflection"],
    },
    "sync-prep": {
        "tools": [
            "python3 ~/.valor/focus.py resolve",
            "python3 ~/.valor/evidence_cli.py list --days 7",
            "fixture: jira.json · github.json · meeting_notes.md",
        ],
        "suggests": ["prep", "weekly"],
    },
    "prep": {
        "tools": [
            "python3 ~/.valor/evidence_cli.py list --days 7",
            "python3 ~/.valor/evidence_cli.py weekly-summary-list --limit 4",
            "python3 ~/.valor/evidence_cli.py framework-slice",
            "fixture: one_on_one_doc.md · calendar.json",
        ],
        "suggests": ["weekly", "reflection"],
    },
    "weekly": {
        "tools": [
            "python3 ~/.valor/evidence_cli.py list --from 2026-08-10 --to 2026-08-14",
            "python3 ~/.valor/evidence_cli.py weekly-summary-save",
            "fixture: jira.json · github.json",
        ],
        "suggests": ["reflection", "prep"],
    },
    "reflection": {
        "start": True,
        "tools": [
            "python3 ~/.valor/evidence_cli.py export --from 2026-02-12 --to 2026-08-13",
            "python3 ~/.valor/collect_transcripts.py",
            "git log --author=alex",
            "fixture: github.json · jira.json",
        ],
        "suggests": ["upward-feedback", "evidence-stats"],
    },
    "upward-feedback": {
        "tools": [
            'python3 ~/.valor/evidence_cli.py search "meeting_notes"',
            "fixture: meeting_notes.md · one_on_one_doc.md",
        ],
        "suggests": ["setup", "evidence-stats"],
    },
    "evidence-stats": {
        "tools": ["python3 ~/.valor/evidence_cli.py stats"],
        "suggests": ["reflection", "briefing", "quiet"],
    },
    "setup": {
        "start": True,
        "tools": [
            "python3 ~/.valor/evidence_cli.py framework-validate",
            "python3 ~/.valor/evidence_cli.py state-set current_level M2",
        ],
        "suggests": ["no-integrations", "briefing"],
    },
    "no-integrations": {
        "tools": [],
        "suggests": ["briefing", "quiet"],
    },
    "quiet": {
        "tools": [],
        "suggests": ["briefing", "reflection"],
    },
}


def parse(path: Path) -> dict:
    """Parse a capture: `key: value` lines, a lone `---`, then the output."""
    raw = path.read_text()
    if "\n---\n" not in raw:
        sys.exit(f"{path.name}: missing the '---' separator between front matter and output")
    head, _, body = raw.partition("\n---\n")

    entry = {}
    for line in head.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            sys.exit(f"{path.name}: front-matter line is not 'key: value': {line!r}")
        entry[key.strip()] = value.strip()

    missing = [k for k in REQUIRED if not entry.get(k)]
    if missing:
        sys.exit(f"{path.name}: front matter missing {missing}")
    if entry["act"] not in ACT_ORDER:
        sys.exit(f"{path.name}: act {entry['act']!r} is not one of {list(ACT_ORDER)}")

    entry["output"] = body.rstrip("\n")
    if not entry["output"].strip():
        sys.exit(f"{path.name}: no output captured")
    return entry


def build() -> dict:
    files = sorted(CAPTURES.glob("*.md"))
    if not files:
        sys.exit(f"no captures found in {CAPTURES}")
    entries = [parse(p) for p in files]

    ids = [e["id"] for e in entries]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        sys.exit(f"duplicate capture ids: {sorted(duplicates)}")

    known = set(ids)
    unknown = set(SESSION) - known
    if unknown:
        sys.exit(f"SESSION references ids with no capture file: {sorted(unknown)}")
    missing = known - set(SESSION)
    if missing:
        sys.exit(f"captures with no SESSION entry (unreachable on the page): {sorted(missing)}")

    starts = []
    for entry in entries:
        flow = SESSION[entry["id"]]
        bad = [s for s in flow.get("suggests", []) if s not in known]
        if bad:
            sys.exit(f"{entry['id']}: suggests unknown ids {bad}")
        entry["tools"] = list(flow.get("tools", []))
        entry["suggests"] = list(flow.get("suggests", []))
        if flow.get("start"):
            starts.append(entry["id"])

    if not starts:
        sys.exit("no capture is marked as a session start")

    reachable = set(starts)
    frontier = list(starts)
    while frontier:
        for nxt in SESSION[frontier.pop()].get("suggests", []):
            if nxt not in reachable:
                reachable.add(nxt)
                frontier.append(nxt)
    orphans = known - reachable
    if orphans:
        sys.exit(f"unreachable from any start — nothing offers these: {sorted(orphans)}")

    return {
        "generated_by": "examples/demo/build_transcripts.py",
        "captured_from": "examples/demo — a seeded profile with fictional data",
        "captured_on": CAPTURED_ON,
        "valor_version": (REPO / "VERSION").read_text().strip(),
        "acts": list(ACT_ORDER),
        "start": starts,
        "entries": entries,
    }


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT, help="where to write the JSON")
    parser.add_argument(
        "--check", action="store_true",
        help="don't write; exit 1 if the existing file is out of date (used by CI)",
    )
    args = parser.parse_args()

    payload = render(build())
    if args.check:
        existing = args.out.read_text() if args.out.exists() else ""
        if existing != payload:
            print(
                f"{args.out} is out of date — run: python3 examples/demo/build_transcripts.py"
            )
            return 1
        print(f"transcripts: OK (in sync with {CAPTURES.name}/)")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload)
    print(f"wrote {args.out} — {len(build()['entries'])} transcripts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
