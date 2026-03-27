# Affiliate MCP Portfolio — Build Roadmap v2
> MCP-powered agent infrastructure for a portfolio of gambling affiliate static sites.
> Built with Claude Code. Stack: Hugo, GitHub Actions, DigitalOcean VPS, OpenAI API, Python/Flask.
> Last updated: March 2026

---

## Architecture overview

### The concept
A hub-and-spoke model. Central agent teams (Content, SEO, Tech, Commercial) are shared across a portfolio of sites. Each site has its own config file that tells agents which rules, tone, market, and affiliate programs apply. Launching a new site means writing a new config — not rebuilding the system.

### The office metaphor
The MCP server is the office. Agents are employees with specialisations baked into their system prompts — and personalities that let them push back, disagree, and have opinions. The Manager Agent (Max) is the COO — he orchestrates, routes work, and escalates genuine blockers to the founder. The founder sets direction weekly; the office handles execution.

### Core principles
- Platform first — build the site before building agents ✅
- Publisher Agent is the bridge — get content landing somewhere real before scaling ✅
- Site config file drives all agent behaviour per site ✅
- Compliance is non-negotiable in gambling — it gates every publish ✅
- Python scripts first, formal MCP server later (Phase 5 refactor)
- **State is an architectural concern, not a framework feature** — memory must be designed, not assumed

---

## State & memory architecture
> This is the most important section to get right. Statelessness is the primary scaling risk.

Three layers of state are required. No single framework solves all three.

### Layer 1 — Run-level state (pipeline continuity)
A pipeline that crashes halfway through should resume, not restart. Every pipeline run has a persistent record in the database with status at each step. If Will crashes mid-draft, Max can restart from that step, not from the SEO brief.

**Implementation:** `pipeline_runs` table in SQLite (already partially exists via logging). Add `step`, `status`, and `payload` columns so any step can be replayed.

### Layer 2 — Editorial memory (cross-run awareness)
Agents currently forget everything between runs. The SEO Agent doesn't know what keywords have already been briefed. Will doesn't know what he wrote last month. This causes keyword cannibalisation, duplicate content angles, and contradictory internal linking.

**Implementation:** `content_register` table — one row per published or in-progress piece. Every agent reads this before acting.

```sql
CREATE TABLE content_register (
  id INTEGER PRIMARY KEY,
  site_slug TEXT NOT NULL,
  keyword TEXT NOT NULL,
  slug TEXT,
  title TEXT,
  status TEXT,           -- 'briefed' | 'drafted' | 'published' | 'refresh-needed'
  published_date TEXT,
  word_count INTEGER,
  compliance_pass INTEGER,
  performance_score REAL, -- populated by rank monitoring in Phase 4
  notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Who reads it:**
- SEO Agent (Sarah) — checks before briefing any keyword to avoid duplication
- Writer Agent (Will) — checks for existing coverage and internal linking opportunities
- Head of SEO — reviews full register when planning keyword strategy

### Layer 3 — Agent learning log (institutional memory)
This is the raw material for self-improving prompts. Every compliance flag, every editorial issue, every founder feedback note gets logged against the agent that produced it. Over time this becomes the evidence base for prompt improvement.

**Implementation:** `agent_learnings` table — already partially seeded by the knowledge base `.md` files per agent. The formal table makes it queryable.

```sql
CREATE TABLE agent_learnings (
  id INTEGER PRIMARY KEY,
  agent_name TEXT NOT NULL,        -- 'will', 'emma', 'clara', etc.
  site_slug TEXT,                  -- null = applies portfolio-wide
  learning_type TEXT NOT NULL,     -- 'compliance_flag' | 'editorial_issue' | 'founder_feedback' | 'performance_signal'
  description TEXT NOT NULL,
  source TEXT,                     -- pipeline run ID or chat session ID
  applied_to_prompt INTEGER DEFAULT 0,  -- 0 = raw log, 1 = incorporated into KB
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Who reads it:**
- All agents — load their own learnings at session start (replaces static `.md` KB files, or supplements them)
- Optimisation Agent (Phase 5) — queries this table to propose prompt improvements

### Layer 4 — Content calendar (shared operational state)
Max currently has no persistent awareness of what the team is working on. The content calendar is the source of truth for what's planned, in-progress, and published per site. Max owns it. All agents read it.

**Implementation:** `content_calendar` table with planned publish dates, assigned agents, and current status. Rendered in the dashboard. Max updates it as jobs progress.

---

## Site config file (per site)

Every agent loads this before acting. Lives at `/sites/{site-slug}/config.json`.

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

## Phase 1 — MVP ✅ COMPLETE
**Completed:** ~60 seconds end-to-end. Site live at http://68.183.44.120:3284/

- [x] Hugo site live on VPS, auto-deploying from GitHub (build time ~22s)
- [x] SEO Agent (Sarah) produces valid content briefs
- [x] Writer Agent (Will) produces Hugo-ready markdown
- [x] Editor/Compliance Agent returns structured pass/fail JSON
- [x] Publisher Agent (Pete) opens PRs via GitHub API
- [x] End-to-end pipeline: topic → PR in ~60 seconds

---

## Phase 2 — Orchestration ✅ COMPLETE (exceeded original spec)
**Dashboard live at:** http://68.183.44.120:5050/

### What was planned — all done
- [x] Manager Agent (Max) — parses briefs, orchestrates full pipeline
- [x] Compliance fail routes back to Writer automatically (via Sam)
- [x] Pipeline logs every step with timestamps (SQLite)
- [x] Flask dashboard with run history and pending PRs
- [x] Founder only touches system to merge PRs and submit briefs

### Built beyond original spec
- [x] **Sub-Editor Agent (Sam)** — surgical fixes, frees Will for next job
- [x] **Agent personalities** — each agent has character, pushes back, disagrees
- [x] **Knowledge bases per agent** — persistent `.md` files with learned preferences
- [x] **Live chat with agents** — DM any agent from dashboard, feedback auto-saved to KB
- [x] **Agent-to-agent chat** — Emma & Clara discuss borderline issues, Messenger-style UI
- [x] **Group chat on failure** — all agents discuss, founder can jump in
- [x] **Spawn chats** — tell Emma to "chat with Sam", new thread opens
- [x] **Persistent sessions** — one Emma across pipeline, chat, and discussions
- [x] **Real-time broadcast** — founder feedback heard by all agents immediately
- [x] **Hybrid compliance** — programmatic checks + LLM for subjective review
- [x] **Job queue** — batch briefs, priority ordering, SQLite-backed
- [x] **Dashboard-triggered pipeline** — no CLI needed
- [x] **Scheduled content** — recurring briefs with cron

### Phase 2 state debt — address before Phase 3
These were identified as gaps that will cause scaling problems if not fixed before the portfolio expands:

- [ ] **Content register table** — Sarah currently briefs blind to what's already been covered
- [ ] **Agent learning log table** — KBs exist as `.md` files but aren't queryable or structured
- [ ] **Content calendar** — Max has no persistent view of what the team is working on
- [ ] **Pipeline run resumability** — failed runs restart from scratch, not from the failed step

These are not new features. They are the foundation Phase 3 depends on.

---

## Phase 3 — Portfolio (Next)
**Goal:** Launch Site B using the same agents, just a different config file.

### 3.0 State foundation (prerequisite — do this first)

Before adding a second site, implement the four database tables from the State & Memory Architecture section above. Without these, two sites will immediately create:
- Keyword cannibalisation across sites
- Agents with no awareness of portfolio-wide coverage
- Unqueryable KB data that can't feed the Optimisation Agent later
- No content calendar for Max to manage across both sites

**Deliverable:** Four new tables in SQLite. Dashboard panels for content register and calendar. All existing agents updated to read from and write to these tables before acting.

---

### 3.1 Multi-site repo structure

```
affiliate-portfolio/
├── agents/               ← shared agent codebase
│   ├── manager_agent.py  (Max)
│   ├── seo_agent.py      (Sarah)
│   ├── writer_agent.py   (Will)
│   ├── editor_agent.py   (Emma)
│   ├── sub_editor_agent.py (Sam)
│   ├── compliance_agent.py (Clara)
│   └── publisher_agent.py  (Pete)
├── pipeline/
│   ├── runner.py
│   └── scheduler.py
├── dashboard/            ← Flask app
├── db/
│   ├── schema.sql        ← single source of truth for all tables
│   └── affiliate.db
├── sites/
│   ├── site-a/
│   │   ├── config.json
│   │   └── [hugo site]
│   └── site-b/
│       ├── config.json
│       └── [hugo site]
└── shared/
    ├── compliance-rules/
    │   ├── ukgc.md
    │   ├── mga.md
    │   └── asa-cap.md
    └── agent-prompts/    ← system prompts as .md files, one per agent
```

---

### 3.2 Agent pooling

Multiple Writer instances run in parallel. Max allocates by site priority and content backlog depth.

- Job queue already exists (SQLite-backed) — extend with `site_slug` and `priority` fields
- Max pulls from queue, assigns to available Writer instance
- Content register prevents duplicate keyword briefs across sites

---

### 3.3 Department head agents

Each head manages their team and reports up to Max.

**Head of Content**
- Receives monthly content strategy from founder
- Breaks into weekly briefs per site, populates content calendar
- Monitors quality scores from Emma
- Flags if Will's output quality drops (reads agent learning log)

**Head of SEO**
- Sets keyword strategy per site (reads content register before planning)
- Reviews ranking reports
- Prioritises refresh vs new content
- Briefs KW Research Agent and On-site Agent

**Head of Tech**
- Reviews VPS health, build times, Core Web Vitals
- Briefs Developer Agent on site improvements
- Monitors Security Agent reports

**Head of Commercial**
- Reviews affiliate program performance
- Briefs Deals Agent on new programs to source
- Reviews Clara's compliance audit reports

---

### 3.4 Portfolio dashboard (v2)

Extend existing dashboard:
- All sites in one view — content backlog, pipeline health, last published date
- Content calendar view per site
- Content register with status filters
- Compliance flag summary per site
- Agent learning log with filter by agent and learning type
- Revenue signals per site (manual input now, automated Phase 4)

---

### Phase 3 success criteria
- [ ] State foundation tables live and all agents reading/writing to them
- [ ] Site B live using same agent codebase, different config
- [ ] Content pipelines running in parallel for both sites
- [ ] No keyword duplication across sites (enforced by content register)
- [ ] Department head agents producing weekly briefs without founder input
- [ ] Dashboard shows portfolio-level view with content calendar
- [ ] Site C requires only a new config file + Hugo setup

---

## Phase 4 — Commercial + SEO Intelligence
**Goal:** Agents monitor rankings, flag broken deals, surface revenue opportunities unprompted.

### 4.1 Commercial Agent
**Triggers:** Scheduled (daily)
- Affiliate link health (HTTP status of outbound links)
- Commission rate changes (compare against stored baseline)
- New affiliate program opportunities (web search)
- Revenue anomalies (significant conversion drop)

**Output:** Daily report to Head of Commercial + escalates critical issues to Max

---

### 4.2 Rank monitoring agent
**Integration:** Google Search Console API
- Track all target keywords per site (sourced from content register)
- Position drops >5 places in 7 days → flag to Head of SEO
- Position drops below page 2 → trigger content refresh pipeline
- Content not ranking within 90 days → flag for review
- Performance data written back to `content_register.performance_score`

---

### 4.3 Scheduled compliance audits
**Schedule:** Weekly crawl of full sitemap per site
- Fetch each live page, run against current ruleset
- If rules updated since last audit → re-check all pages
- Failed pages auto-trigger Editor → Compliance → Publisher pipeline
- Audit history stored in database (not just logged)

---

### 4.4 Analytics integration
Connect GA4 or Plausible — signals feed Max's prioritisation.

- Traffic drop >20% on a page → content review pipeline
- High traffic, low conversion → Commercial Agent review
- New organic traffic to untracked page → add to content register and tracker

---

### Phase 4 success criteria
- [ ] Commercial Agent flags broken affiliate links within 24 hours
- [ ] Rank drops trigger content refresh automatically
- [ ] Performance data flowing back into content register
- [ ] Compliance audit runs weekly across all live pages
- [ ] Analytics signals feeding Max's job queue prioritisation
- [ ] Founder receives weekly digest, not individual alerts

---

## Phase 5 — Full Product
**Goal:** Weekly brief from founder, everything else handled. New sites spin up in hours.

### 5.1 Autonomous weekly cycle

**Founder input:** One brief (~200 words) covering priorities, commercial changes, new direction.

**Max's week:**
- Monday: process brief, cascade to department heads, update content calendar
- Tue–Thu: pipeline executes, content produced and queued for review
- Friday: weekly digest — what published, what's pending, escalations, revenue signals

**Escalation rules (always comes to founder):**
- Compliance fail after 2 revisions
- New regulatory ruling not in existing ruleset
- Affiliate program dispute or negotiation
- New site launch decision
- Anything Max classifies as high-risk or ambiguous

---

### 5.2 Site spin-up automation
New site from config to live in under 4 hours.

**Developer Agent workflow:**
1. Read new `config.json`
2. Scaffold Hugo site from template
3. Create GitHub repo, push initial commit
4. Configure GitHub Actions workflow
5. Provision domain/DNS
6. Configure Nginx on VPS
7. Seed content register and calendar for new site
8. Run first compliance check on site template
9. Open PR for founder review and launch approval

---

### 5.3 Optimisation Agent (self-improving prompts)
> This is the agent that makes the system get better over time without founder intervention.

**Role:** Periodically reviews agent learning logs and performance data, proposes prompt improvements as PRs.

**Inputs:**
- `agent_learnings` table — recurring failure patterns per agent
- `content_register` — performance correlation with content parameters
- Compliance audit history — what issue types keep recurring

**Logic:**
- If Clara flags the same issue type more than N times in 30 days → propose addition to Will's system prompt
- If content above X word count consistently outperforms → update Sarah's brief template
- If a specific bonus description pattern keeps failing compliance → add explicit rule to Will's prompt

**Output:** PR to `/shared/agent-prompts/{agent}.md` with:
- What changed
- Why (evidence from learning log, with stats)
- Which runs it would have affected

**Safeguards:**
- Never auto-merges — always a PR for founder review
- Compliance Agent prompts require explicit founder approval (not just review)
- Changes are versioned — any prompt can be rolled back to any previous version
- Max gets a summary of all proposed changes in the weekly digest

---

### 5.4 Formal MCP server
Refactor Python scripts into a proper MCP server.

**What changes:**
- Agents become first-class MCP tools, callable from Claude Code, Claude Desktop, or any MCP client
- Tool definitions replace ad-hoc function calls
- Agent portability — Max can call Pete without knowing Pete is a Python script on a VPS

**What stays the same:**
- All system prompts and agent behaviour
- Site config structure
- Hugo + GitHub + VPS deployment stack
- Database schema and state layer

---

### 5.5 Agent memory upgrade (vector store)
Upgrade from SQLite queries to semantic retrieval for agent context loading.

**What this adds over the SQLite layer:**
- Will can retrieve *semantically similar* past content, not just exact keyword matches
- Clara can find compliance cases that *resemble* the current article, not just exact flag types
- Sarah can find keyword clusters that performed well in *similar niches*

**Implementation:** Chroma (self-hosted on VPS, no external dependency) or Pinecone
- SQLite remains the source of truth
- Vector store is the retrieval layer on top — embeddings generated from `content_register` and `agent_learnings`

---

## Tech stack — full picture

| Layer | Now (Phase 2) | Phase 3–4 | Phase 5 |
|---|---|---|---|
| Sites | Hugo on VPS | Hugo on VPS | Hugo on VPS |
| Hosting | DigitalOcean Droplet | DigitalOcean | DigitalOcean (scaled) |
| CI/CD | GitHub Actions (~22s) | GitHub Actions | GitHub Actions |
| Agent runtime | Python scripts | Python scripts | MCP server |
| AI model | OpenAI API | OpenAI API | OpenAI API (swappable) |
| Orchestration | Max + pipeline runner | Max + department heads | Max autonomous |
| Job queue | SQLite | SQLite → Redis | Redis |
| Dashboard | Flask + SQLite | Flask + SQLite | Flask + PostgreSQL |
| State / memory | `.md` KB files (per agent) | SQLite tables (structured) | SQLite + Chroma |
| Compliance rules | Markdown files in repo | Markdown + audit history | Versioned + auto-checked |
| Agent prompts | Hardcoded / `.md` files | `.md` files (versioned) | Optimisation Agent manages |
| Analytics | Manual | GA4 / Plausible API | Signals feed Max directly |
| Rank tracking | Manual | GSC API | Auto-triggers refresh pipeline |
| Affiliate monitoring | Manual | Commercial Agent | Commercial Agent (daily) |

---

## Agent index

| Agent | Name | Phase | Status | Reports to | Tools |
|---|---|---|---|---|---|
| Manager Agent | Max | 2 | **Live** | Founder | All agents, job queue |
| SEO Agent | Sarah | 1 | **Live** | Max | Web search, content register |
| Writer Agent | Will | 1 | **Live** | Max | Content register |
| Editor Agent | Emma | 2 | **Live** | Max | Agent learning log |
| Sub-Editor Agent | Sam | 2 | **Live** | Emma | None (LLM only) |
| Compliance Agent | Clara | 2 | **Live** | Max | Programmatic + LLM, audit history |
| Publisher Agent | Pete | 1 | **Live** | Max | GitHub API (PyGithub) |
| Head of Content | — | 3 | Planned | Max | Content calendar, pipeline runner |
| Head of SEO | — | 3 | Planned | Max | Rank data, GSC API |
| Head of Tech | — | 3 | Planned | Max | VPS metrics, GitHub API |
| Head of Commercial | — | 3 | Planned | Max | Affiliate APIs |
| KW Research Agent | — | 3 | Planned | Head of SEO | Web search, KW API |
| On-site Agent | — | 3 | Planned | Head of SEO | Hugo file access |
| Off-site Agent | — | 3 | Planned | Head of SEO | Web search |
| Developer Agent | — | 3 | Planned | Head of Tech | GitHub API, VPS SSH |
| Security Agent | — | 3 | Planned | Head of Tech | Scan tools, VPS |
| Commercial Agent | — | 4 | Planned | Head of Commercial | Affiliate APIs, HTTP checks |
| Deals Agent | — | 4 | Planned | Head of Commercial | Web search |
| Monetisation Agent | — | 4 | Planned | Head of Commercial | Analytics API |
| Optimisation Agent | — | 5 | Planned | Founder | Learning log, all agent prompts |

---

## What to build next (priority order)

**Before anything else in Phase 3:**

1. `content_register` table + update Sarah and Will to read/write it
2. `agent_learnings` table + migrate existing `.md` KB files into it
3. `content_calendar` table + give Max a view of it in the dashboard
4. Pipeline run resumability — add step/status/payload to run logs

**Then Phase 3 proper:**

5. Multi-site repo structure
6. Site B config file + Hugo setup
7. Department head agents
8. Portfolio dashboard view

---

## Notes for Claude Code

- Phase 1 and 2 are done. Do not touch the working pipeline unless fixing state debt.
- The four state tables in section "Phase 2 state debt" are the immediate priority.
- All agents must read `content_register` before acting. This is the single biggest leverage point.
- Agent system prompts live in `/shared/agent-prompts/` as `.md` files. Never hardcode them.
- Compliance Agent output is always JSON with explicit `compliance_pass: true/false`. Never change this.
- Publisher Agent (Pete) never auto-merges. PRs always require founder approval.
- When adding new agents, give them names and personalities. The team dynamic is a feature.
- Log everything to the database, not just to files. It needs to be queryable.
- The Optimisation Agent in Phase 5 depends entirely on the learning log being well-structured from Phase 3. Design the schema now.
