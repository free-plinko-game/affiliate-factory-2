"""Writer Agent (Will) — produces Hugo-ready markdown from a content brief.

Reads the content register for internal linking opportunities.
"""

import json
import logging
import sys
from datetime import date

from openai import OpenAI

from config import load_prompt, load_site_config
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "db"))
import state

logger = logging.getLogger(__name__)


def run(brief: dict, site_config: dict | None = None, issues: list[str] | None = None, previous_draft: str | None = None) -> str:
    """Write an article from a content brief.

    Args:
        brief: Content brief dict from SEO Agent.
        site_config: Site config dict. Loaded from file if not provided.
        issues: Optional list of issues from Editor/Compliance Agent for revision.

    Returns:
        Hugo markdown string (frontmatter + body).
    """
    if site_config is None:
        site_config = load_site_config()

    site_slug = site_config.get("site_slug", "site-a")
    existing_content = state.get_content_for_agent(site_slug)

    system_prompt = load_prompt("writer_agent")
    user_message = (
        f"Site config:\n{json.dumps(site_config, indent=2)}\n\n"
        f"Content brief:\n{json.dumps(brief, indent=2)}\n\n"
        f"Today's date: {date.today().isoformat()}\n\n"
        f"Existing content on this site (use for internal linking where relevant):\n{existing_content}"
    )

    if issues and previous_draft:
        user_message += (
            f"\n\nREVISION REQUIRED — here is the current draft that needs fixing:\n\n"
            f"{previous_draft}\n\n"
            f"Fix ALL of the following issues. Keep the existing structure and content — "
            f"expand and correct, do not shorten or rewrite from scratch. "
            f"The revised article must be LONGER than the original, not shorter.\n\n"
            + "\n".join(f"- {issue}" for issue in issues)
        )
    elif issues:
        user_message += (
            f"\n\nREVISION REQUIRED — fix ALL of these issues:\n\n"
            + "\n".join(f"- {issue}" for issue in issues)
        )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.6,
    )

    draft = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps the output
    if draft.startswith("```"):
        first_newline = draft.index("\n")
        draft = draft[first_newline + 1:]
    if draft.endswith("```"):
        draft = draft[:-3].rstrip()

    logger.info("Draft written for keyword: %s (%d chars)", brief.get("target_keyword"), len(draft))
    return draft


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    brief_path = sys.argv[1] if len(sys.argv) > 1 else None
    if brief_path:
        with open(brief_path) as f:
            brief = json.load(f)
    else:
        brief = {
            "target_keyword": "best uk online casinos",
            "supporting_keywords": ["top casino sites uk", "licensed uk casinos"],
            "intent": "commercial investigation",
            "word_count": 2200,
            "outline": ["Introduction", "How we review", "Top picks", "Comparison table", "FAQs"],
            "meta_title": "Best UK Online Casinos 2026 — Licensed & Reviewed",
            "meta_description": "We review the top UK online casinos licensed by the UKGC.",
        }

    draft = run(brief)
    print(draft)
