"""State foundation — unified database interface for all agent state.

All agents import from here. This is the single source of truth.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "affiliate.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init():
    """Run schema.sql to create all tables."""
    with _conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


# ── Content Register ──────────────────────────────────────

def register_content(site_slug: str, keyword: str, content_type: str = "guide",
                     status: str = "briefed", title: str = None, slug: str = None,
                     run_id: int = None) -> int:
    """Register a new piece of content. Returns the register ID."""
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO content_register
               (site_slug, keyword, content_type, status, title, slug, run_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (site_slug, keyword, content_type, status, title, slug, run_id, _now(), _now()),
        )
        return cur.lastrowid


def update_content_status(register_id: int, status: str, **kwargs):
    """Update a content register entry."""
    with _conn() as conn:
        fields = ["status = ?", "updated_at = ?"]
        values = [status, _now()]
        for key in ["title", "slug", "word_count", "compliance_pass", "pr_url",
                     "published_date", "performance_score", "notes", "run_id"]:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        values.append(register_id)
        conn.execute(f"UPDATE content_register SET {', '.join(fields)} WHERE id = ?", values)


def find_content(site_slug: str, keyword: str = None, status: str = None) -> list[dict]:
    """Search the content register."""
    with _conn() as conn:
        query = "SELECT * FROM content_register WHERE site_slug = ?"
        params = [site_slug]
        if keyword:
            query += " AND keyword LIKE ?"
            params.append(f"%{keyword}%")
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC"
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_all_content(site_slug: str = None, limit: int = 50) -> list[dict]:
    """Get all content register entries."""
    with _conn() as conn:
        if site_slug:
            rows = conn.execute(
                "SELECT * FROM content_register WHERE site_slug = ? ORDER BY updated_at DESC LIMIT ?",
                (site_slug, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM content_register ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def keyword_exists(site_slug: str, keyword: str) -> bool:
    """Check if a keyword has already been briefed/published for a site."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM content_register WHERE site_slug = ? AND keyword LIKE ? AND status != 'refresh_needed'",
            (site_slug, f"%{keyword}%"),
        ).fetchone()
        return row is not None


def get_content_for_agent(site_slug: str) -> str:
    """Get a text summary of existing content for an agent's context."""
    entries = get_all_content(site_slug, limit=100)
    if not entries:
        return "No content published or in progress for this site yet."
    lines = []
    for e in entries:
        lines.append(f"- [{e['status']}] \"{e['keyword']}\" ({e['content_type']}) — {e.get('slug', 'no slug')}")
    return f"Existing content for {site_slug} ({len(entries)} items):\n" + "\n".join(lines)


# ── Agent Learning Log ────────────────────────────────────

def log_learning(agent_name: str, learning_type: str, description: str,
                 site_slug: str = None, source: str = None, severity: str = "info"):
    """Log a learning event for an agent."""
    with _conn() as conn:
        conn.execute(
            """INSERT INTO agent_learnings
               (agent_name, site_slug, learning_type, description, source, severity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_name, site_slug, learning_type, description, source, severity),
        )


def get_learnings(agent_name: str = None, learning_type: str = None,
                  site_slug: str = None, limit: int = 50) -> list[dict]:
    """Query the learning log."""
    with _conn() as conn:
        query = "SELECT * FROM agent_learnings WHERE 1=1"
        params = []
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        if learning_type:
            query += " AND learning_type = ?"
            params.append(learning_type)
        if site_slug:
            query += " AND (site_slug = ? OR site_slug IS NULL)"
            params.append(site_slug)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_learnings_for_agent(agent_name: str, limit: int = 20) -> str:
    """Get a text summary of recent learnings for an agent's context."""
    entries = get_learnings(agent_name=agent_name, limit=limit)
    if not entries:
        return "No learnings recorded yet."
    lines = []
    for e in entries:
        lines.append(f"- [{e['learning_type']}] {e['description']}")
    return f"Recent learnings ({len(entries)} entries):\n" + "\n".join(lines)


# ── Content Calendar ──────────────────────────────────────

def add_to_calendar(site_slug: str, keyword: str, content_type: str = "guide",
                    planned_date: str = None, priority: str = "medium",
                    job_id: int = None) -> int:
    """Add an item to the content calendar."""
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO content_calendar
               (site_slug, keyword, content_type, planned_date, priority, job_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (site_slug, keyword, content_type, planned_date, priority, job_id, _now(), _now()),
        )
        return cur.lastrowid


def update_calendar_status(calendar_id: int, status: str, **kwargs):
    """Update a calendar entry."""
    with _conn() as conn:
        fields = ["status = ?", "updated_at = ?"]
        values = [status, _now()]
        for key in ["assigned_to", "content_register_id", "notes", "job_id"]:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        values.append(calendar_id)
        conn.execute(f"UPDATE content_calendar SET {', '.join(fields)} WHERE id = ?", values)


def get_calendar(site_slug: str = None, status: str = None, limit: int = 50) -> list[dict]:
    """Get calendar entries."""
    with _conn() as conn:
        query = "SELECT * FROM content_calendar WHERE 1=1"
        params = []
        if site_slug:
            query += " AND site_slug = ?"
            params.append(site_slug)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY planned_date ASC, priority ASC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_calendar_for_agent(site_slug: str) -> str:
    """Get a text summary of the content calendar for an agent."""
    entries = get_calendar(site_slug=site_slug, limit=30)
    if not entries:
        return "Content calendar is empty."
    lines = []
    for e in entries:
        date = e.get("planned_date", "unscheduled")
        lines.append(f"- [{e['status']}] \"{e['keyword']}\" ({e['content_type']}) — {date} [{e['priority']}]")
    return f"Content calendar ({len(entries)} items):\n" + "\n".join(lines)


# ── Pipeline Steps (resumability) ─────────────────────────

def create_pipeline_steps(run_id: int, job_id: int, steps: list[tuple]) -> list[int]:
    """Pre-create all pipeline steps for a run. Returns step IDs.

    Args:
        steps: list of (step_name, step_order, agent) tuples
    """
    ids = []
    with _conn() as conn:
        for name, order, agent in steps:
            cur = conn.execute(
                """INSERT INTO pipeline_steps (run_id, job_id, step_name, step_order, agent)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, job_id, name, order, agent),
            )
            ids.append(cur.lastrowid)
    return ids


def start_step(step_id: int, input_payload: dict = None):
    """Mark a step as running."""
    with _conn() as conn:
        conn.execute(
            "UPDATE pipeline_steps SET status = 'running', started_at = ?, input_payload = ? WHERE id = ?",
            (_now(), json.dumps(input_payload) if input_payload else None, step_id),
        )


def finish_step(step_id: int, status: str, output_payload: dict = None, error: str = None):
    """Mark a step as done or failed."""
    with _conn() as conn:
        conn.execute(
            "UPDATE pipeline_steps SET status = ?, finished_at = ?, output_payload = ?, error = ? WHERE id = ?",
            (status, _now(), json.dumps(output_payload) if output_payload else None, error, step_id),
        )


def get_run_steps(run_id: int) -> list[dict]:
    """Get all steps for a run."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM pipeline_steps WHERE run_id = ? ORDER BY step_order", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_last_completed_step(run_id: int) -> dict | None:
    """Get the last successfully completed step for a run (for resumability)."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_steps WHERE run_id = ? AND status = 'done' ORDER BY step_order DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None


def get_next_pending_step(run_id: int) -> dict | None:
    """Get the next step that needs to run."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_steps WHERE run_id = ? AND status = 'pending' ORDER BY step_order LIMIT 1",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None


# Auto-init on import
init()
