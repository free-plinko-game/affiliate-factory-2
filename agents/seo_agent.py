"""SEO Agent — generates structured content briefs from keyword seeds."""

import json
import logging
from openai import OpenAI

from config import load_prompt, load_site_config

logger = logging.getLogger(__name__)


def run(topic: str, site_config: dict | None = None) -> dict:
    """Generate a content brief from a topic or keyword seed.

    Args:
        topic: The topic or keyword seed to build a brief around.
        site_config: Site config dict. Loaded from file if not provided.

    Returns:
        Content brief as a dict.
    """
    if site_config is None:
        site_config = load_site_config()

    system_prompt = load_prompt("seo_agent")
    user_message = (
        f"Site config:\n{json.dumps(site_config, indent=2)}\n\n"
        f"Topic/keyword seed: {topic}"
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
    logger.info("SEO brief generated for topic: %s → keyword: %s", topic, brief.get("target_keyword"))
    return brief


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    topic = sys.argv[1] if len(sys.argv) > 1 else "best uk online casinos"
    brief = run(topic)
    print(json.dumps(brief, indent=2))
