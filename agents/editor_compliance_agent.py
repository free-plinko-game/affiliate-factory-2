"""Editor + Compliance Agent — reviews drafts for quality and regulatory compliance."""

import json
import logging

from openai import OpenAI

from config import load_prompt, load_site_config

logger = logging.getLogger(__name__)


def run(draft: str, site_config: dict | None = None, brief: dict | None = None) -> dict:
    """Review a draft article for editorial quality and compliance.

    Args:
        draft: Hugo markdown string to review.
        site_config: Site config dict. Loaded from file if not provided.
        brief: Optional content brief for structure validation.

    Returns:
        Dict with editorial_pass, compliance_pass, issues, and remediation.
    """
    if site_config is None:
        site_config = load_site_config()

    system_prompt = load_prompt("editor_compliance_agent")
    user_message = f"Site config:\n{json.dumps(site_config, indent=2)}\n\nArticle to review:\n{draft}"

    if brief:
        user_message += f"\n\nContent brief (for structure validation):\n{json.dumps(brief, indent=2)}"

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)

    # Ensure the critical fields are always present
    result.setdefault("editorial_pass", False)
    result.setdefault("compliance_pass", False)
    result.setdefault("issues", [])
    result.setdefault("remediation", [])

    logger.info(
        "Review complete — editorial: %s, compliance: %s, issues: %d",
        result["editorial_pass"],
        result["compliance_pass"],
        len(result["issues"]),
    )
    return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    draft_path = sys.argv[1] if len(sys.argv) > 1 else None
    if draft_path:
        with open(draft_path) as f:
            draft = f.read()
    else:
        print("Usage: python editor_compliance_agent.py <draft.md>")
        sys.exit(1)

    result = run(draft)
    print(json.dumps(result, indent=2))
