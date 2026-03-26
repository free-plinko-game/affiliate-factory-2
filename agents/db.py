"""SQLite logging for pipeline runs."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "dashboard" / "pipeline.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init():
    """Create tables if they don't exist."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                status TEXT DEFAULT 'running',
                pr_url TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                brief_text TEXT,
                manager_output TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                agent TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                data TEXT,
                timestamp TEXT NOT NULL
            )
        """)


def start_run(topic: str, brief_text: str = "") -> int:
    """Start a new pipeline run. Returns the run ID."""
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs (topic, status, started_at, brief_text) VALUES (?, 'running', ?, ?)",
            (topic, datetime.now(timezone.utc).isoformat(), brief_text),
        )
        return cur.lastrowid


def log_step(run_id: int, agent: str, step_name: str, status: str, data: dict | None = None):
    """Log a pipeline step."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO steps (run_id, agent, step_name, status, data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, agent, step_name, status, json.dumps(data) if data else None,
             datetime.now(timezone.utc).isoformat()),
        )


def finish_run(run_id: int, status: str, pr_url: str | None = None, manager_output: dict | None = None):
    """Mark a run as finished."""
    with _conn() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, pr_url = ?, finished_at = ?, manager_output = ? WHERE id = ?",
            (status, pr_url, datetime.now(timezone.utc).isoformat(),
             json.dumps(manager_output) if manager_output else None, run_id),
        )


def get_runs(limit: int = 20) -> list[dict]:
    """Get recent runs."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    """Get a single run with its steps."""
    with _conn() as conn:
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            return None
        steps = conn.execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        result = dict(run)
        result["steps"] = [dict(s) for s in steps]
        return result


# Auto-init on import
init()
