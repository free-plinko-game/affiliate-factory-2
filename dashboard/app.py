"""Agent Office Dashboard — watch your agents work like office employees."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

STATE_FILE = Path(__file__).parent / "state.json"
DB_PATH = Path(__file__).parent / "pipeline.db"

DEFAULT_STATE = {
    "pipeline_running": False,
    "current_topic": None,
    "agents": {
        "manager_agent": {
            "name": "Max",
            "title": "Manager (COO)",
            "status": "idle",
            "speech": "Office is quiet. Submit a brief to get things moving.",
            "emoji": "👔",
        },
        "seo_agent": {
            "name": "Sarah",
            "title": "SEO Specialist",
            "status": "idle",
            "speech": "Waiting for a keyword to research...",
            "emoji": "🔍",
        },
        "writer_agent": {
            "name": "Will",
            "title": "Content Writer",
            "status": "idle",
            "speech": "Ready to write when you are.",
            "emoji": "✍️",
        },
        "editor_agent": {
            "name": "Emma",
            "title": "Editor",
            "status": "idle",
            "speech": "No drafts to review right now.",
            "emoji": "📝",
        },
        "sub_editor_agent": {
            "name": "Sam",
            "title": "Sub-Editor",
            "status": "idle",
            "speech": "Standing by for fixes.",
            "emoji": "🔧",
        },
        "compliance_agent": {
            "name": "Clara",
            "title": "Compliance Officer",
            "status": "idle",
            "speech": "All quiet on the compliance front.",
            "emoji": "📋",
        },
        "publisher_agent": {
            "name": "Pete",
            "title": "Publisher",
            "status": "idle",
            "speech": "No PRs to push right now.",
            "emoji": "🚀",
        },
    },
    "activity_log": [],
    "runs": [],
}


def read_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return json.loads(json.dumps(DEFAULT_STATE))


def write_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


if not STATE_FILE.exists():
    write_state(DEFAULT_STATE)


def get_db_runs(limit=20):
    """Get recent runs from SQLite."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_db_run(run_id):
    """Get a single run with steps."""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        conn.close()
        return None
    steps = conn.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    conn.close()
    result = dict(run)
    result["steps"] = [dict(s) for s in steps]
    return result


@app.route("/")
def index():
    state = read_state()
    return render_template("office.html", state=state)


@app.route("/api/state")
def api_state():
    return jsonify(read_state())


@app.route("/api/runs")
def api_runs():
    return jsonify(get_db_runs())


@app.route("/api/runs/<int:run_id>")
def api_run(run_id):
    run = get_db_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    return jsonify(run)


@app.route("/api/update", methods=["POST"])
def api_update():
    """Called by the pipeline to update agent status."""
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no data"}), 400
    state = read_state()

    agent = data.get("agent")
    if agent and agent in state["agents"]:
        if "status" in data:
            state["agents"][agent]["status"] = data["status"]
        if "speech" in data:
            state["agents"][agent]["speech"] = data["speech"]
        if "thought" in data:
            state["agents"][agent].setdefault("thoughts", []).insert(0, {
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "text": data["thought"],
            })
            state["agents"][agent]["thoughts"] = state["agents"][agent]["thoughts"][:30]
        if "clear_thoughts" in data:
            state["agents"][agent]["thoughts"] = []

    if "pipeline_running" in data:
        state["pipeline_running"] = data["pipeline_running"]
    if "current_topic" in data:
        state["current_topic"] = data["current_topic"]

    if "log" in data:
        entry = {
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "agent": data.get("agent", "system"),
            "message": data["log"],
        }
        state.setdefault("activity_log", []).insert(0, entry)
        state["activity_log"] = state["activity_log"][:50]

    if "run_complete" in data:
        state.setdefault("runs", []).insert(0, data["run_complete"])
        state["runs"] = state["runs"][:20]

    write_state(state)
    return jsonify({"ok": True})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat with an agent — processes feedback and updates their knowledge base."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

    data = request.get_json(force=True)
    agent_key = data.get("agent")
    message = data.get("message", "")

    if not agent_key or not message:
        return jsonify({"error": "agent and message required"}), 400

    try:
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            return jsonify({"error": "OPENAI_API_KEY not set on server"}), 500

        import chat_handler
        result = chat_handler.chat(agent_key, message)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/history/<agent_key>")
def api_chat_history(agent_key):
    """Get chat history for an agent."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import chat_handler
    history = chat_handler.get_history(agent_key)
    return jsonify(history)


@app.route("/api/threads")
def api_threads():
    """Get active agent-to-agent threads."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import agent_chat
    return jsonify(agent_chat.get_active_threads())


@app.route("/api/threads/<thread_id>")
def api_thread(thread_id):
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import agent_chat
    thread = agent_chat.get_thread(thread_id)
    if not thread:
        return jsonify({"error": "not found"}), 404
    return jsonify(thread)


@app.route("/api/threads/<thread_id>/reply", methods=["POST"])
def api_thread_reply(thread_id):
    """Founder replies in a thread."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import agent_chat

    data = request.get_json(force=True)
    message = data.get("message", "")
    if not message:
        return jsonify({"error": "message required"}), 400

    agent_chat.founder_says(thread_id, message)

    # Let the agents respond to the founder
    thread = agent_chat.get_thread(thread_id)
    if thread:
        for p in thread["participants"]:
            import os
            if os.environ.get("OPENAI_API_KEY"):
                agent_chat.agent_says(thread_id, p)

    return jsonify(agent_chat.get_thread(thread_id))


@app.route("/api/brief", methods=["POST"])
def api_brief():
    """Submit a brief — Manager parses it into jobs, then worker processes them."""
    import sys, os, threading
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

    if not os.environ.get("OPENAI_API_KEY"):
        return jsonify({"error": "OPENAI_API_KEY not set"}), 500

    data = request.get_json(force=True)
    brief_text = data.get("brief", "")
    if not brief_text:
        return jsonify({"error": "brief required"}), 400

    import manager_agent
    import job_queue
    from config import load_site_config

    site_config = load_site_config()

    # Manager parses the brief into jobs
    state = read_state()
    state["pipeline_running"] = True
    state["current_topic"] = brief_text[:80]
    if "manager_agent" in state["agents"]:
        state["agents"]["manager_agent"]["status"] = "working"
        state["agents"]["manager_agent"]["speech"] = "Reading the brief..."
    write_state(state)

    result = manager_agent.run(brief_text, site_config)
    jobs = result.get("jobs", [])

    # Add to queue
    job_ids = job_queue.add_batch(jobs)

    # Update dashboard
    state = read_state()
    if "manager_agent" in state["agents"]:
        state["agents"]["manager_agent"]["status"] = "success"
        state["agents"]["manager_agent"]["speech"] = f"{len(jobs)} job(s) queued!"
    entry = {
        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "agent": "manager_agent",
        "message": f"Queued {len(jobs)} jobs from brief",
    }
    state.setdefault("activity_log", []).insert(0, entry)
    write_state(state)

    # Run worker in background thread
    def run_worker():
        import worker
        worker.run_queue()

    threading.Thread(target=run_worker, daemon=True).start()

    return jsonify({
        "interpretation": result.get("interpretation", ""),
        "jobs": len(jobs),
        "job_ids": job_ids,
        "flags": result.get("flags", []),
    })


@app.route("/api/queue")
def api_queue():
    """Get queue stats and jobs."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import job_queue
    return jsonify({
        "stats": job_queue.get_queue_stats(),
        "jobs": job_queue.get_all_jobs(limit=30),
    })


@app.route("/api/schedules")
def api_schedules():
    """Get all schedules."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import scheduler
    return jsonify(scheduler.load_schedules())


@app.route("/api/schedules", methods=["POST"])
def api_add_schedule():
    """Add a recurring schedule."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import scheduler
    data = request.get_json(force=True)
    s = scheduler.add_schedule(
        brief=data.get("brief", ""),
        frequency=data.get("frequency", "weekly"),
        day=data.get("day", "monday"),
    )
    return jsonify(s)


@app.route("/api/schedules/<int:sid>", methods=["DELETE"])
def api_delete_schedule(sid):
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import scheduler
    scheduler.remove_schedule(sid)
    return jsonify({"ok": True})


@app.route("/api/knowledge/<agent_key>")
def api_knowledge(agent_key):
    """Get an agent's knowledge base."""
    kb_path = Path(__file__).parent.parent / "agents" / "knowledge" / f"{agent_key}.md"
    if kb_path.exists():
        return jsonify({"agent": agent_key, "knowledge": kb_path.read_text()})
    return jsonify({"agent": agent_key, "knowledge": ""})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
