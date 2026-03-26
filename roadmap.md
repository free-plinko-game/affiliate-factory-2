# Affiliate MCP Portfolio — Build Roadmap
> Full system: MCP-powered agent infrastructure for a portfolio of gambling affiliate static sites.
> Built with Claude Code. Stack: Hugo, GitHub Actions, DigitalOcean VPS, OpenAI API, Python/Flask.

---

## Architecture overview

### The concept
A hub-and-spoke model. Central agent teams (Content, SEO, Tech, Commercial) are shared across a portfolio of sites. Each site has its own config file that tells agents which rules, tone, market, and affiliate programs apply. Launching a new site means writing a new config — not rebuilding the system.

### The office metaphor
The MCP server is the office. Agents are employees with specialisations baked into their system prompts. The Manager Agent is the COO — it orchestrates, routes work, and escalates genuine blockers to the founder. The founder (you) sets direction weekly; the office handles execution.

### Core principles
- Platform first — build the site before building agents
- Publisher Agent is the bridge — get content landing somewhere real before scaling the pipeline
- Site config file drives all agent behaviour per site
- Compliance is non-negotiable in gambling — it gates every publish
- Python scripts first, formal MCP server later (Phase 5 refactor)

---

## Site config file (per site)

Every agent loads this before acting. Lives at `/sites/{site-slug}/config.md` or `config.json`.

```json
{
  "site_slug": "site-a",
  "domain": "example.com",
  "repo": "github.com/yourorg/site-a",
  "market": "UK",
  "jurisdiction": "UKGC",
  "language": "en-GB",
  "tone_of_voice": "Authoritative, clear, responsible. No hype. No pressure language.",
  "target_audience": "UK adults 25-45, recreational gamblers",
  "content_focus": ["casino reviews", "bonus comparisons", "responsible gambling"],
  "affiliate_programs": [
    { "name": "Program A", "type": "CPA", "value": "£X per FTD" },
    { "name": "Program B", "type": "rev_share", "value": "X%" }
  ],
  "compliance_framework": ["ASA CAP Code 16/17", "UKGC licence condition 7", "BeGambleAware messaging required"],
  "hugo_theme": "theme-name",
  "deploy_branch": "main"
}
```

---

## Phase 1 — MVP (Weeks 1–4)
**Goal:** Publish real content to a real site via agents, with founder reviewing before merge.

One site. One pipeline. Prove the loop works end to end.

### 1.1 Platform setup

**Hugo site on VPS**
- Provision DigitalOcean Droplet (Ubuntu 22.04, minimum 2GB RAM)
- Install Hugo, Git, Nginx
- Set up GitHub repo for Site A
- Configure GitHub Actions: on push to `main` → Hugo build → rsync to VPS
- Set up domain + SSL (Let's Encrypt)
- Verify: push a test markdown file, confirm it builds and deploys live

**Repo structure**
```
site-a/
├── content/
│   ├── reviews/
│   ├── bonuses/
│   └── guides/
├── static/
├── themes/
├── config.toml
└── site-config.json   ← agent config file
```

**GitHub Actions workflow**
```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Hugo
        uses: peaceiris/actions-hugo@v2
      - name: Deploy to VPS
        uses: appleboy/scp-action@master
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_KEY }}
          source: public/
          target: /var/www/site-a/
```

---

### 1.2 Agent: SEO Agent

**Role:** Keyword research and content brief generation.

**System prompt (core)**
```
You are an SEO specialist for a gambling affiliate site. You will be given a site config 
and a topic area. Return a structured JSON content brief including: target keyword, 
supporting keywords, search intent, recommended word count, content structure outline, 
internal linking suggestions, and meta title/description.

Always prioritise informational and commercial investigation intent. 
Avoid transactional-only terms at brief stage.
```

**Input:** Site config JSON + topic or keyword seed
**Output:** Content brief JSON
```json
{
  "target_keyword": "best uk online casinos",
  "supporting_keywords": ["top casino sites uk", "licensed uk casinos"],
  "intent": "commercial investigation",
  "word_count": 2200,
  "outline": ["Introduction", "How we review", "Top picks", "Comparison table", "FAQs"],
  "meta_title": "Best UK Online Casinos 2025 — Licensed & Reviewed",
  "meta_description": "We review the top UK online casinos licensed by the UKGC..."
}
```

**Tools needed:** Web search (for SERP analysis), keyword data API (optional: Ahrefs/SEMrush API, or use web search as proxy at MVP stage)

---

### 1.3 Agent: Writer Agent

**Role:** Content production from brief to Hugo-ready markdown.

**System prompt (core)**
```
You are a content writer for a gambling affiliate site. You will be given a content brief 
and a site config. Write a complete article in markdown format with Hugo frontmatter.

Follow the tone of voice in the site config exactly. Include the target keyword naturally 
in the H1, first paragraph, and at least two subheadings. Do not use pressure language, 
urgency tactics, or imply gambling is a route to income. Include a responsible gambling 
section at the end of every article.
```

**Input:** Content brief JSON + site config
**Output:** Hugo markdown file
```markdown
---
title: "Best UK Online Casinos 2025"
date: 2025-01-15
slug: best-uk-online-casinos
description: "We review the top UK online casinos..."
keywords: ["best uk online casinos"]
author: "editorial-team"
---

[article body]

## Play responsibly
Gambling should be fun. If you feel it's becoming a problem...
[BeGambleAware messaging]
```

---

### 1.4 Agent: Editor + Compliance Agent (combined at MVP)

**Role:** Quality review and compliance check before publish.

**System prompt (core)**
```
You are an editor and compliance checker for a gambling affiliate site targeting the UK market.

Review the provided article for:
EDITORIAL: clarity, accuracy, factual claims, grammar, tone consistency with site config
COMPLIANCE: 
- Responsible gambling section present and correctly worded
- No pressure language or urgency tactics
- Bonus terms accurately described (no misleading claims)
- BeGambleAware or equivalent messaging included
- No claims that imply gambling is a way to make money
- 18+ messaging present

Return a JSON object:
{
  "editorial_pass": true/false,
  "compliance_pass": true/false,
  "issues": ["list of specific issues if any"],
  "remediation": ["suggested fixes per issue"]
}

If compliance_pass is false, the article must NOT be published.
```

**Input:** Draft markdown + site config
**Output:** JSON pass/fail with issues list

---

### 1.5 Agent: Publisher Agent

**Role:** Commit reviewed content to GitHub and open a PR for founder review.

**System prompt (core)**
```
You are a publishing agent. You will be given a Hugo markdown file and a site config.
Commit the file to the correct content directory in the site repo, on a new branch named 
content/{slug}-{date}. Open a pull request with a summary of the content, the SEO brief 
it was written to, and the compliance check result. Do not merge — leave for human review.
```

**Tools needed:** GitHub API (create branch, commit file, open PR)

**Input:** Approved markdown file + site config + compliance JSON
**Output:** GitHub PR URL

---

### Phase 1 success criteria
- [x] Hugo site live on VPS, auto-deploying from GitHub → **http://68.183.44.120:3284/**
- [x] SEO Agent produces a valid content brief from a keyword seed
- [x] Writer Agent produces a publishable Hugo markdown file from that brief
- [x] Editor/Compliance Agent returns a structured pass/fail JSON
- [x] Publisher Agent opens a PR on GitHub
- [x] You merge PR, site rebuilds and deploys automatically
- [x] End-to-end time from brief to PR under 10 minutes → **~60 seconds**

---

## Phase 2 — Orchestration (Weeks 5–8)
**Goal:** You give one brief to the Manager Agent and the pipeline runs itself.

### 2.1 Manager Agent

**Role:** Receives brief from founder, orchestrates full pipeline, handles routing on pass/fail.

**System prompt (core)**
```
You are the Manager Agent (COO) of a gambling affiliate content operation. You receive 
a brief from the founder and orchestrate the full content pipeline.

Pipeline sequence:
1. Send brief to SEO Agent → receive content brief JSON
2. Send content brief to Writer Agent → receive draft markdown
3. Send draft to Editor/Compliance Agent → receive pass/fail JSON
4. If compliance_pass is false: return issues to Writer Agent for revision (max 2 attempts)
5. If editorial_pass is false: return issues to Writer Agent for revision (max 2 attempts)
6. If both pass: send to Publisher Agent → receive PR URL
7. Report pipeline result to founder dashboard

Escalate to founder if: compliance fails after 2 revisions, ambiguous regulatory question 
arises, or any agent returns an error.
```

**Input:** Founder brief (natural language or structured JSON)
**Output:** PR URL + pipeline summary report

---

### 2.2 Pipeline runner

A Python script (later Flask app) that chains agent calls, logs each step, and retries on failure.

```python
# pipeline.py — simplified structure
def run_pipeline(brief: dict, site_config: dict):
    log("Pipeline started", brief)
    
    # Step 1: SEO brief
    seo_brief = seo_agent(brief, site_config)
    log("SEO brief complete", seo_brief)
    
    # Step 2: Write
    draft = writer_agent(seo_brief, site_config)
    log("Draft complete")
    
    # Step 3: Edit + compliance (with retry)
    for attempt in range(2):
        result = editor_compliance_agent(draft, site_config)
        if result["compliance_pass"] and result["editorial_pass"]:
            break
        draft = writer_agent(seo_brief, site_config, issues=result["issues"])
    
    if not result["compliance_pass"]:
        escalate_to_founder(result)
        return
    
    # Step 4: Publish
    pr_url = publisher_agent(draft, site_config, result)
    log("PR opened", pr_url)
    notify_founder(pr_url)
```

---

### 2.3 Flask dashboard (v1)

Simple internal tool. Shows pipeline run status, content in review, published pages.

**Routes:**
- `GET /` — pipeline run history, status per run
- `GET /runs/{id}` — full log for a specific run
- `GET /review` — PRs awaiting founder merge
- `POST /brief` — submit a new brief to trigger pipeline

**Stack:** Flask, SQLite (logs), GitHub API (PR status)

---

### 2.4 Split Editor and Compliance into separate agents

- **Editor Agent** — quality, tone, structure, factual accuracy
- **Compliance Agent** — regulatory checks only, returns structured JSON, hard blocks publish on fail

---

### Phase 2 success criteria
- [x] Single brief to Manager Agent triggers full pipeline without manual steps
- [x] Compliance fail routes back to ~~Writer~~ Sub-Editor (Sam) automatically
- [x] Pipeline logs every step with timestamps (SQLite)
- [x] Flask dashboard shows run history and pending PRs → **http://68.183.44.120:5050/**
- [x] Founder only touches the system to merge PRs and submit new briefs

### Built beyond original Phase 2 plan
- **Sub-Editor Agent (Sam)** — handles surgical revisions, freeing Will for the next job
- **Knowledge bases per agent** — each agent has a persistent .md file with learned preferences
- **Live chat with agents** — click any agent in dashboard, chat like Slack DM, feedback auto-saved to KB
- **Agent-to-agent chat** — Emma & Clara discuss borderline issues before escalating; Messenger-style bubbles in dashboard
- **Hybrid compliance** — programmatic checks (word count, 18+, BeGambleAware, T&Cs) + LLM for subjective review
- **Agent personalities** — each agent has character, can push back, disagree, and have opinions

---

## Phase 3 — Portfolio (Weeks 9–14)
**Goal:** Launch Site B using the same agents, just a different config file.

### 3.1 Multi-site repo structure

```
affiliate-portfolio/
├── agents/               ← shared agent codebase
│   ├── seo_agent.py
│   ├── writer_agent.py
│   ├── editor_agent.py
│   ├── compliance_agent.py
│   ├── publisher_agent.py
│   └── manager_agent.py
├── pipeline/
│   ├── runner.py
│   └── scheduler.py
├── dashboard/            ← Flask app
├── sites/
│   ├── site-a/
│   │   ├── config.json
│   │   └── [hugo site]
│   ├── site-b/
│   │   ├── config.json
│   │   └── [hugo site]
└── shared/
    ├── compliance-rules/
    │   ├── ukgc.md
    │   ├── mga.md
    │   └── asa-cap.md
    └── tone-templates/
```

---

### 3.2 Agent pooling

Multiple Writer Agent instances run in parallel. Manager Agent allocates by site priority and content backlog depth.

- Add a job queue (Redis or simple SQLite queue at this stage)
- Manager Agent pulls from queue, assigns to available Writer instance
- Each job tagged with site_slug so agents load correct config

---

### 3.3 Department head agents

Each head agent manages their team and reports up to Manager Agent.

**Head of Content Agent**
- Receives monthly content strategy from founder
- Breaks into weekly briefs per site
- Monitors quality scores from Editor Agent
- Flags if Writer pool output quality drops

**Head of SEO Agent**
- Sets keyword strategy per site
- Reviews ranking reports (fed in from rank tracker)
- Prioritises refresh vs new content
- Briefs KW Research Agent and On-site Agent

**Head of Tech Agent**
- Reviews VPS health, build times, Core Web Vitals
- Briefs Developer Agent on site improvements
- Monitors Security Agent reports

**Head of Commercial Agent**
- Reviews affiliate program performance
- Briefs Deals Agent on new programs to source
- Reviews Compliance Agent audit reports

---

### 3.4 Portfolio dashboard (v2)

Extended Flask dashboard:
- All sites in one view — content backlog, pipeline health, last published date
- Compliance flag summary per site
- Revenue signals per site (manual input at this stage, automated in Phase 4)
- Agent activity log across the portfolio

---

### Phase 3 success criteria
- [ ] Site B live using same agent codebase, different config
- [ ] Content pipeline running in parallel for both sites
- [ ] Department head agents producing weekly briefs without founder input
- [ ] Dashboard shows portfolio-level view
- [ ] Spinning up Site C requires only a new config file + Hugo setup

---

## Phase 4 — Commercial + SEO Intelligence (Weeks 15–20)
**Goal:** Agents monitor rankings, flag broken deals, surface revenue opportunities unprompted.

### 4.1 Commercial Agent

**Role:** Monitors affiliate program health across all sites.

**Triggers:** Scheduled (daily)
**Checks:**
- Affiliate link health (HTTP status of outbound links)
- Commission rate changes (compare against stored baseline)
- New affiliate program opportunities (web search for niche programs)
- Revenue anomalies (significant drop in reported conversions)

**Output:** Daily report to Head of Commercial Agent + escalates critical issues to Manager

---

### 4.2 Rank monitoring agent

**Role:** Tracks keyword positions, triggers content refresh when rankings drop.

**Integration:** Google Search Console API (free, reliable for owned sites) or third-party rank tracker API
**Logic:**
- Track all target keywords per site
- If position drops >5 places in 7 days → flag to Head of SEO
- If position drops below page 2 → trigger content refresh pipeline automatically
- New content that hasn't ranked within 90 days → flag for review

---

### 4.3 Scheduled compliance audits

**Role:** Compliance Agent runs across all live pages on a schedule, not just pre-publish.

**Schedule:** Weekly crawl of full sitemap per site
**Logic:**
- Fetch each live page
- Run compliance checks against current ruleset
- If rules have been updated since last audit → re-check all pages against new rules
- Output: audit report with pass/fail per page, list of pages requiring update
- Failed pages trigger Editor → Compliance → Publisher pipeline automatically

---

### 4.4 Analytics integration

Connect GA4 or Plausible to feed signals into Manager Agent decision-making.

**Signals that trigger agent action:**
- Traffic drop >20% on a page → content review pipeline
- High traffic page with low conversion → Commercial Agent review
- New organic traffic to a page not in keyword tracker → add to tracking

---

### Phase 4 success criteria
- [ ] Commercial Agent flags broken affiliate links within 24 hours
- [ ] Rank drops trigger content refresh automatically
- [ ] Compliance audit runs weekly across all live pages
- [ ] Analytics signals feeding into Manager Agent prioritisation
- [ ] Founder receives a weekly digest report, not individual alerts

---

## Phase 5 — Full Product (Month 6+)
**Goal:** Weekly brief from founder, everything else handled. New sites spin up in hours.

### 5.1 Autonomous weekly cycle

**Founder input:** One weekly brief (natural language, ~200 words) covering priorities, any commercial changes, new direction.

**Manager Agent runs:**
- Monday: process founder brief, cascade to department heads
- Tue–Thu: pipeline executes, content produced and queued for review
- Friday: weekly digest report to founder — what published, what's pending, any escalations, revenue signals

**Escalation rules (always comes to founder):**
- Compliance fail after 2 revisions
- New regulatory ruling not covered by existing ruleset
- Affiliate program dispute or deal negotiation
- New site launch decision
- Anything the Manager Agent classifies as ambiguous or high-risk

---

### 5.2 Site spin-up automation

New site from config to live in under 4 hours.

**Developer Agent workflow:**
1. Read new `config.json`
2. Scaffold Hugo site from template
3. Create GitHub repo, push initial commit
4. Configure GitHub Actions workflow
5. Provision subdomain/domain DNS
6. Configure Nginx on VPS
7. Run first compliance check on site template
8. Open PR for founder review and launch approval

---

### 5.3 Agent memory layer

Agents learn what works. Successful patterns feed back into future decisions.

**Implementation:** Vector database (Chroma or Pinecone) storing:
- Content performance by type, topic, format, word count
- Keyword win/loss history per site
- Compliance issue patterns (what triggers flags most often)
- Affiliate program performance by content type

**Usage:**
- Writer Agent retrieves top-performing content patterns before writing
- SEO Agent checks which keyword clusters have driven results
- Head of Content Agent uses performance data to adjust brief templates

---

### 5.4 Formal MCP server

Refactor Python scripts into a proper MCP server implementation.

**What changes:**
- Agents become first-class MCP tools, callable by any MCP-compatible client
- Tool definitions replace ad-hoc function calls
- Agent portability — any agent can be called from Claude Code, Claude Desktop, or other MCP clients
- Cleaner separation between agent logic and orchestration

**What stays the same:**
- System prompts and agent behaviour
- Site config structure
- Hugo + GitHub + VPS deployment stack

---

## Tech stack — full picture

| Layer | MVP (Phase 1–2) | Full product (Phase 5) |
|---|---|---|
| Sites | Hugo on VPS | Hugo on VPS |
| Hosting | DigitalOcean Droplet | DigitalOcean (scaled) |
| CI/CD | GitHub Actions | GitHub Actions |
| Agent runtime | Python scripts | MCP server |
| AI model | OpenAI API | OpenAI API (swap anytime) |
| Orchestration | Pipeline runner script | Manager Agent + job queue |
| Job queue | None / SQLite | Redis |
| Dashboard | Flask + SQLite | Flask + PostgreSQL |
| Compliance rules | Markdown files in repo | Markdown files + version history |
| Memory | None | Chroma / Pinecone |
| Analytics | Manual | GA4 / Plausible API |
| Rank tracking | Manual | GSC API / rank tracker API |
| Affiliate monitoring | Manual | Commercial Agent + HTTP checks |

---

## Agent index

| Agent | Name | Phase | Status | Reports to | Tools |
|---|---|---|---|---|---|
| Manager Agent | Max | 2 | **Live** | Founder | All agent APIs |
| SEO Agent | Sarah | 1 | **Live** | Manager | Web search, KW data |
| Writer Agent | Will | 1 | **Live** | Manager | None (LLM only) |
| Editor Agent | Emma | 2 | **Live** | Manager | None (LLM only) |
| Sub-Editor Agent | Sam | 2 | **Live** | Emma | None (LLM only) |
| Compliance Agent | Clara | 2 | **Live** | Manager | Programmatic + LLM |
| Publisher Agent | Pete | 1 | **Live** | Manager | GitHub API (PyGithub) |
| Head of Content | 3 | Manager | Pipeline runner |
| Head of SEO | 3 | Manager | Rank data, GSC API |
| Head of Tech | 3 | Manager | VPS metrics, GitHub API |
| Head of Commercial | 3 | Manager | Affiliate APIs |
| KW Research Agent | 3 | Head of SEO | Web search, KW API |
| On-site Agent | 3 | Head of SEO | Hugo file access |
| Off-site Agent | 3 | Head of SEO | Web search, outreach tools |
| Developer Agent | 3 | Head of Tech | GitHub API, VPS SSH |
| Security Agent | 3 | Head of Tech | Scan tools, VPS access |
| Commercial Agent | 4 | Head of Commercial | Affiliate APIs, HTTP checks |
| Deals Agent | 4 | Head of Commercial | Web search |
| Monetisation Agent | 4 | Head of Commercial | Analytics API |

---

## Notes for Claude Code

- Start with Phase 1. Do not build agents until the Hugo site is live and deploying.
- The site config JSON is load-bearing — design it carefully before writing agent prompts.
- Every agent should return structured JSON where possible. Prose responses are harder to route.
- Compliance Agent output must always be JSON with explicit `compliance_pass: true/false`. This is the hard gate.
- Publisher Agent should never auto-merge. PRs always require human approval until Phase 5 is mature.
- Keep agent system prompts in separate `.txt` or `.md` files in the repo — not hardcoded in scripts. Makes iteration fast.
- Log everything. You cannot debug a multi-agent pipeline without logs.
- Build the Flask dashboard early (Phase 2). Flying blind on pipeline status is painful.