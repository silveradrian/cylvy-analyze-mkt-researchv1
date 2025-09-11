-- ================================
-- PIPELINE ROBUSTNESS ENHANCEMENTS
-- Phase 1: Critical Infrastructure for Resume, Retry, and State Management
-- ================================

-- 1. GRANULAR STATE TRACKING
-- ================================

-- Pipeline state tracking with resume capabilities
CREATE TABLE IF NOT EXISTS pipeline_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_execution_id UUID NOT NULL REFERENCES pipeline_executions(id),
    phase VARCHAR(50) NOT NULL,
    item_type VARCHAR(50) NOT NULL, -- 'keyword_region', 'domain', 'url', etc.
    item_identifier TEXT NOT NULL, -- composite key like 'keyword:region:type' or domain
    
    -- State management
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Error tracking
    last_error TEXT,
    error_category VARCHAR(50), -- 'recoverable', 'non_recoverable', 'rate_limit', etc.
    
    -- Progress tracking
    progress_data JSONB DEFAULT '{}', -- phase-specific progress details
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT pipeline_state_status CHECK (
        status IN ('pending', 'processing', 'completed', 'failed', 'skipped', 'queued')
    ),
    CONSTRAINT pipeline_state_unique UNIQUE(pipeline_execution_id, phase, item_identifier)
);

CREATE INDEX idx_pipeline_state_status ON pipeline_state(pipeline_execution_id, phase, status);
CREATE INDEX idx_pipeline_state_identifier ON pipeline_state(item_identifier);

-- 2. CIRCUIT BREAKER STATE
-- ================================

CREATE TABLE IF NOT EXISTS circuit_breakers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(100) NOT NULL UNIQUE,
    
    -- Circuit state
    state VARCHAR(20) NOT NULL DEFAULT 'closed',
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    
    -- Thresholds
    failure_threshold INTEGER DEFAULT 10,
    success_threshold INTEGER DEFAULT 5,
    timeout_seconds INTEGER DEFAULT 300, -- 5 minutes
    
    -- State timestamps
    last_failure_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    opened_at TIMESTAMP WITH TIME ZONE,
    half_opened_at TIMESTAMP WITH TIME ZONE,
    
    -- Statistics
    total_requests BIGINT DEFAULT 0,
    total_failures BIGINT DEFAULT 0,
    total_successes BIGINT DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT circuit_state CHECK (
        state IN ('closed', 'open', 'half_open')
    )
);

-- 3. PERSISTENT JOB QUEUE
-- ================================

CREATE TABLE IF NOT EXISTS job_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_name VARCHAR(50) NOT NULL, -- 'serp', 'enrichment', 'analysis'
    
    -- Job details
    job_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 0, -- higher = more important
    
    -- State management
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    -- Scheduling
    scheduled_for TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    locked_at TIMESTAMP WITH TIME ZONE,
    locked_by VARCHAR(100), -- worker ID
    
    -- Execution tracking
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    failed_at TIMESTAMP WITH TIME ZONE,
    
    -- Error handling
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    dead_letter BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT job_status CHECK (
        status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')
    )
);

CREATE INDEX idx_job_queue_pending ON job_queue(queue_name, status, priority DESC, scheduled_for)
    WHERE status = 'pending' AND NOT dead_letter;
CREATE INDEX idx_job_queue_locked ON job_queue(locked_at) WHERE locked_at IS NOT NULL;

-- 4. ERROR CATEGORIZATION
-- ================================

CREATE TABLE IF NOT EXISTS error_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_code VARCHAR(50) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    
    -- Error handling rules
    is_recoverable BOOLEAN DEFAULT TRUE,
    retry_strategy VARCHAR(50) DEFAULT 'exponential',
    max_retries INTEGER DEFAULT 3,
    base_delay_seconds INTEGER DEFAULT 1,
    max_delay_seconds INTEGER DEFAULT 300,
    
    -- Error patterns
    http_status_codes INTEGER[] DEFAULT '{}',
    error_patterns TEXT[] DEFAULT '{}', -- regex patterns
    
    -- Actions
    should_alert BOOLEAN DEFAULT FALSE,
    should_dead_letter BOOLEAN DEFAULT FALSE,
    fallback_action VARCHAR(100),
    
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default error categories
INSERT INTO error_categories (error_code, category, is_recoverable, retry_strategy, max_retries, base_delay_seconds, http_status_codes, description) VALUES
-- Recoverable errors
('RATE_LIMIT', 'recoverable', TRUE, 'exponential', 5, 60, '{429}', 'API rate limit exceeded'),
('TIMEOUT', 'recoverable', TRUE, 'exponential', 3, 5, '{}', 'Request timeout'),
('SERVICE_UNAVAILABLE', 'recoverable', TRUE, 'exponential', 4, 10, '{503}', 'Service temporarily unavailable'),
('GATEWAY_ERROR', 'recoverable', TRUE, 'exponential', 3, 5, '{502,504}', 'Gateway errors'),
('NETWORK_ERROR', 'recoverable', TRUE, 'exponential', 3, 2, '{}', 'Network connectivity issues'),

-- Non-recoverable errors
('UNAUTHORIZED', 'non_recoverable', FALSE, 'none', 0, 0, '{401}', 'Authentication failed'),
('FORBIDDEN', 'non_recoverable', FALSE, 'none', 0, 0, '{403}', 'Access forbidden'),
('NOT_FOUND', 'non_recoverable', FALSE, 'none', 0, 0, '{404}', 'Resource not found'),
('BAD_REQUEST', 'non_recoverable', FALSE, 'none', 0, 0, '{400}', 'Invalid request'),
('UNPROCESSABLE', 'non_recoverable', FALSE, 'none', 0, 0, '{422}', 'Unprocessable entity'),

-- Partial success errors
('PARTIAL_CONTENT', 'degraded', TRUE, 'linear', 2, 5, '{206}', 'Partial content received'),
('INCOMPLETE_DATA', 'degraded', TRUE, 'linear', 2, 10, '{}', 'Data partially complete');

-- 5. RETRY TRACKING
-- ================================

CREATE TABLE IF NOT EXISTS retry_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL, -- 'pipeline_state', 'job_queue'
    entity_id UUID NOT NULL,
    
    -- Attempt details
    attempt_number INTEGER NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Result
    success BOOLEAN,
    error_code VARCHAR(50),
    error_message TEXT,
    response_data JSONB,
    
    -- Retry metadata
    retry_delay_seconds INTEGER,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_retry_history_entity ON retry_history(entity_type, entity_id);

-- 6. SERVICE HEALTH METRICS
-- ================================

CREATE TABLE IF NOT EXISTS service_health_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    
    -- Time window
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Metrics
    request_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    timeout_count INTEGER DEFAULT 0,
    
    -- Performance
    avg_response_time_ms NUMERIC(10,2),
    p95_response_time_ms NUMERIC(10,2),
    p99_response_time_ms NUMERIC(10,2),
    
    -- Error breakdown
    error_breakdown JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(service_name, metric_type, window_start)
);

CREATE INDEX idx_service_health_window ON service_health_metrics(service_name, window_start DESC);

-- 7. CHECKPOINT MANAGEMENT
-- ================================

CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_execution_id UUID NOT NULL REFERENCES pipeline_executions(id),
    phase VARCHAR(50) NOT NULL,
    checkpoint_name VARCHAR(100) NOT NULL,
    
    -- Checkpoint data
    state_data JSONB NOT NULL,
    items_processed INTEGER DEFAULT 0,
    items_total INTEGER,
    
    -- Timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(pipeline_execution_id, phase, checkpoint_name)
);

-- Helper functions
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at
CREATE TRIGGER update_pipeline_state_updated_at BEFORE UPDATE ON pipeline_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_circuit_breakers_updated_at BEFORE UPDATE ON circuit_breakers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_queue_updated_at BEFORE UPDATE ON job_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_error_categories_updated_at BEFORE UPDATE ON error_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Verification
SELECT 
    'PIPELINE ROBUSTNESS SCHEMA CREATED' as status,
    COUNT(*) as tables_created
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'pipeline_state', 
    'circuit_breakers', 
    'job_queue', 
    'error_categories',
    'retry_history',
    'service_health_metrics',
    'pipeline_checkpoints'
);
