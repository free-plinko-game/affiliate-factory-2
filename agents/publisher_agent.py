"""Publisher Agent — commits approved content to GitHub and opens a PR."""

import json
import logging
from datetime import date

from github import Github, Auth
from openai import OpenAI

from config import load_prompt, load_site_config

logger = logging.getLogger(__name__)


def _determine_publish_details(draft: str, brief: dict, compliance_result: dict, site_config: dict) -> dict:
    """Use the LLM to determine file path, branch name, and PR details."""
    system_prompt = load_prompt("publisher_agent")
    user_message = (
        f"Site config:\n{json.dumps(site_config, indent=2)}\n\n"
        f"Content brief:\n{json.dumps(brief, indent=2)}\n\n"
        f"Compliance result:\n{json.dumps(compliance_result, indent=2)}\n\n"
        f"Article:\n{draft}"
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


def run(
    draft: str,
    brief: dict,
    compliance_result: dict,
    site_config: dict | None = None,
    github_token: str | None = None,
) -> str:
    """Publish approved content as a GitHub PR.

    Args:
        draft: The approved Hugo markdown content.
        brief: The content brief from SEO Agent.
        compliance_result: The compliance check result.
        site_config: Site config dict. Loaded from file if not provided.
        github_token: GitHub personal access token. Falls back to GITHUB_TOKEN env var.

    Returns:
        The PR URL.
    """
    import os

    if site_config is None:
        site_config = load_site_config()

    if github_token is None:
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

    # Determine publish details via LLM
    details = _determine_publish_details(draft, brief, compliance_result, site_config)
    logger.info("Publish details: %s", json.dumps(details))

    # Connect to GitHub
    auth = Auth.Token(github_token)
    g = Github(auth=auth)
    repo = g.get_repo(site_config["repo"])

    # Create branch from main
    main_branch = repo.get_branch(site_config["deploy_branch"])
    branch_name = details["branch_name"]
    repo.create_git_ref(f"refs/heads/{branch_name}", main_branch.commit.sha)
    logger.info("Created branch: %s", branch_name)

    # Commit the content file
    file_path = details["file_path"]
    repo.create_file(
        path=file_path,
        message=f"Add content: {brief.get('target_keyword', 'new article')}",
        content=draft,
        branch=branch_name,
    )
    logger.info("Committed file: %s", file_path)

    # Open PR
    pr = repo.create_pull(
        title=details["pr_title"],
        body=details["pr_body"],
        head=branch_name,
        base=site_config["deploy_branch"],
    )
    logger.info("PR opened: %s", pr.html_url)

    g.close()
    return pr.html_url


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    print("Publisher Agent — use via pipeline.py or import directly.")
    print("Requires: GITHUB_TOKEN env var, draft markdown, brief JSON, compliance JSON.")
