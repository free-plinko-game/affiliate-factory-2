"""Editor Agent — reviews drafts for editorial quality only."""

import json
import logging

from openai import OpenAI

from config import load_prompt, load_site_config

logger = logging.getLogger(__name__)


def run(draft: str, site_config: dict | None = None, brief: dict | None = None) -> dict:
    """Review a draft for editorial quality.

    Returns:
        Dict with editorial_pass, issues, and remediation.
    """
    if site_config is None:
        site_config = load_site_config()

    system_prompt = load_prompt("editor_agent")
    user_message = f"Site config:\n{json.dumps(site_config, indent=2)}\n\nArticle to review:\n{draft}"
    if brief:
        user_message += f"\n\nContent brief:\n{json.dumps(brief, indent=2)}"

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    result.setdefault("editorial_pass", False)
    result.setdefault("issues", [])
    result.setdefault("remediation", [])

    logger.info("Editorial review: %s (%d issues)", result["editorial_pass"], len(result["issues"]))
    return result
