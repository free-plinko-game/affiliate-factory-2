"""Pipeline runner — chains SEO → Writer → Editor/Compliance → Publisher."""

import json
import logging
import sys
from datetime import datetime, timezone

import seo_agent
import writer_agent
import editor_compliance_agent
import publisher_agent
import dashboard_client as dash
from config import load_site_config

logger = logging.getLogger(__name__)

MAX_REVISIONS = 3


def run_pipeline(topic: str, site_config: dict | None = None, publish: bool = True) -> dict:
    """Run the full content pipeline from topic to PR."""
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

    # Signal pipeline start
    dash.update(pipeline_running=True, current_topic=topic, log=f"Pipeline started for: {topic}")

    # Step 1: SEO brief
    dash.update(agent="seo_agent", status="working",
                speech=f"Researching keywords for \"{topic}\"...",
                log=f"Researching: {topic}")
    brief = seo_agent.run(topic, site_config)
    log_step("seo_brief", brief)
    kw = brief.get("target_keyword", topic)
    dash.update(agent="seo_agent", status="success",
                speech=f"Brief done! Target: \"{kw}\" — {brief.get('word_count', '?')} words, {brief.get('intent', '?')} intent.",
                log=f"Brief complete → \"{kw}\"")

    # Step 2: Write draft
    dash.update(agent="writer_agent", status="working",
                speech=f"Writing first draft for \"{kw}\"... coffee's hot, let's go.",
                log=f"Writing draft for \"{kw}\"")
    draft = writer_agent.run(brief, site_config)
    word_count = len(draft.split())
    log_step("first_draft", {"length": len(draft), "keyword": kw})
    dash.update(agent="writer_agent", status="success",
                speech=f"First draft done! {word_count} words. Sending to Emma for review.",
                log=f"Draft complete — {word_count} words")

    # Step 3: Edit + compliance (with retry)
    compliance_result: dict = {}
    for attempt in range(1, MAX_REVISIONS + 1):
        dash.update(agent="editor_compliance_agent", status="working",
                    speech=f"Reviewing draft (attempt {attempt}/{MAX_REVISIONS})... checking compliance.",
                    log=f"Review attempt {attempt}/{MAX_REVISIONS}")
        compliance_result = editor_compliance_agent.run(draft, site_config, brief)
        log_step(f"review_attempt_{attempt}", compliance_result)

        issues = compliance_result.get("issues", [])
        c_pass = compliance_result.get("compliance_pass", False)
        e_pass = compliance_result.get("editorial_pass", False)

        if c_pass and e_pass:
            dash.update(agent="editor_compliance_agent", status="success",
                        speech="All clear! Editorial and compliance both passed. Ship it!",
                        log="Review PASSED — all clear")
            break

        issue_summary = issues[0] if issues else "minor issues"
        dash.update(agent="editor_compliance_agent", status="error",
                    speech=f"Found {len(issues)} issue(s): \"{issue_summary}\" — sending back to Will.",
                    log=f"Review failed — {len(issues)} issue(s)")

        if attempt < MAX_REVISIONS:
            dash.update(agent="writer_agent", status="working",
                        speech=f"Revising... Emma found {len(issues)} thing(s) to fix.",
                        log=f"Revising draft (attempt {attempt})")
            remediation = compliance_result.get("remediation", [])
            all_feedback = []
            for i, issue in enumerate(issues):
                fix = remediation[i] if i < len(remediation) else ""
                all_feedback.append(f"ISSUE: {issue} → FIX: {fix}")
            draft = writer_agent.run(brief, site_config, issues=all_feedback, previous_draft=draft)
            word_count = len(draft.split())
            log_step(f"revision_{attempt}", {"length": len(draft)})
            dash.update(agent="writer_agent", status="success",
                        speech=f"Revision done! Now {word_count} words. Back to you, Emma.",
                        log=f"Revision complete — {word_count} words")

    if not compliance_result.get("compliance_pass") or not compliance_result.get("editorial_pass"):
        result["status"] = "review_failed"
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        dash.update(pipeline_running=False,
                    log=f"ESCALATION: Review failed after {MAX_REVISIONS} attempts",
                    run_complete={"topic": topic, "status": "review_failed"})
        dash.update(agent="editor_compliance_agent", status="error",
                    speech=f"Couldn't get this one through. Escalating to the boss.")
        print("\n⚠ REVIEW FAILED — requires founder review")
        print(json.dumps(compliance_result, indent=2))
        return result

    # Step 4: Publish
    if publish:
        dash.update(agent="publisher_agent", status="working",
                    speech=f"Creating branch and PR for \"{kw}\"...",
                    log=f"Publishing to GitHub")
        pr_url = publisher_agent.run(draft, brief, compliance_result, site_config)
        log_step("published", {"pr_url": pr_url})
        result["pr_url"] = pr_url
        result["status"] = "published"
        dash.update(agent="publisher_agent", status="success",
                    speech=f"PR opened! Waiting for the boss to merge.",
                    log=f"PR opened → {pr_url}",
                    run_complete={"topic": topic, "status": "published", "pr_url": pr_url})
        dash.update(pipeline_running=False)
        print(f"\n✓ PR opened: {pr_url}")
    else:
        result["status"] = "approved"
        result["draft"] = draft
        dash.update(pipeline_running=False,
                    log="Content approved (no PR — dry run)",
                    run_complete={"topic": topic, "status": "approved"})
        print("\n✓ Content approved (publish=False, no PR created)")

    # Reset idle agents
    dash.update(agent="seo_agent", status="idle", speech="Done! Waiting for the next keyword...")
    dash.update(agent="writer_agent", status="idle", speech="Another one done. Who's next?")

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

    log_path = f"pipeline_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info("Pipeline log saved: %s", log_path)
