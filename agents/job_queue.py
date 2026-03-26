"""Job queue — SQLite-backed queue for pipeline jobs."""

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
    """Create the jobs table if it doesn't exist."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                content_type TEXT DEFAULT 'guide',
                priority TEXT DEFAULT 'medium',
                instructions TEXT DEFAULT '',
                status TEXT DEFAULT 'queued',
                run_id INTEGER,
                pr_url TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                scheduled_for TEXT
            )
        """)


def add_job(topic: str, content_type: str = "guide", priority: str = "medium",
            instructions: str = "", scheduled_for: str = None) -> int:
    """Add a job to the queue. Returns the job ID."""
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (topic, content_type, priority, instructions, status, created_at, scheduled_for) "
            "VALUES (?, ?, ?, ?, 'queued', ?, ?)",
            (topic, content_type, priority, instructions,
             datetime.now(timezone.utc).isoformat(), scheduled_for),
        )
        return cur.lastrowid


def add_batch(jobs: list[dict]) -> list[int]:
    """Add multiple jobs at once. Returns list of job IDs."""
    ids = []
    for j in jobs:
        job_id = add_job(
            topic=j.get("topic", ""),
            content_type=j.get("content_type", "guide"),
            priority=j.get("priority", "medium"),
            instructions=j.get("instructions", ""),
            scheduled_for=j.get("scheduled_for"),
        )
        ids.append(job_id)
    return ids


def get_next_jobs(limit: int = 5) -> list[dict]:
    """Get next queued jobs, ordered by priority then creation time.
    Only returns jobs that are due (scheduled_for is null or in the past)."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM jobs WHERE status = 'queued'
               AND (scheduled_for IS NULL OR scheduled_for <= ?)
               ORDER BY
                 CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                 created_at
               LIMIT ?""",
            (now, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def start_job(job_id: int):
    """Mark a job as running."""
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), job_id),
        )


def finish_job(job_id: int, status: str, pr_url: str = None, error: str = None, run_id: int = None):
    """Mark a job as finished."""
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, pr_url = ?, error = ?, run_id = ?, finished_at = ? WHERE id = ?",
            (status, pr_url, error, run_id,
             datetime.now(timezone.utc).isoformat(), job_id),
        )


def get_all_jobs(limit: int = 50) -> list[dict]:
    """Get all jobs, newest first."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_queue_stats() -> dict:
    """Get queue statistics."""
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        queued = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'queued'").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running'").fetchone()[0]
        published = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'published'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('failed', 'review_failed')").fetchone()[0]
        return {"total": total, "queued": queued, "running": running, "published": published, "failed": failed}


# Auto-init
init()
