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

    return {
        "generated_by": "examples/demo/build_transcripts.py",
        "captured_from": "examples/demo — a seeded profile with fictional data",
        "captured_on": CAPTURED_ON,
        "valor_version": (REPO / "VERSION").read_text().strip(),
        "acts": list(ACT_ORDER),
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
