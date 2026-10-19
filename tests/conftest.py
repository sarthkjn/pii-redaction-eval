import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.redactor import get_redactor  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test writes to its own throwaway SQLite file, never data/runs.db."""
    db = tmp_path / "test_runs.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    return db


@pytest.fixture(scope="session")
def baseline():
    return get_redactor("baseline")


@pytest.fixture(scope="session")
def improved():
    return get_redactor("improved")
