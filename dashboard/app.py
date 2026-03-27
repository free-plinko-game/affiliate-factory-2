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
    return jsonify(agent_chat.get_all_threads())


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
        import os
        if os.environ.get("OPENAI_API_KEY"):
            for p in thread["participants"]:
                agent_chat.agent_says(thread_id, p)

            # Check if founder asked agents to loop someone else in
            spawned = _check_spawn_request(message, thread, agent_chat)
            if spawned:
                return jsonify({**agent_chat.get_thread(thread_id), "spawned_thread": spawned})

            # Check if founder asked Max to retry
            retried = _check_retry_request(message, thread)
            if retried:
                return jsonify({**agent_chat.get_thread(thread_id), "retried_job": retried})

    return jsonify(agent_chat.get_thread(thread_id))


# Agent name → key mapping for spawn detection
_AGENT_LOOKUP = {
    "max": "manager_agent", "sarah": "seo_agent", "will": "writer_agent",
    "emma": "editor_agent", "sam": "sub_editor_agent", "clara": "compliance_agent",
    "pete": "publisher_agent",
}

def _check_spawn_request(message: str, thread: dict, agent_chat_mod):
    """Detect if the founder is asking an agent to start a chat with another agent."""
    msg_lower = message.lower()

    # Look for patterns like "chat with Sam", "chat to Sam", "talk to Will", etc.
    triggers = [
        "chat with", "chat to", "talk to", "talk with", "discuss with",
        "speak to", "speak with", "loop in", "bring in", "pull in",
        "start a chat with", "start a conversation with", "have a word with",
        "get ", "ask ",
    ]
    target_name = None
    for trigger in triggers:
        if trigger in msg_lower:
            # Extract the name after the trigger
            after = msg_lower.split(trigger, 1)[1].strip().split()[0].rstrip(".,!?")
            if after in _AGENT_LOOKUP:
                target_name = after
                break

    if not target_name:
        return None

    target_key = _AGENT_LOOKUP[target_name]

    # Figure out which participant in the current thread was asked to start the chat
    # Use the first participant that isn't the target
    initiator = None
    for p in thread["participants"]:
        if p != target_key:
            initiator = p
            break
    if not initiator:
        initiator = thread["participants"][0]

    # Get context from the current thread
    recent_msgs = thread.get("messages", [])[-5:]
    context_summary = "\n".join(f"{m['name']}: {m['text']}" for m in recent_msgs)

    # Create new thread between the agents
    new_thread_id = agent_chat_mod.create_thread(
        [initiator, target_key],
        thread.get("topic", "Discussion"),
        f"The founder asked you to have this conversation.\n\nContext from previous chat:\n{context_summary}"
    )

    # Have both agents speak
    agent_chat_mod.agent_says(new_thread_id, initiator)
    agent_chat_mod.agent_says(new_thread_id, target_key)

    return new_thread_id


def _check_retry_request(message: str, thread: dict):
    """Detect if the founder is asking Max to retry a failed job."""
    msg_lower = message.lower()
    retry_triggers = ["retry", "try again", "run it again", "rerun", "re-run", "have another go",
                      "kick it off again", "give it another shot", "redo"]

    if not any(t in msg_lower for t in retry_triggers):
        return None

    # Check Max is in the thread
    if "manager_agent" not in thread.get("participants", []):
        return None

    # Extract the topic from the thread
    topic = thread.get("topic", "").replace("Review: ", "").replace("Failed: ", "").strip()
    if not topic:
        return None

    import sys, os, threading
    sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
    import job_queue, worker

    # Queue the retry
    job_id = job_queue.add_job(topic=topic, priority="high")

    # Update dashboard state
    state = read_state()
    if "manager_agent" in state["agents"]:
        state["agents"]["manager_agent"]["status"] = "working"
        state["agents"]["manager_agent"]["speech"] = f"Retrying \"{topic}\"..."
    entry = {
        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "agent": "manager_agent",
        "message": f"Retrying: {topic} (job #{job_id})",
    }
    state.setdefault("activity_log", []).insert(0, entry)
    state["pipeline_running"] = True
    write_state(state)

    # Run in background
    def run_retry():
        worker.run_queue()

    threading.Thread(target=run_retry, daemon=True).start()

    return {"job_id": job_id, "topic": topic}


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


@app.route("/api/content-register")
def api_content_register():
    """Get the content register."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
    import state as st
    site_slug = request.args.get("site", "site-a")
    return jsonify(st.get_all_content(site_slug))


@app.route("/api/content-calendar")
def api_content_calendar():
    """Get the content calendar."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
    import state as st
    site_slug = request.args.get("site", "site-a")
    return jsonify(st.get_calendar(site_slug))


@app.route("/api/learnings")
def api_learnings():
    """Get agent learning log."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
    import state as st
    agent = request.args.get("agent")
    ltype = request.args.get("type")
    return jsonify(st.get_learnings(agent_name=agent, learning_type=ltype, limit=50))


@app.route("/api/knowledge/<agent_key>")
def api_knowledge(agent_key):
    """Get an agent's knowledge base."""
    kb_path = Path(__file__).parent.parent / "agents" / "knowledge" / f"{agent_key}.md"
    if kb_path.exists():
        return jsonify({"agent": agent_key, "knowledge": kb_path.read_text()})
    return jsonify({"agent": agent_key, "knowledge": ""})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
