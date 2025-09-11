-- Create table to track webhook batch completions
CREATE TABLE IF NOT EXISTS webhook_batch_completions (
    batch_id VARCHAR(255) PRIMARY KEY,
    batch_name VARCHAR(500),
    content_type VARCHAR(50),
    result_set_id INTEGER,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id UUID,
    success BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for querying
CREATE INDEX IF NOT EXISTS idx_webhook_completions_content_type ON webhook_batch_completions(content_type);
CREATE INDEX IF NOT EXISTS idx_webhook_completions_completed_at ON webhook_batch_completions(completed_at);
CREATE INDEX IF NOT EXISTS idx_webhook_completions_pipeline_id ON webhook_batch_completions(pipeline_id);

-- Create table for pipeline schedules if not exists
CREATE TABLE IF NOT EXISTS pipeline_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    content_schedules JSONB NOT NULL DEFAULT '[]',
    keywords JSONB,
    regions JSONB NOT NULL DEFAULT '["US", "UK"]',
    max_concurrent_executions INTEGER DEFAULT 1,
    notification_emails JSONB,
    notify_on_completion BOOLEAN DEFAULT TRUE,
    notify_on_error BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_executed_at TIMESTAMP,
    next_execution_at TIMESTAMP
);

-- Create indexes for pipeline schedules
CREATE INDEX IF NOT EXISTS idx_pipeline_schedules_active ON pipeline_schedules(is_active);
CREATE INDEX IF NOT EXISTS idx_pipeline_schedules_next_execution ON pipeline_schedules(next_execution_at);

-- Create table for schedule executions
CREATE TABLE IF NOT EXISTS schedule_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID REFERENCES pipeline_schedules(id) ON DELETE CASCADE,
    pipeline_id UUID,
    content_types JSONB NOT NULL DEFAULT '[]',
    scheduled_for TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    results_summary JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for schedule executions
CREATE INDEX IF NOT EXISTS idx_schedule_executions_schedule_id ON schedule_executions(schedule_id);
CREATE INDEX IF NOT EXISTS idx_schedule_executions_status ON schedule_executions(status);
CREATE INDEX IF NOT EXISTS idx_schedule_executions_scheduled_for ON schedule_executions(scheduled_for);
