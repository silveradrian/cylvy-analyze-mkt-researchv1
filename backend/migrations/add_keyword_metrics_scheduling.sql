-- Add keyword metrics scheduling support

-- Create table to track keyword metrics jobs
CREATE TABLE IF NOT EXISTS keyword_metrics_jobs (
    id VARCHAR(255) PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL, -- 'scheduled_monthly', 'manual', 'upload'
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_keywords INTEGER DEFAULT 0,
    keywords_processed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for keyword metrics jobs
CREATE INDEX IF NOT EXISTS idx_metrics_jobs_status ON keyword_metrics_jobs(status);
CREATE INDEX IF NOT EXISTS idx_metrics_jobs_type ON keyword_metrics_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_metrics_jobs_created ON keyword_metrics_jobs(created_at);

-- Add metrics fields to keywords table if they don't exist
ALTER TABLE keywords 
ADD COLUMN IF NOT EXISTS competition_index DECIMAL(5,4),
ADD COLUMN IF NOT EXISTS low_bid_micros BIGINT,
ADD COLUMN IF NOT EXISTS high_bid_micros BIGINT,
ADD COLUMN IF NOT EXISTS metrics_updated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Add index for active keywords
CREATE INDEX IF NOT EXISTS idx_keywords_active ON keywords(is_active);
CREATE INDEX IF NOT EXISTS idx_keywords_metrics_updated ON keywords(metrics_updated_at);

-- Update historical_keyword_metrics to ensure it has all needed columns
ALTER TABLE historical_keyword_metrics
ADD COLUMN IF NOT EXISTS competition_index DECIMAL(5,4),
ADD COLUMN IF NOT EXISTS low_top_of_page_bid_micros BIGINT,
ADD COLUMN IF NOT EXISTS high_top_of_page_bid_micros BIGINT;
