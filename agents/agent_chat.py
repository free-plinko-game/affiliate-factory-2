"""Agent-to-agent chat system with founder escalation."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from config import load_knowledge

logger = logging.getLogger(__name__)

THREADS_DIR = Path(__file__).parent / "chats" / "threads"
THREADS_DIR.mkdir(parents=True, exist_ok=True)

AGENTS = {
    "manager_agent": {"name": "Max", "title": "Manager (COO)", "emoji": "👔"},
    "seo_agent": {"name": "Sarah", "title": "SEO Specialist", "emoji": "🔍"},
    "writer_agent": {"name": "Will", "title": "Content Writer", "emoji": "✍️"},
    "editor_agent": {"name": "Emma", "title": "Editor", "emoji": "📝"},
    "sub_editor_agent": {"name": "Sam", "title": "Sub-Editor", "emoji": "🔧"},
    "compliance_agent": {"name": "Clara", "title": "Compliance Officer", "emoji": "📋"},
    "publisher_agent": {"name": "Pete", "title": "Publisher", "emoji": "🚀"},
}

PERSONALITIES = {
    "manager_agent": "You're Max, the COO. Strategic, big-picture thinker. You mediate disagreements and make calls.",
    "seo_agent": "You're Sarah, SEO nerd. You care about rankings and keyword strategy. Data-driven.",
    "writer_agent": "You're Will, the writer. Creative, a bit defensive about your work, but professional.",
    "editor_agent": "You're Emma, the editor. High standards but reasonable. Direct and concise.",
    "sub_editor_agent": "You're Sam, the sub-editor. Eager, practical, solution-oriented.",
    "compliance_agent": "You're Clara, compliance. Firm on real violations, fair on grey areas. References regulations.",
    "publisher_agent": "You're Pete, publisher. Chill, practical, focused on shipping.",
}


def _thread_path(thread_id: str) -> Path:
    return THREADS_DIR / f"{thread_id}.json"


def create_thread(participants: list[str], topic: str, context: str = "") -> str:
    """Create a new chat thread between agents."""
    thread_id = f"t_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{participants[0][:4]}"
    thread = {
        "id": thread_id,
        "participants": participants,
        "topic": topic,
        "context": context,
        "messages": [],
        "needs_founder": False,
        "resolved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _thread_path(thread_id).write_text(json.dumps(thread, indent=2))
    return thread_id


def get_thread(thread_id: str) -> dict | None:
    path = _thread_path(thread_id)
    if path.exists():
        return json.loads(path.read_text())
    return None


def get_active_threads() -> list[dict]:
    """Get all unresolved threads, newest first."""
    threads = []
    for f in sorted(THREADS_DIR.glob("t_*.json"), reverse=True):
        t = json.loads(f.read_text())
        if not t.get("resolved"):
            threads.append(t)
    return threads[:10]


def get_all_threads(limit=20) -> list[dict]:
    """Get all threads, newest first."""
    threads = []
    for f in sorted(THREADS_DIR.glob("t_*.json"), reverse=True):
        threads.append(json.loads(f.read_text()))
    return threads[:limit]


def _save_thread(thread: dict):
    _thread_path(thread["id"]).write_text(json.dumps(thread, indent=2))


def agent_says(thread_id: str, agent_key: str, auto=True) -> str:
    """Have an agent contribute to a thread. Returns their message."""
    thread = get_thread(thread_id)
    if not thread:
        return ""

    agent = AGENTS.get(agent_key, {})
    name = agent.get("name", agent_key)
    kb = load_knowledge(agent_key)

    # Build the conversation context
    other_names = [AGENTS[p]["name"] for p in thread["participants"] if p != agent_key]
    system = f"""{PERSONALITIES.get(agent_key, '')}

You're in a group chat with {', '.join(other_names)} about: {thread['topic']}

Context: {thread.get('context', '')}

Your knowledge base: {kb if kb else '(empty)'}

Keep messages SHORT — 1-2 sentences. This is a quick work chat, not an essay.
Be natural, have opinions, reference specifics from the context.
If you think you need the founder's input, say "I think we need the boss on this" or "@founder".
If you agree with a resolution, say so clearly."""

    messages = [{"role": "system", "content": system}]
    for m in thread["messages"][-15:]:
        if m["agent"] == agent_key:
            messages.append({"role": "assistant", "content": m["text"]})
        else:
            messages.append({"role": "user", "content": f"{m['name']}: {m['text']}"})

    if not thread["messages"]:
        messages.append({"role": "user", "content": "Start the conversation — raise the issue."})

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=150,
    )

    text = response.choices[0].message.content.strip()

    msg = {
        "agent": agent_key,
        "name": name,
        "emoji": agent.get("emoji", ""),
        "text": text,
        "time": datetime.now(timezone.utc).strftime("%H:%M"),
        "is_founder": False,
    }
    thread["messages"].append(msg)

    # Check if they're escalating to founder
    if "@founder" in text.lower() or "need the boss" in text.lower():
        thread["needs_founder"] = True

    _save_thread(thread)
    logger.info("[%s] %s: %s", thread_id, name, text[:80])
    return text


def founder_says(thread_id: str, message: str):
    """Founder contributes to a thread."""
    thread = get_thread(thread_id)
    if not thread:
        return

    msg = {
        "agent": "founder",
        "name": "Boss",
        "emoji": "👤",
        "text": message,
        "time": datetime.now(timezone.utc).strftime("%H:%M"),
        "is_founder": True,
    }
    thread["messages"].append(msg)
    thread["needs_founder"] = False
    _save_thread(thread)


def resolve_thread(thread_id: str):
    """Mark a thread as resolved."""
    thread = get_thread(thread_id)
    if thread:
        thread["resolved"] = True
        _save_thread(thread)


def discuss(participants: list[str], topic: str, context: str = "", rounds: int = 2) -> dict:
    """Run a quick discussion between agents. Returns the thread.

    Each participant speaks once per round.
    """
    thread_id = create_thread(participants, topic, context)

    for _ in range(rounds):
        for agent_key in participants:
            agent_says(thread_id, agent_key)
            thread = get_thread(thread_id)
            if thread.get("needs_founder"):
                return thread
            # Check if they seem to agree (simple heuristic)
            last_msg = thread["messages"][-1]["text"].lower()
            if any(w in last_msg for w in ["agreed", "let's go with that", "sounds good", "fair enough", "i'm fine with"]):
                if len(thread["messages"]) >= len(participants):
                    resolve_thread(thread_id)
                    return get_thread(thread_id)

    return get_thread(thread_id)
