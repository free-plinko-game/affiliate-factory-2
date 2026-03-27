"""Queue worker — processes jobs from the queue through the pipeline."""

import logging
import time
import sys

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "db"))
import state

import job_queue
import seo_agent
import writer_agent
import editor_agent
import compliance_agent
import sub_editor_agent
import publisher_agent
import agent_chat
import dashboard_client as dash
import db
from config import load_site_config

logger = logging.getLogger(__name__)

MAX_REVISIONS = 3


def process_job(job: dict) -> dict:
    """Process a single job from the queue through the full pipeline."""
    job_id = job["id"]
    topic = job["topic"]
    instructions = job.get("instructions", "")
    site_config = load_site_config()

    job_queue.start_job(job_id)
    run_id = db.start_run(topic, topic)

    dash.update(pipeline_running=True, current_topic=topic,
                agent="manager_agent", status="working",
                speech=f"Processing: \"{topic}\"",
                log=f"Job #{job_id}: {topic}",
                thought=f"Starting job #{job_id}: \"{topic}\" ({job.get('content_type', 'guide')}, {job.get('priority', 'medium')})")

    try:
        # SEO brief
        dash.update(agent="seo_agent", status="working",
                    speech=f"Researching \"{topic}\"...",
                    log=f"SEO: {topic}",
                    thought=f"Researching: {topic}")
        brief = seo_agent.run(topic, site_config)
        kw = brief.get("target_keyword", topic)
        db.log_step(run_id, "seo_agent", "seo_brief", "done", brief)

        # Register content in state foundation
        site_slug = site_config.get("site_slug", "site-a")
        content_type = job.get("content_type", "guide")
        register_id = state.register_content(site_slug, kw, content_type, "briefed", run_id=run_id)
        calendar_id = state.add_to_calendar(site_slug, kw, content_type, job_id=job_id)

        dash.update(agent="seo_agent", status="success",
                    speech=f"Brief done! \"{kw}\"",
                    log=f"Brief → \"{kw}\"",
                    thought=f"Keyword: \"{kw}\" | {brief.get('word_count', '?')} words | {brief.get('intent', '?')}")

        # Write
        dash.update(agent="writer_agent", status="working",
                    speech=f"Writing \"{kw}\"...",
                    log=f"Writing: {kw}",
                    thought=f"Drafting \"{kw}\".{f' Instructions: {instructions}' if instructions else ''}")
        draft = writer_agent.run(brief, site_config)
        wc = len(draft.split())
        db.log_step(run_id, "writer_agent", "first_draft", "done", {"word_count": wc})
        state.update_content_status(register_id, "drafted", word_count=wc)
        state.update_calendar_status(calendar_id, "in_review", assigned_to="emma")

        dash.update(agent="writer_agent", status="success",
                    speech=f"Draft done! {wc} words.",
                    log=f"Draft: {wc} words",
                    thought=f"Draft complete: {wc} words. Off to review.")

        # Review loop
        comp_result = {}
        edit_result = {}
        passed = False

        for attempt in range(1, MAX_REVISIONS + 1):
            # Compliance
            dash.update(agent="compliance_agent", status="working",
                        speech=f"Compliance check #{attempt}...",
                        log=f"Compliance #{attempt}: {kw}")
            comp_result = compliance_agent.run(draft, site_config, brief)
            db.log_step(run_id, "compliance_agent", f"compliance_{attempt}", "done", comp_result)

            if comp_result.get("compliance_pass"):
                dash.update(agent="compliance_agent", status="success",
                            speech="Compliance clear!",
                            thought=f"[{kw}] Compliance passed.")
            else:
                dash.update(agent="compliance_agent", status="error",
                            speech=f"{len(comp_result.get('issues', []))} compliance issue(s).",
                            thought=f"[{kw}] Failed:\n" + "\n".join(f"• {i}" for i in comp_result.get("issues", [])))
                for issue in comp_result.get("issues", []):
                    state.log_learning("clara", "compliance_flag", issue,
                                       site_slug=site_slug, source=str(run_id))

            # Editorial
            dash.update(agent="editor_agent", status="working",
                        speech=f"Editorial review #{attempt}...",
                        log=f"Editorial #{attempt}: {kw}")
            edit_result = editor_agent.run(draft, site_config, brief)
            db.log_step(run_id, "editor_agent", f"editorial_{attempt}", "done", edit_result)

            if edit_result.get("editorial_pass"):
                dash.update(agent="editor_agent", status="success",
                            speech=f"\"{kw}\" reads great!",
                            thought=f"[{kw}] Editorial passed.")
            else:
                dash.update(agent="editor_agent", status="error",
                            speech=f"{len(edit_result.get('issues', []))} editorial issue(s).",
                            thought=f"[{kw}] Issues:\n" + "\n".join(f"• {i}" for i in edit_result.get("issues", [])))
                for issue in edit_result.get("issues", []):
                    state.log_learning("emma", "editorial_issue", issue,
                                       site_slug=site_slug, source=str(run_id))

            if comp_result.get("compliance_pass") and edit_result.get("editorial_pass"):
                passed = True
                break

            if attempt < MAX_REVISIONS:
                all_issues = []
                for src in [comp_result, edit_result]:
                    for i, issue in enumerate(src.get("issues", [])):
                        fix = src.get("remediation", [])[i] if i < len(src.get("remediation", [])) else ""
                        all_issues.append(f"ISSUE: {issue} → FIX: {fix}")

                dash.update(agent="sub_editor_agent", status="working",
                            speech=f"Fixing {len(all_issues)} issue(s)...",
                            log=f"Sub-editing: {len(all_issues)} fixes")
                draft = sub_editor_agent.run(draft, all_issues, site_config, brief)
                wc = len(draft.split())
                db.log_step(run_id, "sub_editor_agent", f"sub_edit_{attempt}", "done", {"word_count": wc})
                dash.update(agent="sub_editor_agent", status="success",
                            speech=f"Fixes done! {wc} words.",
                            log=f"Sub-edit: {wc} words")

        if not passed:
            # Agent discussion before escalating
            issues_text = "\n".join(f"- {i}" for i in comp_result.get("issues", []) + edit_result.get("issues", []))
            dash.update(agent="manager_agent", status="working",
                        speech=f"Emma & Clara discussing \"{kw}\"...",
                        log=f"💬 Agents discussing: {kw}")
            thread = agent_chat.discuss(
                ["editor_agent", "compliance_agent"], f"Review: {kw}",
                f"Remaining issues:\n{issues_text}\nCheck your KB for founder preferences.", rounds=2
            )
            for msg in thread.get("messages", []):
                dash.update(agent=msg["agent"], speech=f"💬 {msg['text'][:80]}")

            if thread.get("resolved"):
                passed = True
                dash.update(agent="manager_agent", status="success",
                            speech=f"Team resolved \"{kw}\"!",
                            log=f"✓ Resolved: {kw}")
            else:
                job_queue.finish_job(job_id, "review_failed", error="Review failed after discussion")
                db.finish_run(run_id, "failed")

                # Open group chat with all agents for founder to review
                all_issues = comp_result.get("issues", []) + edit_result.get("issues", [])
                issues_text = "\n".join(f"- {i}" for i in all_issues)
                group_thread = agent_chat.create_thread(
                    ["manager_agent", "editor_agent", "compliance_agent", "sub_editor_agent", "writer_agent"],
                    f"Failed: {kw}",
                    f"Article \"{kw}\" failed review after {MAX_REVISIONS} attempts.\n\nRemaining issues:\n{issues_text}\n\nThe founder can give feedback here and ask Max to retry."
                )
                # Max kicks off the discussion
                agent_chat.agent_says(group_thread, "manager_agent")
                # Emma and Clara chime in
                agent_chat.agent_says(group_thread, "editor_agent")
                agent_chat.agent_says(group_thread, "compliance_agent")

                dash.update(agent="manager_agent", status="error",
                            speech=f"\"{kw}\" failed. Group chat open — check in!",
                            log=f"FAILED: {kw} — group chat opened")
                return {"status": "review_failed", "job_id": job_id, "thread_id": group_thread}

        # Publish
        dash.update(agent="publisher_agent", status="working",
                    speech=f"Opening PR for \"{kw}\"...",
                    log=f"Publishing: {kw}")
        pr_url = publisher_agent.run(draft, brief, {**comp_result, **edit_result}, site_config)
        db.log_step(run_id, "publisher_agent", "published", "done", {"pr_url": pr_url})
        dash.update(agent="publisher_agent", status="success",
                    speech=f"PR opened for \"{kw}\"!",
                    log=f"PR → {pr_url}")

        # Update state foundation
        state.update_content_status(register_id, "published", pr_url=pr_url,
                                     compliance_pass=1, word_count=len(draft.split()),
                                     slug=brief.get("target_keyword", "").replace(" ", "-").lower())
        state.update_calendar_status(calendar_id, "published",
                                      content_register_id=register_id)

        job_queue.finish_job(job_id, "published", pr_url=pr_url, run_id=run_id)
        db.finish_run(run_id, "completed", pr_url=pr_url)
        return {"status": "published", "pr_url": pr_url, "job_id": job_id}

    except Exception as e:
        logger.exception("Job %d failed: %s", job_id, e)
        job_queue.finish_job(job_id, "failed", error=str(e))
        db.finish_run(run_id, "failed")
        dash.update(agent="manager_agent", status="error",
                    speech=f"Error on \"{topic}\": {str(e)[:60]}",
                    log=f"ERROR: {e}")
        return {"status": "failed", "error": str(e), "job_id": job_id}


def run_queue(limit: int = 10):
    """Process all queued jobs."""
    jobs = job_queue.get_next_jobs(limit=limit)
    if not jobs:
        logger.info("Queue empty.")
        dash.update(agent="manager_agent", status="idle",
                    speech="Queue empty. Nothing to do.",
                    log="Queue empty")
        return []

    logger.info("Processing %d jobs from queue", len(jobs))
    dash.update(agent="manager_agent", status="working",
                speech=f"{len(jobs)} job(s) in queue. Let's go!",
                log=f"Queue: {len(jobs)} jobs",
                pipeline_running=True)

    results = []
    for i, job in enumerate(jobs):
        dash.update(agent="manager_agent", status="working",
                    speech=f"Job {i+1}/{len(jobs)}: \"{job['topic']}\"",
                    current_topic=job["topic"])
        result = process_job(job)
        results.append(result)

        # Reset worker agents between jobs
        for a in ["seo_agent", "writer_agent", "editor_agent", "sub_editor_agent",
                   "compliance_agent", "publisher_agent"]:
            dash.update(agent=a, status="idle")

    published = sum(1 for r in results if r.get("status") == "published")
    failed = sum(1 for r in results if r.get("status") != "published")
    dash.update(agent="manager_agent", status="success",
                speech=f"Queue done! {published} published, {failed} failed.",
                log=f"Queue complete: {published}/{len(results)}",
                pipeline_running=False,
                run_complete={"topic": f"Batch: {len(results)} jobs", "status": "completed",
                              "jobs": len(results)})

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    run_queue()
