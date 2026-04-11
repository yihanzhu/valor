from pathlib import Path


def test_wrapup_carry_forward_stays_under_valor_home():
    text = Path("commands/valor-wrapup.md").read_text()
    assert "~/.valor/carry-forward/" in text
    assert ".claude/memories" not in text
    assert "MEMORY.md" not in text


def test_weekly_reflection_uses_explicit_week_window():
    text = Path("commands/valor-weekly.md").read_text()
    assert "reflection_week_start" in text
    assert "reflection_week_end_exclusive" in text
    assert "previous ISO week" in text
