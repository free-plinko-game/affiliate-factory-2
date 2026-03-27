"""Agent session — single persistent conversation per agent across all contexts."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(__file__).parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

MAX_HISTORY = 40  # Keep last N messages in context window


def _session_path(agent_key: str) -> Path:
    return SESSIONS_DIR / f"{agent_key}.json"


def get_history(agent_key: str) -> list[dict]:
    """Get an agent's full session history."""
    path = _session_path(agent_key)
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_history(agent_key: str, history: list[dict]):
    path = _session_path(agent_key)
    path.write_text(json.dumps(history, indent=2))


def add_event(agent_key: str, role: str, content: str, context: str = ""):
    """Add an event to an agent's session.

    Args:
        agent_key: Which agent
        role: 'user', 'assistant', or 'system'
        content: The message content
        context: Label like 'pipeline', 'founder_chat', 'agent_chat', 'review'
    """
    history = get_history(agent_key)
    history.append({
        "role": role,
        "content": content,
        "context": context,
        "time": datetime.now(timezone.utc).strftime("%H:%M"),
    })
    # Trim to keep manageable
    if len(history) > MAX_HISTORY * 2:
        history = history[-MAX_HISTORY * 2:]
    _save_history(agent_key, history)


def get_messages_for_llm(agent_key: str, limit: int = MAX_HISTORY) -> list[dict]:
    """Get recent session history formatted for the LLM messages array.

    Returns list of {role, content} dicts ready for OpenAI.
    """
    history = get_history(agent_key)
    recent = history[-limit:]
    return [{"role": h["role"], "content": h["content"]} for h in recent]


def clear_session(agent_key: str):
    """Clear an agent's session (e.g. between days)."""
    _save_history(agent_key, [])
