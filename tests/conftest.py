import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    """Monkeypatches DB_PATH, BACKUP_DIR, and VALOR_HOME in evidence_cli to use tmp dirs."""
    import src.evidence_cli as cli_module
    db_path = tmp_path / "cli_test.sqlite"
    backup_dir = tmp_path / "backups"
    valor_home = tmp_path / ".valor"
    valor_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cli_module, "DB_PATH", db_path)
    monkeypatch.setattr(cli_module, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(cli_module, "VALOR_HOME", valor_home)
    return db_path, backup_dir
