"""Lightweight client for pushing status updates to the office dashboard."""

import json
import logging
import os

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://68.183.44.120:5050")

IDLE_SPEECH = {
    "seo_agent": "Waiting for a keyword to research...",
    "writer_agent": "Ready to write when you are.",
    "editor_compliance_agent": "All quiet on the compliance front.",
    "publisher_agent": "No PRs to push right now.",
}


def _post(data: dict):
    """POST JSON to the dashboard API."""
    try:
        req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/update",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.debug("Dashboard update failed (non-fatal): %s", e)


def update(agent: str = None, status: str = None, speech: str = None,
           log: str = None, pipeline_running: bool = None, current_topic: str = None,
           run_complete: dict = None):
    """Push a status update to the dashboard."""
    data = {}
    if agent:
        data["agent"] = agent
    if status:
        data["status"] = status
    if speech:
        data["speech"] = speech
    if log:
        data["log"] = log
    if pipeline_running is not None:
        data["pipeline_running"] = pipeline_running
    if current_topic is not None:
        data["current_topic"] = current_topic
    if run_complete:
        data["run_complete"] = run_complete

    _post(data)


def reset_all_agents():
    """Set all agents back to idle."""
    for agent_key, idle_text in IDLE_SPEECH.items():
        update(agent=agent_key, status="idle", speech=idle_text)
    update(pipeline_running=False)
