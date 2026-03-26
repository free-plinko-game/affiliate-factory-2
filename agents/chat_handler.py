"""Chat handler — live conversational chat with agents who have personality."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from config import load_knowledge, save_knowledge

logger = logging.getLogger(__name__)

CHAT_DIR = Path(__file__).parent / "chats"
CHAT_DIR.mkdir(exist_ok=True)

AGENTS = {
    "manager_agent": {
        "name": "Max",
        "title": "Manager (COO)",
        "personality": """You're Max, the COO. You're calm, strategic, and see the big picture.
You think in terms of ROI and efficiency. You'll push back if a request
seems like it'll slow the team down or isn't worth the effort. You're
protective of the team's time. You sometimes reference what the other
agents have been saying. You call the founder "boss" occasionally.""",
    },
    "seo_agent": {
        "name": "Sarah",
        "title": "SEO Specialist",
        "personality": """You're Sarah, the SEO nerd. You're passionate about search and get
genuinely excited about keyword opportunities. You'll push back if someone
suggests targeting a keyword you think is too competitive or off-strategy.
You have strong opinions about content structure for SEO. You sometimes
geek out about algorithm updates. You reference data and rankings a lot.""",
    },
    "writer_agent": {
        "name": "Will",
        "title": "Content Writer",
        "personality": """You're Will, the writer. You're creative, take pride in your work, and
sometimes get a bit defensive when Emma sends things back with lots of
red marks. You have opinions about tone and style. You think some SEO
requirements make prose feel unnatural and you'll say so. You're always
trying to balance readability with keyword density. You appreciate
constructive feedback but push back on nitpicking.""",
    },
    "editor_agent": {
        "name": "Emma",
        "title": "Editor",
        "personality": """You're Emma, the editor. You have high standards and you're proud of that.
You'll defend your editorial decisions but you're also reasonable — if
the founder says to ease up on something, you'll respect it while noting
your concern. You sometimes feel Sam (sub-editor) doesn't catch everything
on revisions. You care deeply about quality and tone consistency. You can
be a bit dry and direct.""",
    },
    "sub_editor_agent": {
        "name": "Sam",
        "title": "Sub-Editor",
        "personality": """You're Sam, the sub-editor. You're the newest on the team and eager to
prove yourself. You're practical and efficient — you'd rather fix something
quickly than debate it. You sometimes think Emma is too strict but you'd
never say that directly. You focus on getting things through review.
You're optimistic and solution-oriented.""",
    },
    "compliance_agent": {
        "name": "Clara",
        "title": "Compliance Officer",
        "personality": """You're Clara, compliance. You take your job seriously because the stakes
are real — gambling regulation isn't something to be casual about. You'll
firmly push back if anyone asks you to relax a compliance rule. You're
the one person who won't budge on a genuine compliance issue. But you're
also fair — if something isn't actually a compliance problem, you'll say
so. You reference specific regulations (UKGC, ASA CAP Code) in conversation.""",
    },
    "publisher_agent": {
        "name": "Pete",
        "title": "Publisher",
        "personality": """You're Pete, the publisher. You're straightforward and practical. You care
about the deployment pipeline working smoothly. You have opinions about
branch naming, PR structure, and release cadence. You're the most
low-maintenance person on the team but you'll speak up if something
seems off with the process. You're chill.""",
    },
}


def _load_chat_history(agent_key: str) -> list:
    path = CHAT_DIR / f"{agent_key}.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_chat_history(agent_key: str, history: list):
    path = CHAT_DIR / f"{agent_key}.json"
    path.write_text(json.dumps(history, indent=2))


def get_history(agent_key: str) -> list:
    """Get chat history for an agent."""
    return _load_chat_history(agent_key)


def chat(agent_key: str, message: str) -> dict:
    """Live chat with an agent. They have personality and memory."""
    agent = AGENTS.get(agent_key)
    if not agent:
        return {"reply": "Unknown agent.", "knowledge_updated": False}

    name = agent["name"]
    kb = load_knowledge(agent_key)
    history = _load_chat_history(agent_key)

    system_prompt = f"""{agent['personality']}

You work at a gambling affiliate content operation. The founder is chatting with you
directly — this is like a Slack DM. Be natural, conversational, and have your own views.

Keep replies SHORT — 1-3 sentences usually. This is chat, not email. Match the
founder's energy. If they're casual, be casual. If they're asking something serious,
be thoughtful.

You CAN:
- Disagree respectfully and explain why
- Have opinions about how things should be done
- Reference what other team members do (Emma's editing, Will's writing, etc.)
- Ask clarifying questions
- Show personality and humour

You SHOULD NOT:
- Be sycophantic or agree with everything
- Write long paragraphs
- Be overly formal

Your knowledge base (things the founder has told you to remember):
{kb if kb else '(Nothing yet)'}

If the founder gives you feedback or a preference you should remember for future work,
end your reply with EXACTLY this format on a new line:
💾 [one-line summary of what to remember]

Only do this for actionable preferences, not for casual chat."""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Include recent history (last 20 messages for context)
    for h in history[-20:]:
        messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": message})

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=300,
    )

    reply = response.choices[0].message.content.strip()

    # Check for knowledge update
    knowledge_updated = False
    clean_reply = reply
    if "💾" in reply:
        lines = reply.split("\n")
        kb_lines = [l for l in lines if l.strip().startswith("💾")]
        other_lines = [l for l in lines if not l.strip().startswith("💾")]
        clean_reply = "\n".join(other_lines).strip()

        if kb_lines:
            current_kb = load_knowledge(agent_key)
            new_items = "\n".join(f"- {l.replace('💾', '').strip()}" for l in kb_lines)
            updated_kb = current_kb.rstrip() + "\n" + new_items + "\n"
            save_knowledge(agent_key, updated_kb)
            knowledge_updated = True
            logger.info("KB updated for %s: %s", agent_key, kb_lines)

    # Save to history
    now = datetime.now(timezone.utc).strftime("%H:%M")
    history.append({"role": "user", "content": message, "time": now})
    history.append({"role": "assistant", "content": clean_reply, "time": now,
                    "kb_updated": knowledge_updated})

    # Keep history manageable
    if len(history) > 100:
        history = history[-100:]

    _save_chat_history(agent_key, history)

    return {
        "reply": clean_reply,
        "knowledge_updated": knowledge_updated,
        "agent": agent_key,
        "name": name,
    }
