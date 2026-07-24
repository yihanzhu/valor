"""Every shipped example framework must pass the repo's own framework-validate.

Self-contained: copies each example into a temp VALOR_HOME (via the `cli_db`
fixture, which monkeypatches src.evidence_cli.VALOR_HOME) and runs the real
validator. Does not touch the user's installed ~/.valor.
"""
import argparse
import json
from pathlib import Path

import pytest

from src.evidence_cli import TEMPLATE_MARKER, cmd_framework_validate

EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "frameworks"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.md"))


def test_examples_directory_is_populated():
    # Guard against the glob silently matching nothing (which would make the
    # parametrized test below vacuously pass).
    assert len(EXAMPLE_FILES) >= 2, f"expected >=2 example frameworks in {EXAMPLES_DIR}"


@pytest.mark.parametrize("example", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_framework_passes_validate(example, cli_db, capsys):
    db_path, _ = cli_db
    valor_home = db_path.parent / ".valor"
    content = example.read_text()

    # Must not trip the "still unedited template" sentinel.
    assert TEMPLATE_MARKER not in content, f"{example.name} contains the template marker"

    (valor_home / "career_framework.md").write_text(content)
    cmd_framework_validate(argparse.Namespace())

    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is True, f"{example.name} failed validate: {result['errors']}"
    assert result["errors"] == []
    # Each example ships a real ladder, so it should carry the recommended
    # minimum of three level headings (no "too few levels" warning).
    assert len(result["levels_found"]) >= 3, f"{example.name}: {result['levels_found']}"
