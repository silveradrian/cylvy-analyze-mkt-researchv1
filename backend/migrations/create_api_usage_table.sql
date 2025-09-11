-- Create api_usage table for tracking API quota usage
CREATE TABLE IF NOT EXISTS api_usage (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    api_name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(255),
    operation VARCHAR(100),
    quota_used INTEGER DEFAULT 1,
    quota_limit INTEGER,
    reset_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_api_usage_api_name ON api_usage(api_name);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_reset_at ON api_usage(reset_at);

-- Add comment
COMMENT ON TABLE api_usage IS 'Tracks API usage and quota consumption for external services';
