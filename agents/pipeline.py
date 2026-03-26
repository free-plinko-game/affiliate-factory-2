"""Pipeline runner — chains SEO → Writer → Editor/Compliance → Publisher."""

import json
import logging
import sys
from datetime import datetime, timezone

import seo_agent
import writer_agent
import editor_compliance_agent
import publisher_agent
from config import load_site_config

logger = logging.getLogger(__name__)

MAX_REVISIONS = 3


def run_pipeline(topic: str, site_config: dict | None = None, publish: bool = True) -> dict:
    """Run the full content pipeline from topic to PR.

    Args:
        topic: Keyword seed or topic for the SEO Agent.
        site_config: Site config dict. Loaded from file if not provided.
        publish: If True, open a PR via Publisher Agent. If False, stop after compliance.

    Returns:
        Pipeline result dict with all intermediate outputs.
    """
    if site_config is None:
        site_config = load_site_config()

    result = {
        "topic": topic,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [],
    }

    def log_step(name, data):
        step = {"step": name, "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
        result["steps"].append(step)
        logger.info("Step complete: %s", name)

    # Step 1: SEO brief
    logger.info("Step 1: Generating SEO brief for topic: %s", topic)
    brief = seo_agent.run(topic, site_config)
    log_step("seo_brief", brief)

    # Step 2: Write draft
    logger.info("Step 2: Writing draft for keyword: %s", brief.get("target_keyword"))
    draft = writer_agent.run(brief, site_config)
    log_step("first_draft", {"length": len(draft), "keyword": brief.get("target_keyword")})

    # Step 3: Edit + compliance (with retry)
    compliance_result: dict = {}
    for attempt in range(1, MAX_REVISIONS + 1):
        logger.info("Step 3: Review attempt %d/%d", attempt, MAX_REVISIONS)
        compliance_result = editor_compliance_agent.run(draft, site_config, brief)
        log_step(f"review_attempt_{attempt}", compliance_result)

        if compliance_result["compliance_pass"] and compliance_result["editorial_pass"]:
            logger.info("Review passed on attempt %d", attempt)
            break

        if attempt < MAX_REVISIONS:
            logger.info("Issues found, sending back to writer for revision")
            issues = compliance_result.get("issues", [])
            remediation = compliance_result.get("remediation", [])
            # Pair each issue with its fix for clarity
            all_feedback = []
            for i, issue in enumerate(issues):
                fix = remediation[i] if i < len(remediation) else ""
                all_feedback.append(f"ISSUE: {issue} → FIX: {fix}")
            draft = writer_agent.run(brief, site_config, issues=all_feedback, previous_draft=draft)
            log_step(f"revision_{attempt}", {"length": len(draft)})

    if not compliance_result.get("compliance_pass") or not compliance_result.get("editorial_pass"):
        result["status"] = "review_failed"
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.error("ESCALATION: Review failed after %d attempts — needs founder review", MAX_REVISIONS)
        print("\n⚠ REVIEW FAILED — requires founder review")
        print(json.dumps(compliance_result, indent=2))
        return result

    # Step 4: Publish
    if publish:
        logger.info("Step 4: Publishing to GitHub")
        pr_url = publisher_agent.run(draft, brief, compliance_result, site_config)
        log_step("published", {"pr_url": pr_url})
        result["pr_url"] = pr_url
        result["status"] = "published"
        print(f"\n✓ PR opened: {pr_url}")
    else:
        result["status"] = "approved"
        result["draft"] = draft
        print("\n✓ Content approved (publish=False, no PR created)")

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    topic = sys.argv[1] if len(sys.argv) > 1 else "best uk online casinos"
    publish = "--no-publish" not in sys.argv

    result = run_pipeline(topic, publish=publish)

    # Save pipeline log
    log_path = f"pipeline_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info("Pipeline log saved: %s", log_path)
