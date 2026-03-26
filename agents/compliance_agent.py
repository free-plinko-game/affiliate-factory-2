"""Compliance Agent — regulatory compliance checks with programmatic + LLM layers."""

import json
import logging
import re

from openai import OpenAI

from config import load_prompt, load_site_config

logger = logging.getLogger(__name__)

PRESSURE_PHRASES = [
    "act now", "don't miss out", "limited time", "hurry",
    "guaranteed wins", "risk-free", "risk free",
]


def _programmatic_checks(draft: str) -> tuple[list[str], list[str]]:
    """Deterministic compliance checks that don't need an LLM."""
    issues = []
    remediation = []

    body = draft
    if draft.startswith("---"):
        parts = draft.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    # Word count
    words = len(body.split())
    if words < 800:
        issues.append(f"Word count is {words}, below the minimum of 800.")
        remediation.append(f"Expand the article by at least {800 - words} words.")

    # 18+ messaging
    if "18+" not in draft:
        issues.append("No '18+' messaging found in the article.")
        remediation.append("Add '18+' messaging near the start of the article.")

    # BeGambleAware
    if "begambleaware" not in draft.lower():
        issues.append("No BeGambleAware messaging found in the article.")
        remediation.append("Add a reference to BeGambleAware.org.")

    # Responsible gambling section
    headings = re.findall(r'^#{1,3}\s+(.+)$', draft, re.MULTILINE)
    has_rg_section = any("responsib" in h.lower() for h in headings)
    if not has_rg_section:
        issues.append("No responsible gambling section heading found.")
        remediation.append("Add a section with a heading like '## Play responsibly'.")

    # Pressure language
    body_lower = body.lower()
    found_pressure = [p for p in PRESSURE_PHRASES if p in body_lower]
    if found_pressure:
        issues.append(f"Pressure language found: {', '.join(found_pressure)}")
        remediation.append(f"Remove or rephrase: {', '.join(found_pressure)}")

    # T&Cs with bonuses
    if "bonus" in body_lower and "t&cs" not in body_lower and "terms and conditions" not in body_lower:
        issues.append("Bonuses mentioned without 'T&Cs apply' notice.")
        remediation.append("Add 'T&Cs apply' near each mention of bonuses.")

    return issues, remediation


def run(draft: str, site_config: dict | None = None, brief: dict | None = None) -> dict:
    """Check draft for regulatory compliance.

    Returns:
        Dict with compliance_pass, issues, and remediation.
    """
    if site_config is None:
        site_config = load_site_config()

    # Step 1: Programmatic checks
    prog_issues, prog_remediation = _programmatic_checks(draft)
    if prog_issues:
        logger.info("Programmatic compliance failed: %d issues", len(prog_issues))
        return {
            "compliance_pass": False,
            "issues": prog_issues,
            "remediation": prog_remediation,
        }

    # Step 2: LLM checks for subjective compliance
    system_prompt = load_prompt("compliance_agent")
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
    result.setdefault("compliance_pass", False)
    result.setdefault("issues", [])
    result.setdefault("remediation", [])

    logger.info("Compliance review: %s (%d issues)", result["compliance_pass"], len(result["issues"]))
    return result
