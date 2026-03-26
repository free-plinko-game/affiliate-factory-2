"""Pipeline runner — Manager Agent orchestrates the office.

Flow per job:
  1. Sarah (SEO) → brief
  2. Will (Writer) → first draft (then freed for next job)
  3. Clara (Compliance) → programmatic + LLM checks
  4. Emma (Editor) → editorial review
  5. If issues: Sam (Sub-Editor) fixes → back to Emma (loop)
  6. Pete (Publisher) → PR

Max (Manager) can dispatch the next job to Will as soon as the first draft is done.
"""

import logging
import sys

import manager_agent
import seo_agent
import writer_agent
import editor_agent
import compliance_agent
import sub_editor_agent
import publisher_agent
import dashboard_client as dash
import db
from config import load_site_config

logger = logging.getLogger(__name__)

MAX_REVISIONS = 3


def _review_and_fix(draft: str, site_config: dict, brief: dict, run_id: int, job_label: str) -> tuple:
    """Run the compliance → editor → sub-editor loop. Returns (final_draft, comp_result, edit_result, passed)."""

    for attempt in range(1, MAX_REVISIONS + 1):
        # Compliance
        dash.update(agent="compliance_agent", status="working",
                    speech=f"Checking compliance on \"{job_label}\" (attempt {attempt})...",
                    log=f"Compliance #{attempt}: {job_label}",
                    thought=f"[{job_label}] Attempt {attempt}/{MAX_REVISIONS}. Running programmatic checks: 18+, BeGambleAware, RG section, pressure language, T&Cs, word count...")
        comp_result = compliance_agent.run(draft, site_config, brief)
        db.log_step(run_id, "compliance_agent", f"compliance_{attempt}", "done", comp_result)
        comp_issues = comp_result.get("issues", [])

        if not comp_result.get("compliance_pass", False):
            dash.update(agent="compliance_agent", status="error",
                        speech=f"{len(comp_issues)} compliance issue(s) on \"{job_label}\".",
                        log=f"Compliance FAIL — {len(comp_issues)} issues",
                        thought=f"[{job_label}] FAILED:\n" + "\n".join(f"• {i}" for i in comp_issues))
        else:
            dash.update(agent="compliance_agent", status="success",
                        speech=f"Compliance clear on \"{job_label}\"!",
                        log=f"Compliance PASS: {job_label}",
                        thought=f"[{job_label}] All checks passed. ✓ 18+ ✓ BeGambleAware ✓ RG section ✓ No pressure language ✓ T&Cs ✓ Word count")

        # Editor
        dash.update(agent="editor_agent", status="working",
                    speech=f"Reviewing \"{job_label}\" (attempt {attempt})...",
                    log=f"Editorial #{attempt}: {job_label}",
                    thought=f"[{job_label}] Checking tone, keyword placement, grammar, structure...")
        edit_result = editor_agent.run(draft, site_config, brief)
        db.log_step(run_id, "editor_agent", f"editorial_{attempt}", "done", edit_result)
        edit_issues = edit_result.get("issues", [])

        if not edit_result.get("editorial_pass", False):
            dash.update(agent="editor_agent", status="error",
                        speech=f"{len(edit_issues)} editorial issue(s). Passing to Sam.",
                        log=f"Editorial FAIL — {len(edit_issues)} issues",
                        thought=f"[{job_label}] Not quite right:\n" + "\n".join(f"• {i}" for i in edit_issues))
        else:
            dash.update(agent="editor_agent", status="success",
                        speech=f"\"{job_label}\" reads great!",
                        log=f"Editorial PASS: {job_label}",
                        thought=f"[{job_label}] Approved. Tone on-brand, structure solid, keyword placement good.")

        # Both passed?
        if comp_result.get("compliance_pass") and edit_result.get("editorial_pass"):
            return draft, comp_result, edit_result, True

        # Sub-editor fixes
        if attempt < MAX_REVISIONS:
            all_issues = []
            for src in [comp_result, edit_result]:
                issues = src.get("issues", [])
                fixes = src.get("remediation", [])
                for i, issue in enumerate(issues):
                    fix = fixes[i] if i < len(fixes) else ""
                    all_issues.append(f"ISSUE: {issue} → FIX: {fix}")

            dash.update(agent="sub_editor_agent", status="working",
                        speech=f"Fixing {len(all_issues)} issue(s) on \"{job_label}\"...",
                        log=f"Sub-editing: {len(all_issues)} fixes",
                        thought=f"[{job_label}] Revision {attempt}. Applying {len(all_issues)} fixes:\n" + "\n".join(f"• {i}" for i in all_issues))
            draft = sub_editor_agent.run(draft, all_issues, site_config, brief)
            wc = len(draft.split())
            db.log_step(run_id, "sub_editor_agent", f"sub_edit_{attempt}", "done", {"word_count": wc})
            dash.update(agent="sub_editor_agent", status="success",
                        speech=f"Fixes applied! {wc} words. Back to Emma.",
                        log=f"Sub-edit done: {wc} words",
                        thought=f"[{job_label}] Revision {attempt} complete. Now {wc} words. Applied all {len(all_issues)} fixes. Sending back to Emma and Clara...")

    return draft, comp_result, edit_result, False


def run_single_job(job: dict, site_config: dict, run_id: int) -> dict:
    """Run one content job through the full pipeline."""
    topic = job["topic"]
    instructions = job.get("instructions", "")
    kw = topic  # Updated after SEO brief

    # Step 1: SEO brief
    dash.update(agent="seo_agent", status="working",
                speech=f"Researching \"{topic}\"...",
                log=f"Researching: {topic}",
                thought=f"Starting keyword research for: {topic}")
    brief = seo_agent.run(topic, site_config)
    kw = brief.get("target_keyword", topic)
    supporting = brief.get("supporting_keywords", [])
    db.log_step(run_id, "seo_agent", "seo_brief", "done", brief)
    dash.update(agent="seo_agent", status="success",
                speech=f"Brief done! \"{kw}\" — {brief.get('word_count', '?')} words.",
                log=f"Brief → \"{kw}\"",
                thought=f"Primary: \"{kw}\" | Supporting: {', '.join(supporting[:3])} | Intent: {brief.get('intent', '?')} | {brief.get('word_count', '?')} words | {len(brief.get('outline', []))} sections")

    # Step 2: Will writes first draft
    dash.update(agent="writer_agent", status="working",
                speech=f"Writing \"{kw}\"...",
                log=f"Writing: {kw}",
                thought=f"Starting draft for \"{kw}\". Target: {brief.get('word_count', '?')} words, {len(brief.get('outline', []))} sections.{f' Instructions: {instructions}' if instructions else ''}")
    draft = writer_agent.run(brief, site_config)
    wc = len(draft.split())
    db.log_step(run_id, "writer_agent", "first_draft", "done", {"word_count": wc})
    dash.update(agent="writer_agent", status="success",
                speech=f"Draft done! {wc} words. Off to review.",
                log=f"Draft: {wc} words",
                thought=f"First draft complete: {wc} words. Handing off to Clara and Emma. I'm free for the next job.")

    # Step 3: Review + sub-editor loop (Will is now free)
    final_draft, comp_result, edit_result, passed = _review_and_fix(draft, site_config, brief, run_id, kw)

    if not passed:
        dash.update(agent="manager_agent", status="error",
                    speech=f"Couldn't get \"{kw}\" through. Escalating.",
                    log=f"ESCALATION: {kw}",
                    thought=f"Job failed for \"{kw}\". After {MAX_REVISIONS} review cycles, still has issues. Escalating to founder.")
        return {"topic": topic, "status": "review_failed",
                "issues": comp_result.get("issues", []) + edit_result.get("issues", [])}

    # Step 4: Publish
    dash.update(agent="publisher_agent", status="working",
                speech=f"Opening PR for \"{kw}\"...",
                log=f"Publishing: {kw}",
                thought=f"Creating branch and PR for \"{kw}\".")
    pr_url = publisher_agent.run(final_draft, brief, {**comp_result, **edit_result}, site_config)
    db.log_step(run_id, "publisher_agent", "published", "done", {"pr_url": pr_url})
    dash.update(agent="publisher_agent", status="success",
                speech=f"PR opened for \"{kw}\"!",
                log=f"PR → {pr_url}",
                thought=f"PR created: {pr_url}\nWaiting for founder to merge.")

    return {"topic": topic, "status": "published", "pr_url": pr_url}


def run_pipeline(brief_text: str, site_config: dict | None = None, publish: bool = True) -> dict:
    """Run the full pipeline from founder brief to PRs."""
    if site_config is None:
        site_config = load_site_config()

    dash.reset_all_agents()
    dash.update(pipeline_running=True, current_topic=brief_text[:80],
                log=f"New brief: {brief_text[:100]}")

    # Manager parses
    dash.update(agent="manager_agent", status="working",
                speech="Reading the founder's brief...",
                log="Parsing brief",
                thought=f"Brief received: \"{brief_text}\"")
    manager_result = manager_agent.run(brief_text, site_config)
    jobs = manager_result.get("jobs", [])
    flags = manager_result.get("flags", [])
    jobs_summary = ", ".join(f"\"{j.get('topic')}\"" for j in jobs)
    dash.update(agent="manager_agent", status="success",
                speech=f"{len(jobs)} job(s) queued. Let's go!",
                log=f"Manager → {len(jobs)} jobs",
                thought=f"Interpretation: {manager_result.get('interpretation', '?')}\nJobs: {jobs_summary}\n{'Flags: ' + ', '.join(flags) if flags else 'No flags.'}")

    run_id = db.start_run(brief_text, brief_text)
    db.log_step(run_id, "manager_agent", "parse_brief", "done", manager_result)

    results = []
    for i, job in enumerate(jobs):
        dash.update(agent="manager_agent", status="working",
                    speech=f"Job {i+1}/{len(jobs)}: \"{job.get('topic')}\"",
                    log=f"Job {i+1}/{len(jobs)}: {job.get('topic')}",
                    thought=f"Dispatching job {i+1}/{len(jobs)}: \"{job.get('topic')}\" ({job.get('content_type', '?')}, {job.get('priority', '?')})")

        if publish:
            job_result = run_single_job(job, site_config, run_id)
        else:
            job_result = run_single_job(job, site_config, run_id)
            # In dry run we'd skip publisher, but for now run same flow

        results.append(job_result)

    # Summary
    published = [r for r in results if r.get("status") == "published"]
    failed = [r for r in results if r.get("status") == "review_failed"]
    status = "completed" if not failed else ("partial" if published else "failed")
    pr_urls = [r["pr_url"] for r in published if "pr_url" in r]

    db.finish_run(run_id, status, pr_url=", ".join(pr_urls) if pr_urls else None,
                  manager_output=manager_result)

    dash.update(agent="manager_agent", status="success",
                speech=f"Done! {len(published)} published, {len(failed)} failed.",
                log=f"Complete: {len(published)} published, {len(failed)} failed",
                thought=f"Pipeline finished.\n✓ Published: {len(published)}\n✗ Failed: {len(failed)}\nPRs: {', '.join(pr_urls) if pr_urls else 'None'}",
                pipeline_running=False,
                run_complete={"topic": brief_text[:60], "status": status,
                              "pr_urls": pr_urls, "jobs": len(jobs)})

    for a in ["seo_agent", "writer_agent", "editor_agent", "sub_editor_agent", "compliance_agent", "publisher_agent"]:
        dash.update(agent=a, status="idle")

    return {"run_id": run_id, "manager": manager_result, "results": results,
            "status": status, "pr_urls": pr_urls}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")

    brief = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Write an article about the best UK casino bonuses"
    publish = "--no-publish" not in sys.argv
    if "--no-publish" in sys.argv:
        brief = brief.replace("--no-publish", "").strip()

    result = run_pipeline(brief, publish=publish)
    for pr in result.get("pr_urls", []):
        print(f"✓ PR: {pr}")
    if not result.get("pr_urls"):
        print(f"Pipeline finished: {result['status']}")
