import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    """Monkeypatches DB_PATH and BACKUP_DIR in evidence_cli to use tmp dirs."""
    import src.evidence_cli as cli_module
    db_path = tmp_path / "cli_test.sqlite"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(cli_module, "DB_PATH", db_path)
    monkeypatch.setattr(cli_module, "BACKUP_DIR", backup_dir)
    return db_path, backup_dir
