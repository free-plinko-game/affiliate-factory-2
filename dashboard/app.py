"""Agent Office Dashboard — watch your agents work like office employees."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

STATE_FILE = Path(__file__).parent / "state.json"

DEFAULT_STATE = {
    "pipeline_running": False,
    "current_topic": None,
    "agents": {
        "seo_agent": {
            "name": "Sarah",
            "title": "SEO Specialist",
            "status": "idle",
            "speech": "Waiting for a keyword to research...",
            "emoji": "🔍",
            "desk": "left",
        },
        "writer_agent": {
            "name": "Will",
            "title": "Content Writer",
            "status": "idle",
            "speech": "Ready to write when you are.",
            "emoji": "✍️",
            "desk": "center-left",
        },
        "editor_compliance_agent": {
            "name": "Emma",
            "title": "Editor & Compliance",
            "status": "idle",
            "speech": "All quiet on the compliance front.",
            "emoji": "📋",
            "desk": "center-right",
        },
        "publisher_agent": {
            "name": "Pete",
            "title": "Publisher",
            "status": "idle",
            "speech": "No PRs to push right now.",
            "emoji": "🚀",
            "desk": "right",
        },
    },
    "activity_log": [],
    "runs": [],
}


def read_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return DEFAULT_STATE.copy()


def write_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# Initialize state file if it doesn't exist
if not STATE_FILE.exists():
    write_state(DEFAULT_STATE)


@app.route("/")
def index():
    state = read_state()
    return render_template("office.html", state=state)


@app.route("/api/state")
def api_state():
    return jsonify(read_state())


@app.route("/api/update", methods=["POST"])
def api_update():
    """Called by the pipeline to update agent status."""
    data = request.json
    state = read_state()

    agent = data.get("agent")
    if agent and agent in state["agents"]:
        if "status" in data:
            state["agents"][agent]["status"] = data["status"]
        if "speech" in data:
            state["agents"][agent]["speech"] = data["speech"]

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
        state["activity_log"].insert(0, entry)
        state["activity_log"] = state["activity_log"][:50]  # Keep last 50

    if "run_complete" in data:
        state["runs"].insert(0, data["run_complete"])
        state["runs"] = state["runs"][:20]

    write_state(state)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
