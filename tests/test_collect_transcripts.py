from src.collect_transcripts import (
    _find_transcript_dirs,
    _first_n_words,
    _workspace_label,
)


# --- _workspace_label (pure logic) ---

def test_workspace_label_users_skips_three():
    # 'Users-<user>-<...>' drops 'Users' + the next two segments (user dir parts).
    assert _workspace_label("Users-alex-kim-git-myrepo") == "git/myrepo"


def test_workspace_label_var_and_home_skip_two():
    # 'var'/'home' roots drop the root segment + one more, keeping the remainder.
    assert _workspace_label("var-lib-buildkite-checkout") == "buildkite/checkout"
    assert _workspace_label("home-alex-projects-foo") == "projects/foo"


def test_workspace_label_no_known_root_returns_joined():
    # No Users/var/home anchor -> StopIteration path joins every segment.
    assert _workspace_label("noanchor-segment-here") == "noanchor/segment/here"


def test_workspace_label_empty_remainder_falls_back_to_folder_name():
    # When skipping consumes everything, the original folder name is returned.
    assert _workspace_label("Users-alex-kim") == "Users-alex-kim"


# --- _first_n_words (pure logic) ---

def test_first_n_words_truncates():
    assert _first_n_words("one two three four", 2) == "one two"


def test_first_n_words_fewer_than_n():
    assert _first_n_words("only two", 10) == "only two"


def test_first_n_words_empty_is_untitled():
    assert _first_n_words("", 5) == "(untitled)"
    assert _first_n_words("   ", 5) == "(untitled)"


# --- _find_transcript_dirs (filesystem discovery) ---
# Path.home() resolves via $HOME on POSIX, so pointing HOME at a tmp dir lets us
# exercise discovery without touching the real home directory.


def test_find_transcript_dirs_discovers_cursor_and_claude(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    # Cursor: ~/.cursor/projects/<proj>/agent-transcripts/ must exist.
    cursor_proj = tmp_path / ".cursor" / "projects" / "Users-alex-kim-git-myrepo"
    (cursor_proj / "agent-transcripts").mkdir(parents=True)
    # A cursor project WITHOUT agent-transcripts is skipped.
    (tmp_path / ".cursor" / "projects" / "Users-alex-kim-git-empty").mkdir(parents=True)

    # Claude Code: ~/.claude/projects/<proj>/ used directly (leading '-' stripped).
    claude_proj = tmp_path / ".claude" / "projects" / "-Users-alex-kim-git-other"
    claude_proj.mkdir(parents=True)

    results = _find_transcript_dirs()
    by_source = {(src, ws): path for ws, path, src in results}

    assert ("cursor", "git/myrepo") in by_source
    assert by_source[("cursor", "git/myrepo")] == cursor_proj / "agent-transcripts"
    assert ("claude-code", "git/other") in by_source
    assert by_source[("claude-code", "git/other")] == claude_proj
    # The cursor project lacking agent-transcripts contributes nothing.
    assert not any(ws == "git/empty" for ws, _, _ in results)


def test_find_transcript_dirs_skips_non_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    projects = tmp_path / ".cursor" / "projects"
    projects.mkdir(parents=True)
    # A stray file under projects/ must not be treated as a project dir.
    (projects / "stray.txt").write_text("not a project")

    results = _find_transcript_dirs()
    assert results == []


def test_find_transcript_dirs_empty_when_no_roots(tmp_path, monkeypatch):
    # No ~/.cursor or ~/.claude at all -> empty list, no error.
    monkeypatch.setenv("HOME", str(tmp_path))
    assert _find_transcript_dirs() == []
