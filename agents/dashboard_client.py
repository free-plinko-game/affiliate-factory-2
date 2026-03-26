"""Lightweight client for pushing status updates to the office dashboard."""

import json
import logging
import os

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://68.183.44.120:5050")


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
           log: str = None, thought: str = None, clear_thoughts: bool = False,
           pipeline_running: bool = None, current_topic: str = None,
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
    if thought:
        data["thought"] = thought
    if clear_thoughts:
        data["clear_thoughts"] = True
    if pipeline_running is not None:
        data["pipeline_running"] = pipeline_running
    if current_topic is not None:
        data["current_topic"] = current_topic
    if run_complete:
        data["run_complete"] = run_complete

    _post(data)


def reset_all_agents():
    """Set all agents back to idle."""
    for a in ["manager_agent", "seo_agent", "writer_agent", "editor_agent", "compliance_agent", "publisher_agent"]:
        update(agent=a, status="idle", clear_thoughts=True)
    update(pipeline_running=False)
