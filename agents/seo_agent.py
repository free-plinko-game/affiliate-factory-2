"""SEO Agent (Sarah) — generates structured content briefs from keyword seeds.

Reads the content register before briefing to avoid keyword cannibalization.
"""

import json
import logging
import sys

from openai import OpenAI

from config import load_prompt, load_site_config
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "db"))
import state

logger = logging.getLogger(__name__)


def run(topic: str, site_config: dict | None = None) -> dict:
    """Generate a content brief from a topic or keyword seed.

    Checks the content register first to avoid duplicating existing content.
    """
    if site_config is None:
        site_config = load_site_config()

    site_slug = site_config.get("site_slug", "site-a")

    # Check what already exists
    existing_content = state.get_content_for_agent(site_slug)
    duplicate_warning = ""
    if state.keyword_exists(site_slug, topic):
        duplicate_warning = (
            f"\n\n⚠ WARNING: The keyword \"{topic}\" (or similar) already exists in the content register. "
            f"You MUST choose a different angle, long-tail variation, or related keyword to avoid cannibalization. "
            f"Do NOT brief the same keyword again."
        )

    system_prompt = load_prompt("seo_agent")
    user_message = (
        f"Site config:\n{json.dumps(site_config, indent=2)}\n\n"
        f"Topic/keyword seed: {topic}\n\n"
        f"{existing_content}"
        f"{duplicate_warning}"
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )

    brief = json.loads(response.choices[0].message.content)
    logger.info("SEO brief: %s → keyword: %s", topic, brief.get("target_keyword"))
    return brief


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    topic = sys.argv[1] if len(sys.argv) > 1 else "best uk online casinos"
    brief = run(topic)
    print(json.dumps(brief, indent=2))
