-- Database initialization script
-- Creates required extensions and base schema

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create queue table
CREATE TABLE IF NOT EXISTS queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    question_embedding VECTOR(768),
    domain VARCHAR(50),
    software_version VARCHAR(20),
    stack_pack VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    reference_count INT NOT NULL DEFAULT 1,
    requester_session_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    worker_id VARCHAR(100),
    retry_count INT NOT NULL DEFAULT 0,
    error_log JSONB,
    result_entry_id VARCHAR(200),
    needs_review_reason TEXT,
    CONSTRAINT status_check CHECK (status IN ('pending', 'researching', 'needs_review', 'completed', 'failed', 'discarded'))
);

-- Queue indexes
CREATE INDEX IF NOT EXISTS idx_queue_status_pending ON queue(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_queue_created ON queue(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_queue_embedding ON queue USING ivfflat (question_embedding vector_cosine_ops);

-- Dead letter queue
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    LIKE queue INCLUDING ALL,
    moved_to_dlq_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    final_error JSONB
);

-- Worker heartbeats
CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker_id VARCHAR(100) PRIMARY KEY,
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_task_id UUID,
    tasks_completed INT NOT NULL DEFAULT 0,
    tasks_failed INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
);

-- Entry provenance
CREATE TABLE IF NOT EXISTS entry_provenance (
    entry_id VARCHAR(200) PRIMARY KEY,
    source_queue_ids UUID[] NOT NULL,
    research_cost_usd DECIMAL(10, 4),
    tokens_consumed JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    promoted_at TIMESTAMPTZ
);

-- Metrics log
CREATE TABLE IF NOT EXISTS metrics_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    domain VARCHAR(50),
    entry_id VARCHAR(200),
    software_version VARCHAR(20),
    queue_id UUID,
    stack_pack VARCHAR(50),
    is_cached_hit BOOLEAN NOT NULL DEFAULT FALSE,
    model_name VARCHAR(100),
    confidence FLOAT,
    latency_ms FLOAT,
    tokens_input INT,
    tokens_output INT,
    extra_data JSONB
);

-- Metrics indexes
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_event_type ON metrics_log(event_type);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO kbpro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kbpro;

