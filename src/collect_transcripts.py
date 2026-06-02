#!/usr/bin/env python3
"""Discover Cursor agent transcripts across all workspaces, filtered by date.

Used by the evening wrap-up to find all sessions from the current day,
regardless of which workspace they ran in.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER_QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)

_MAX_JSONL_SCAN_LINES = 50
_MAX_TXT_READ_BYTES = 50 * 1024


def _find_transcript_dirs() -> list[tuple[str, Path, str]]:
    """Return (workspace_name, transcripts_dir, source) tuples.

    Scans both Cursor and Claude Code project directories:
    - Cursor: ~/.cursor/projects/*/agent-transcripts/
    - Claude Code: ~/.claude/projects/*/ (transcripts stored directly)
    """
    results: list[tuple[str, Path, str]] = []

    cursor_projects = Path.home() / ".cursor" / "projects"
    if cursor_projects.exists():
        for project_dir in sorted(cursor_projects.iterdir()):
            if not project_dir.is_dir():
                continue
            transcripts = project_dir / "agent-transcripts"
            if transcripts.is_dir():
                workspace = _workspace_label(project_dir.name)
                results.append((workspace, transcripts, "cursor"))

    claude_projects = Path.home() / ".claude" / "projects"
    if claude_projects.exists():
        for project_dir in sorted(claude_projects.iterdir()):
            if not project_dir.is_dir():
                continue
            workspace = _workspace_label(project_dir.name.lstrip("-"))
            results.append((workspace, project_dir, "claude-code"))

    return results


def _workspace_label(folder_name: str) -> str:
    """Convert 'Users-yihan-zhu-git-blocklist' -> 'git/blocklist'."""
    parts = folder_name.split("-")
    try:
        home_idx = next(
            i for i, p in enumerate(parts)
            if p in ("Users", "var", "home")
        )
        skip = 3 if parts[home_idx] == "Users" else 2
        remainder = parts[home_idx + skip:]
    except StopIteration:
        remainder = parts
    if not remainder:
        return folder_name
    return "/".join(remainder)


def _collect_files(transcripts_dir: Path, cutoff: datetime) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.jsonl", "*.txt"):
        for p in transcripts_dir.rglob(pattern):
            if p.is_file() and p.stat().st_mtime >= cutoff.timestamp():
                files.append(p)
    return files


def _extract_query_jsonl(path: Path) -> str | None:
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= _MAX_JSONL_SCAN_LINES:
                break
            line = line.strip()
            if not line or "<user_query>" not in line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            found = _search_for_query(obj)
            if found:
                return found
    return None


def _search_for_query(obj: object) -> str | None:
    if isinstance(obj, dict):
        for v in obj.values():
            found = _search_for_query(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _search_for_query(item)
            if found:
                return found
    elif isinstance(obj, str) and "<user_query>" in obj:
        m = USER_QUERY_RE.search(obj)
        if m:
            return m.group(1).strip()
    return None


def _extract_query_txt(path: Path) -> str | None:
    with open(path, encoding="utf-8", errors="replace") as f:
        head = f.read(_MAX_TXT_READ_BYTES)
    m = USER_QUERY_RE.search(head)
    return m.group(1).strip() if m else None


def _first_n_words(text: str, n: int = 10) -> str:
    words = text.split()
    return " ".join(words[:n]) if words else "(untitled)"


def _process_file(path: Path, workspace: str, source: str) -> dict | None:
    suffix = path.suffix.lower()
    try:
        if suffix == ".jsonl":
            query = _extract_query_jsonl(path)
        elif suffix == ".txt":
            query = _extract_query_txt(path)
        else:
            return None
    except OSError:
        return None

    uuid = path.stem
    if path.parent.name == path.stem and len(path.parts) >= 2:
        uuid = path.parent.name

    stat = path.stat()
    mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone()
    mtime_iso = mtime_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    if len(mtime_iso) > 5 and mtime_iso[-5] in "+-":
        mtime_iso = mtime_iso[:-2] + ":" + mtime_iso[-2:]

    return {
        "uuid": uuid,
        "workspace": workspace,
        "source": source,
        "title": _first_n_words(query, 10) if query else "(untitled)",
        "query_preview": (query[:300] + "...") if query and len(query) > 300 else (query or ""),
        "mtime": mtime_iso,
        "file": str(path),
        "size_kb": round(stat.st_size / 1024),
    }


def collect(days: int) -> list[dict]:
    now = datetime.now().astimezone()
    cutoff = now - timedelta(days=days)

    seen: set[tuple[str, str]] = set()
    records: list[dict] = []

    for workspace, transcripts_dir, source in _find_transcript_dirs():
        for path in _collect_files(transcripts_dir, cutoff):
            rec = _process_file(path, workspace, source)
            if not rec:
                continue
            key = (rec["uuid"], rec["mtime"])
            if key not in seen:
                seen.add(key)
                records.append(rec)

    records.sort(key=lambda r: r["mtime"], reverse=True)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover Cursor agent transcripts across all workspaces."
    )
    parser.add_argument(
        "--days", type=int, default=1,
        help="How many days back to look (default: 1 = today only)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON array",
    )
    args = parser.parse_args()

    records = collect(args.days)

    if args.json:
        print(json.dumps(records, indent=2))
    else:
        if not records:
            print("No transcripts found.")
            return 0
        for r in records:
            print(
                f'[{r["mtime"]}] [{r["source"]}] [{r["workspace"]}] '
                f'"{r["title"]}" (uuid: {r["uuid"][:8]}, {r["size_kb"]} KB)'
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
