import json
from pathlib import Path

AGENTS_DIR = Path(__file__).parent
PROJECT_ROOT = AGENTS_DIR.parent
PROMPTS_DIR = AGENTS_DIR / "prompts"
KNOWLEDGE_DIR = AGENTS_DIR / "knowledge"
SITE_CONFIG_PATH = PROJECT_ROOT / "site-config.json"


def load_prompt(agent_name: str) -> str:
    """Load system prompt + knowledge base for an agent."""
    prompt_path = PROMPTS_DIR / f"{agent_name}.md"
    prompt = prompt_path.read_text()

    kb_path = KNOWLEDGE_DIR / f"{agent_name}.md"
    if kb_path.exists():
        kb = kb_path.read_text().strip()
        if kb:
            prompt += f"\n\n---\n\nYour knowledge base (learned preferences and feedback from the founder):\n\n{kb}"

    return prompt


def load_knowledge(agent_name: str) -> str:
    """Load just the knowledge base for an agent."""
    kb_path = KNOWLEDGE_DIR / f"{agent_name}.md"
    if kb_path.exists():
        return kb_path.read_text()
    return ""


def save_knowledge(agent_name: str, content: str):
    """Save updated knowledge base for an agent."""
    kb_path = KNOWLEDGE_DIR / f"{agent_name}.md"
    kb_path.write_text(content)


def load_site_config() -> dict:
    return json.loads(SITE_CONFIG_PATH.read_text())
