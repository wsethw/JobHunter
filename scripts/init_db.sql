CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(300) NOT NULL,
    company VARCHAR(200),
    location VARCHAR(200),
    stack JSONB DEFAULT '[]'::jsonb,
    link VARCHAR(500) UNIQUE NOT NULL,
    source VARCHAR(100) NOT NULL,
    published_at TIMESTAMPTZ,
    seniority VARCHAR(50),
    score DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs (source);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs (score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_stack_gin ON jobs USING GIN (stack);

CREATE TABLE IF NOT EXISTS execution_logs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    sources_scraped INTEGER DEFAULT 0,
    jobs_found INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_started_at ON execution_logs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_logs_status ON execution_logs (status);
