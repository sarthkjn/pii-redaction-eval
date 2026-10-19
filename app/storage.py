"""Save evaluation runs to SQLite so results can be compared over time.

SQLite ships with Python, so there's no database server to install. Each run is
one row: a few summary columns for quick queries, plus the full report as JSON.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    engine      TEXT    NOT NULL,
    dataset     TEXT    NOT NULL,
    n_samples   INTEGER NOT NULL,
    precision   REAL    NOT NULL,
    recall      REAL    NOT NULL,
    f1          REAL    NOT NULL,
    report_json TEXT    NOT NULL
)
"""


def _connect(db_path: Path | None) -> sqlite3.Connection:
    db_path = Path(db_path or config.DB_PATH)  # resolved at call time so tests can override it
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def save_run(report: dict, db_path: Path | None = None) -> int:
    overall = report["overall"]
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO runs (created_at, engine, dataset, n_samples, precision, recall, f1, report_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                report["engine"],
                report["dataset"],
                report["n_samples"],
                overall["precision"],
                overall["recall"],
                overall["f1"],
                json.dumps(report),
            ),
        )
        return cur.lastrowid


def list_runs(limit: int = 50, db_path: Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, created_at, engine, dataset, n_samples, precision, recall, f1 "
            "FROM runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: int, db_path: Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT report_json FROM runs WHERE id = ?", (run_id,)).fetchone()
    return json.loads(row["report_json"]) if row else None
