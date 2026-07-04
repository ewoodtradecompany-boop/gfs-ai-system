-- GFS CRM Schema — Stage 0
-- Applied automatically on first `docker compose up` via init script

CREATE TABLE IF NOT EXISTS contacts (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT,
    company     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meetings (
    id              SERIAL PRIMARY KEY,
    contact_id      INT REFERENCES contacts(id),  -- nullable: meeting may not have a linked contact yet
    transcript_raw  TEXT,
    summary         TEXT,
    action_items    JSONB,
    sentiment       TEXT CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    next_step       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log for every agent action — required by CLAUDE.md non-negotiables
CREATE TABLE IF NOT EXISTS agent_actions (
    id              SERIAL PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    model_used      TEXT,
    input_summary   TEXT,
    output_summary  TEXT,
    cost_usd        NUMERIC(10, 6) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
