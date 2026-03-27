"""SEO Agent (Sarah) — generates structured content briefs from keyword seeds.

Uses the Sitemap Reader tool to check what's already live on the site.
Reads the content register for in-progress content.
Prevents keyword cannibalization at source.
"""

import json
import logging
import sys
from pathlib import Path

from openai import OpenAI

from config import load_prompt, load_site_config

# Add paths for tools and db
sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import state
import sitemap_reader

logger = logging.getLogger(__name__)


def run(topic: str, site_config: dict | None = None) -> dict:
    """Generate a content brief from a topic or keyword seed.

    1. Fetches live sitemap to see what's already published
    2. Checks content register for in-progress content
    3. Blocks duplicate keywords, forces different angle
    """
    if site_config is None:
        site_config = load_site_config()

    site_slug = site_config.get("site_slug", "site-a")
    domain = site_config.get("domain", "")

    # Tool 1: Check live sitemap
    live_content = sitemap_reader.get_existing_topics(domain)
    overlaps = sitemap_reader.check_overlap(domain, topic)

    # Tool 2: Check content register (in-progress stuff not yet live)
    in_progress = state.get_content_for_agent(site_slug)

    # Build duplicate warnings
    duplicate_block = ""
    if overlaps:
        overlap_slugs = ", ".join(f"\"{p.slug}\"" for p in overlaps)
        logger.warning("Keyword overlap detected: '%s' overlaps with %s", topic, overlap_slugs)
        duplicate_block = (
            f"\n\n🚫 DUPLICATE DETECTED: The topic \"{topic}\" overlaps with existing live pages: {overlap_slugs}\n"
            f"You MUST choose a DIFFERENT keyword. Suggestions:\n"
            f"- Find a long-tail variation (e.g. 'wagering requirements' → 'low wagering casino bonuses UK')\n"
            f"- Find a related subtopic not yet covered\n"
            f"- Target a different search intent for the same topic area\n"
            f"Your target_keyword MUST NOT match any existing page slug."
        )

    system_prompt = load_prompt("seo_agent")
    user_message = (
        f"Site config:\n{json.dumps(site_config, indent=2)}\n\n"
        f"Topic/keyword seed: {topic}\n\n"
        f"{live_content}\n\n"
        f"In-progress content (not yet live):\n{in_progress}"
        f"{duplicate_block}"
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

    # Post-check: verify the LLM didn't ignore the duplicate warning
    if overlaps:
        chosen_kw = brief.get("target_keyword", "").lower().replace(" ", "-")
        for p in overlaps:
            if chosen_kw == p.slug or chosen_kw in p.slug or p.slug in chosen_kw:
                logger.warning("Sarah tried to use duplicate keyword '%s' — forcing variation", chosen_kw)
                # Force a re-run with stronger instruction
                user_message += (
                    f"\n\nYou returned \"{brief.get('target_keyword')}\" which STILL matches an existing page. "
                    f"This is NOT acceptable. Pick something COMPLETELY different."
                )
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.6,
                    response_format={"type": "json_object"},
                )
                brief = json.loads(response.choices[0].message.content)
                break

    logger.info("SEO brief: %s → keyword: %s", topic, brief.get("target_keyword"))
    return brief


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    topic = sys.argv[1] if len(sys.argv) > 1 else "best uk online casinos"
    brief = run(topic)
    print(json.dumps(brief, indent=2))
