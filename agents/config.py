import json
import os
from pathlib import Path

AGENTS_DIR = Path(__file__).parent
PROJECT_ROOT = AGENTS_DIR.parent
PROMPTS_DIR = AGENTS_DIR / "prompts"
SITE_CONFIG_PATH = PROJECT_ROOT / "site-config.json"


def load_prompt(agent_name: str) -> str:
    path = PROMPTS_DIR / f"{agent_name}.md"
    return path.read_text()


def load_site_config() -> dict:
    return json.loads(SITE_CONFIG_PATH.read_text())
