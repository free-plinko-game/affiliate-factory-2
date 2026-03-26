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


@app.route("/api/knowledge/<agent_key>")
def api_knowledge(agent_key):
    """Get an agent's knowledge base."""
    kb_path = Path(__file__).parent.parent / "agents" / "knowledge" / f"{agent_key}.md"
    if kb_path.exists():
        return jsonify({"agent": agent_key, "knowledge": kb_path.read_text()})
    return jsonify({"agent": agent_key, "knowledge": ""})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
