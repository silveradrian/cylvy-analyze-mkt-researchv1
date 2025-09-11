-- Create table to store YouTube channel company associations
CREATE TABLE IF NOT EXISTS youtube_channel_companies (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    channel_id VARCHAR(255) UNIQUE NOT NULL,
    company_domain VARCHAR(255),
    company_name VARCHAR(500),
    source_type VARCHAR(50), -- OWNED, COMPETITOR, INFLUENCER, MEDIA, EDUCATIONAL, AGENCY, OTHER
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    extracted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_youtube_channel_companies_domain 
ON youtube_channel_companies(company_domain);

CREATE INDEX IF NOT EXISTS idx_youtube_channel_companies_source_type 
ON youtube_channel_companies(source_type);

CREATE INDEX IF NOT EXISTS idx_youtube_channel_companies_confidence 
ON youtube_channel_companies(confidence_score);

-- Add comment explaining the table
COMMENT ON TABLE youtube_channel_companies IS 'Stores AI-extracted company domain associations for YouTube channels';

-- Create company enrichment queue table
CREATE TABLE IF NOT EXISTS company_enrichment_queue (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    source_type VARCHAR(50), -- youtube_channel, serp_result, etc.
    source_id VARCHAR(500), -- Reference to source (channel_id, serp_id, etc.)
    confidence_score DECIMAL(3,2),
    priority VARCHAR(20) DEFAULT 'medium', -- high, medium, low
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for queue processing
CREATE INDEX IF NOT EXISTS idx_enrichment_queue_status 
ON company_enrichment_queue(status);

CREATE INDEX IF NOT EXISTS idx_enrichment_queue_priority 
ON company_enrichment_queue(priority, created_at);

-- Add comment
COMMENT ON TABLE company_enrichment_queue IS 'Queue for domains to be enriched via Cognism API';
