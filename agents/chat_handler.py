"""Chat handler — processes founder feedback and updates agent knowledge bases."""

import json
import logging

from openai import OpenAI

from config import load_prompt, load_knowledge, save_knowledge

logger = logging.getLogger(__name__)

AGENT_NAMES = {
    "manager_agent": "Max",
    "seo_agent": "Sarah",
    "writer_agent": "Will",
    "editor_agent": "Emma",
    "sub_editor_agent": "Sam",
    "compliance_agent": "Clara",
    "publisher_agent": "Pete",
}

AGENT_TITLES = {
    "manager_agent": "Manager (COO)",
    "seo_agent": "SEO Specialist",
    "writer_agent": "Content Writer",
    "editor_agent": "Editor",
    "sub_editor_agent": "Sub-Editor",
    "compliance_agent": "Compliance Officer",
    "publisher_agent": "Publisher",
}


def chat(agent_key: str, message: str) -> dict:
    """Process a message from the founder to an agent.

    Returns:
        Dict with 'reply' (agent's response) and 'knowledge_updated' (bool).
    """
    name = AGENT_NAMES.get(agent_key, agent_key)
    title = AGENT_TITLES.get(agent_key, "Agent")
    current_kb = load_knowledge(agent_key)

    system_prompt = f"""You are {name}, the {title} at a gambling affiliate content operation.
The founder is talking to you directly. Respond in character — be professional but personable.

Your current knowledge base:
{current_kb}

When the founder gives you feedback, guidance, or preferences:
1. Acknowledge it naturally in your reply
2. Return a JSON block at the END of your reply with the updated knowledge base

Format your reply as:
[Your natural conversational reply to the founder]

KNOWLEDGE_UPDATE:
```
[The complete updated knowledge base markdown, incorporating the new feedback. Keep all existing entries and add new ones. Be concise — bullet points, not paragraphs.]
```

If the message is just a question or chat (no actionable feedback), reply normally and do NOT include a KNOWLEDGE_UPDATE block."""

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        temperature=0.5,
    )

    full_reply = response.choices[0].message.content.strip()

    # Parse out knowledge update if present
    knowledge_updated = False
    reply = full_reply
    if "KNOWLEDGE_UPDATE:" in full_reply:
        parts = full_reply.split("KNOWLEDGE_UPDATE:", 1)
        reply = parts[0].strip()
        kb_block = parts[1].strip()
        # Extract from code fence if present
        if "```" in kb_block:
            kb_block = kb_block.split("```", 2)
            if len(kb_block) >= 2:
                kb_content = kb_block[1].strip()
                # Remove language identifier if present
                if kb_content.startswith("markdown"):
                    kb_content = kb_content[8:].strip()
                save_knowledge(agent_key, kb_content)
                knowledge_updated = True
                logger.info("Knowledge base updated for %s", agent_key)

    return {
        "reply": reply,
        "knowledge_updated": knowledge_updated,
        "agent": agent_key,
        "name": name,
    }
