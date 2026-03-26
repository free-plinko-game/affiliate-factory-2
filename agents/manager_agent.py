"""Manager Agent — translates founder briefs into pipeline jobs."""

import json
import logging

from openai import OpenAI

from config import load_prompt, load_site_config

logger = logging.getLogger(__name__)


def run(brief: str, site_config: dict | None = None) -> dict:
    """Parse a founder brief into structured pipeline jobs.

    Args:
        brief: Natural language or structured brief from the founder.
        site_config: Site config dict. Loaded from file if not provided.

    Returns:
        Dict with interpretation, jobs list, and flags.
    """
    if site_config is None:
        site_config = load_site_config()

    system_prompt = load_prompt("manager_agent")
    user_message = (
        f"Site config:\n{json.dumps(site_config, indent=2)}\n\n"
        f"Founder brief:\n{brief}"
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    result.setdefault("interpretation", "")
    result.setdefault("jobs", [])
    result.setdefault("flags", [])

    logger.info(
        "Manager parsed brief → %d jobs, %d flags",
        len(result["jobs"]),
        len(result["flags"]),
    )
    return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    brief = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Write 3 articles about responsible gambling, casino bonuses, and how slots work"
    result = run(brief)
    print(json.dumps(result, indent=2))
