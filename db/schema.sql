-- Affiliate Factory — State Foundation
-- Single source of truth for all database tables.

-- Existing tables (created by db.py and job_queue.py) are kept as-is.
-- This file adds the four state foundation tables from roadmap v2.

-----------------------------------------------------------
-- 1. Content Register
-- One row per piece of content (briefed, drafted, or published).
-- Every agent reads this before acting.
-----------------------------------------------------------
CREATE TABLE IF NOT EXISTS content_register (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_slug TEXT NOT NULL,
    keyword TEXT NOT NULL,
    slug TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'briefed',  -- briefed | drafted | in_review | published | refresh_needed
    content_type TEXT DEFAULT 'guide',        -- guide | review | bonus
    published_date TEXT,
    word_count INTEGER,
    compliance_pass INTEGER,
    performance_score REAL,                   -- populated by rank monitoring (Phase 4)
    pr_url TEXT,
    run_id INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_content_register_keyword ON content_register(keyword);
CREATE INDEX IF NOT EXISTS idx_content_register_site ON content_register(site_slug);
CREATE INDEX IF NOT EXISTS idx_content_register_status ON content_register(status);

-----------------------------------------------------------
-- 2. Agent Learning Log
-- Every compliance flag, editorial issue, founder feedback note.
-- Raw material for the Optimisation Agent in Phase 5.
-----------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,                 -- 'sarah', 'will', 'emma', 'clara', 'sam', 'max', 'pete'
    site_slug TEXT,                           -- null = applies portfolio-wide
    learning_type TEXT NOT NULL,              -- compliance_flag | editorial_issue | founder_feedback | performance_signal | agent_discussion
    description TEXT NOT NULL,
    source TEXT,                              -- pipeline run ID, chat session ID, or thread ID
    severity TEXT DEFAULT 'info',             -- info | warning | critical
    applied_to_prompt INTEGER DEFAULT 0,      -- 0 = raw log, 1 = incorporated into KB/prompt
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_learnings_agent ON agent_learnings(agent_name);
CREATE INDEX IF NOT EXISTS idx_learnings_type ON agent_learnings(learning_type);

-----------------------------------------------------------
-- 3. Content Calendar
-- What's planned, in-progress, and published per site.
-- Max owns this. All agents read it.
-----------------------------------------------------------
CREATE TABLE IF NOT EXISTS content_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_slug TEXT NOT NULL,
    keyword TEXT NOT NULL,
    content_type TEXT DEFAULT 'guide',
    planned_date TEXT,                        -- when it should publish
    status TEXT NOT NULL DEFAULT 'planned',   -- planned | in_progress | in_review | published | blocked
    assigned_to TEXT,                         -- agent or 'will', 'sam', etc.
    priority TEXT DEFAULT 'medium',           -- high | medium | low
    job_id INTEGER,                           -- link to jobs table
    content_register_id INTEGER,              -- link to content_register
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_site ON content_calendar(site_slug);
CREATE INDEX IF NOT EXISTS idx_calendar_status ON content_calendar(status);
CREATE INDEX IF NOT EXISTS idx_calendar_date ON content_calendar(planned_date);

-----------------------------------------------------------
-- 4. Pipeline Run Steps (resumability)
-- Extends existing runs table with step-level state.
-- If a run crashes, Max can resume from the last completed step.
-----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    job_id INTEGER,
    step_name TEXT NOT NULL,                  -- seo_brief | first_draft | compliance_1 | editorial_1 | sub_edit_1 | publish
    step_order INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | running | done | failed | skipped
    agent TEXT NOT NULL,
    input_payload TEXT,                        -- JSON: what was sent to the agent
    output_payload TEXT,                       -- JSON: what came back
    error TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_steps_run ON pipeline_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_steps_status ON pipeline_steps(status);
