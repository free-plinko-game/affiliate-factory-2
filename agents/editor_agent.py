"""Editor Agent — reviews drafts for editorial quality. Uses persistent session."""

import json
import logging

from openai import OpenAI

from config import load_prompt, load_site_config
import agent_session as session

logger = logging.getLogger(__name__)

AGENT_KEY = "editor_agent"


def run(draft: str, site_config: dict | None = None, brief: dict | None = None) -> dict:
    """Review a draft for editorial quality.

    Returns:
        Dict with editorial_pass, issues, and remediation.
    """
    if site_config is None:
        site_config = load_site_config()

    system_prompt = load_prompt(AGENT_KEY)
    user_message = f"Site config:\n{json.dumps(site_config, indent=2)}\n\nArticle to review:\n{draft}"
    if brief:
        user_message += f"\n\nContent brief:\n{json.dumps(brief, indent=2)}"

    # Build messages: system prompt + session history + this review request
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.get_messages_for_llm(AGENT_KEY))
    messages.append({"role": "user", "content": user_message})

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    reply = response.choices[0].message.content
    result = json.loads(reply)
    result.setdefault("editorial_pass", False)
    result.setdefault("issues", [])
    result.setdefault("remediation", [])

    # Log this interaction to the session
    kw = brief.get("target_keyword", "article") if brief else "article"
    session.add_event(AGENT_KEY, "user", f"[Review request] Article: \"{kw}\" ({len(draft.split())} words)", "pipeline")
    if result["editorial_pass"]:
        session.add_event(AGENT_KEY, "assistant", f"[Review] \"{kw}\" — PASSED. Looks good.", "pipeline")
    else:
        issues_summary = "; ".join(result["issues"][:3])
        session.add_event(AGENT_KEY, "assistant", f"[Review] \"{kw}\" — FAILED. Issues: {issues_summary}", "pipeline")

    logger.info("Editorial review: %s (%d issues)", result["editorial_pass"], len(result["issues"]))
    return result
