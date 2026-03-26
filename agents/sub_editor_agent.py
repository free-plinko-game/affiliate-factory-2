"""Sub-Editor Agent — applies surgical fixes to drafts based on editorial feedback."""

import json
import logging

from openai import OpenAI

from config import load_prompt, load_site_config

logger = logging.getLogger(__name__)


def run(draft: str, issues: list[str], site_config: dict | None = None, brief: dict | None = None) -> str:
    """Apply editorial fixes to a draft.

    Args:
        draft: The current article markdown.
        issues: List of issues with fixes to apply.
        site_config: Site config dict.
        brief: Content brief for context.

    Returns:
        Revised markdown string.
    """
    if site_config is None:
        site_config = load_site_config()

    system_prompt = load_prompt("sub_editor_agent")
    user_message = (
        f"Site config:\n{json.dumps(site_config, indent=2)}\n\n"
        f"Current article ({len(draft.split())} words):\n{draft}\n\n"
        f"Issues to fix:\n" + "\n".join(f"- {i}" for i in issues)
    )

    if brief:
        user_message += f"\n\nContent brief (for reference):\n{json.dumps(brief, indent=2)}"

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
    )

    revised = response.choices[0].message.content.strip()

    # Strip markdown code fences if wrapped
    if revised.startswith("```"):
        first_newline = revised.index("\n")
        revised = revised[first_newline + 1:]
    if revised.endswith("```"):
        revised = revised[:-3].rstrip()

    logger.info("Sub-editor revised: %d → %d words", len(draft.split()), len(revised.split()))
    return revised
