-- Create table for storing YouTube channel company information
CREATE TABLE IF NOT EXISTS youtube_channel_companies (
    channel_id VARCHAR(255) PRIMARY KEY,
    company_domain VARCHAR(255),
    company_name VARCHAR(255),
    source_type VARCHAR(50) DEFAULT 'OTHER',
    confidence_score DECIMAL(3,2) DEFAULT 0.5,
    extracted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indices for efficient lookups
CREATE INDEX IF NOT EXISTS idx_channel_companies_domain ON youtube_channel_companies(company_domain);
CREATE INDEX IF NOT EXISTS idx_channel_companies_source ON youtube_channel_companies(source_type);
CREATE INDEX IF NOT EXISTS idx_channel_companies_confidence ON youtube_channel_companies(confidence_score);

-- Create table for company enrichment queue if not exists
CREATE TABLE IF NOT EXISTS company_enrichment_queue (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE,
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    confidence_score DECIMAL(3,2),
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for queue processing
CREATE INDEX IF NOT EXISTS idx_enrichment_queue_status ON company_enrichment_queue(status, priority);
