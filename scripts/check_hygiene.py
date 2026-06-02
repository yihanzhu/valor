#!/usr/bin/env python3
"""Company-info hygiene scanner for the public Valor repo.

Valor ships publicly, so committed artifacts must never contain an employer
name, internal Jira project keys, colleague names, or non-placeholder emails.
This script is the mechanical guard that the local git hooks and CI both run.

KEY DESIGN CONSTRAINT: the guard must not become the leak. The list of *exact*
sensitive terms (your org, project keys, names) is therefore NEVER committed.
It is loaded at runtime from out-of-repo sources:

  * a git-ignored local file (default: .hygiene/denylist.local) -- used by the
    local pre-commit / commit-msg hooks;
  * the HYGIENE_DENYLIST env var (one pattern per line) -- in CI this is
    wired to an encrypted GitHub Actions secret.

Each denylist entry is a case-insensitive regex (e.g. `\\bACME-\\d+`, `acme-corp`).
Only generic, placeholder-safe patterns (non-example emails) live in this file.

Output is redacted in CI mode so a matched term is never echoed into the public
Actions log -- it reports file:line and which rule fired, not the text.

Any line containing the marker `hygiene:ignore` is skipped (for legitimate
example/fixture content).

Usage:
    check_hygiene.py --mode staged                  # added lines in the index (pre-commit)
    check_hygiene.py --mode msg --commit-msg-file F  # a commit message (commit-msg)
    check_hygiene.py --mode ci                       # all tracked files; redacted output
    check_hygiene.py --mode tree                     # all tracked files; full output (local)

Exit code 0 = clean, 1 = matches found, 2 = usage/setup error.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

IGNORE_MARKER = "hygiene:ignore"
DEFAULT_DENYLIST = ".hygiene/denylist.local"

# Email domains that are safe to appear in committed files: RFC-2606 reserved
# placeholders, the co-author trailer domain, GitHub no-reply, and the project's
# own canonical domains (project metadata, not a leak).
SAFE_EMAIL_DOMAINS = (
    "example.com", "example.org", "example.net",
    "anthropic.com",
    "github.com", "noreply.github.com", "users.noreply.github.com",
    "yihanzhu.com", "valor.yihanzhu.com",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Paths never scanned (the denylist itself is git-ignored, but be defensive).
SKIP_PREFIXES = (".git/", ".hygiene/denylist.local")


def run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout


def load_exact_patterns(denylist_path: str) -> list[re.Pattern]:
    raw: list[str] = []
    p = Path(denylist_path)
    if p.exists():
        raw += p.read_text(encoding="utf-8", errors="replace").splitlines()
    env = os.environ.get("HYGIENE_DENYLIST", "")
    if env:
        # Split on newlines only (NOT commas): comment lines may contain commas,
        # and splitting on them would turn comment fragments into live patterns.
        raw += env.splitlines()
    patterns: list[re.Pattern] = []
    for line in raw:
        term = line.strip()
        if not term or term.startswith("#"):
            continue
        try:
            patterns.append(re.compile(term, re.IGNORECASE))
        except re.error as exc:
            print(f"warning: skipping invalid denylist pattern {term!r}: {exc}", file=sys.stderr)
    return patterns


def email_is_flagged(match: str) -> bool:
    domain = match.rsplit("@", 1)[-1].lower()
    return not any(domain == d or domain.endswith("." + d) for d in SAFE_EMAIL_DOMAINS)


def scan_line(line: str, exact: list[re.Pattern]) -> list[tuple[str, str]]:
    """Return [(rule_label, matched_text), ...] for a single line."""
    if IGNORE_MARKER in line:
        return []
    hits: list[tuple[str, str]] = []
    for pat in exact:
        m = pat.search(line)
        if m:
            hits.append(("denylist", m.group(0)))
    for m in EMAIL_RE.finditer(line):
        if email_is_flagged(m.group(0)):
            hits.append(("non-placeholder-email", m.group(0)))
    return hits


def iter_staged_added():
    """Yield (path, lineno, text) for added lines in the staged diff."""
    diff = run(["git", "diff", "--cached", "--unified=0", "--no-color"])
    path, new_ln = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:]
            path = target[2:] if target.startswith("b/") else None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_ln = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            if path:
                yield path, new_ln, line[1:]
            new_ln += 1
        elif not line.startswith("-"):
            new_ln += 1


def iter_tracked_files():
    """Yield (path, lineno, text) for every line of every tracked text file."""
    for path in run(["git", "ls-files"]).splitlines():
        if any(path.startswith(pre) or path == pre for pre in SKIP_PREFIXES):
            continue
        try:
            data = Path(path).read_bytes()
        except OSError:
            continue
        if b"\x00" in data:  # binary
            continue
        for i, text in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            yield path, i, text


def redact(text: str) -> str:
    if len(text) <= 2:
        return "*" * len(text)
    return text[0] + "*" * (len(text) - 2) + text[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Company-info hygiene scanner")
    ap.add_argument("--mode", required=True, choices=["staged", "msg", "ci", "tree", "text"])
    ap.add_argument("--denylist", default=DEFAULT_DENYLIST)
    ap.add_argument("--commit-msg-file", default=None)
    ap.add_argument("--input-file", default=None,
                    help="File to scan in --mode text (e.g. a PR title+body)")
    ap.add_argument("--redact", action="store_true",
                    help="Mask matched text (use for CI / public logs)")
    args = ap.parse_args()

    exact = load_exact_patterns(args.denylist)
    redact_out = args.redact or args.mode == "ci"

    findings: list[tuple[str, int, str, str]] = []  # source, lineno, label, text

    if args.mode == "msg":
        if not args.commit_msg_file:
            print("error: --mode msg requires --commit-msg-file", file=sys.stderr)
            return 2
        for i, text in enumerate(Path(args.commit_msg_file).read_text(errors="replace").splitlines(), 1):
            if text.startswith("#"):
                continue
            for label, hit in scan_line(text, exact):
                findings.append(("<commit message>", i, label, hit))
    elif args.mode == "text":
        # Free text (e.g. a PR title+body). Unlike msg mode, '#' lines are NOT
        # skipped — they're markdown headings here, not git comments.
        if not args.input_file:
            print("error: --mode text requires --input-file", file=sys.stderr)
            return 2
        for i, text in enumerate(Path(args.input_file).read_text(errors="replace").splitlines(), 1):
            for label, hit in scan_line(text, exact):
                findings.append((args.input_file, i, label, hit))
    elif args.mode == "staged":
        for path, ln, text in iter_staged_added():
            for label, hit in scan_line(text, exact):
                findings.append((path, ln, label, hit))
    else:  # ci / tree
        for path, ln, text in iter_tracked_files():
            for label, hit in scan_line(text, exact):
                findings.append((path, ln, label, hit))

    if not findings:
        if not exact and redact_out:
            print("hygiene: OK (generic rules only — HYGIENE_DENYLIST secret not set)")
        else:
            print(f"hygiene: OK ({len(exact)} denylist pattern(s) active)")
        return 0

    print(f"\nhygiene: BLOCKED — {len(findings)} potential company-info leak(s):\n", file=sys.stderr)
    for source, ln, label, hit in findings:
        shown = redact(hit) if redact_out else hit
        print(f"  {source}:{ln}  [{label}]  {shown}", file=sys.stderr)
    print(
        "\nThese must not reach the public repo. Fix the content, or if it is a "
        "legitimate placeholder add a `hygiene:ignore` comment on that line.\n"
        "Denylist terms live out-of-repo (.hygiene/denylist.local / HYGIENE_DENYLIST).\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
