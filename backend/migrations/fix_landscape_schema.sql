-- Fix missing columns for landscape DSI calculation

-- 1. Add result_type to serp_results if not exists
ALTER TABLE serp_results
ADD COLUMN IF NOT EXISTS result_type VARCHAR(50) DEFAULT 'organic';

-- Update existing records to have organic as default
UPDATE serp_results 
SET result_type = 'organic' 
WHERE result_type IS NULL;

-- 2. Add jtbd_alignment_score to content_analysis if not exists
ALTER TABLE content_analysis
ADD COLUMN IF NOT EXISTS jtbd_alignment_score NUMERIC DEFAULT 0.0;

-- 3. Add persona_scores to content_analysis if not exists
ALTER TABLE content_analysis
ADD COLUMN IF NOT EXISTS persona_scores JSONB DEFAULT '{}'::jsonb;

-- 4. Add content_classification to content_analysis if not exists
ALTER TABLE content_analysis
ADD COLUMN IF NOT EXISTS content_classification VARCHAR(50);

-- 5. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_serp_results_result_type ON serp_results(result_type);
CREATE INDEX IF NOT EXISTS idx_content_analysis_jtbd_score ON content_analysis(jtbd_alignment_score);
CREATE INDEX IF NOT EXISTS idx_content_analysis_classification ON content_analysis(content_classification);

-- 6. Ensure companies table exists with required columns
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    industry VARCHAR(100),
    company_size VARCHAR(50),
    headquarters VARCHAR(255),
    founded_year INTEGER,
    website_url VARCHAR(500),
    linkedin_url VARCHAR(500),
    is_competitor BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Create index for company domain lookups
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_is_competitor ON companies(is_competitor);

-- 8. Insert some basic company data if table is empty
INSERT INTO companies (name, domain, is_competitor)
SELECT 'Finastra', 'finastra.com', false
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE domain = 'finastra.com');

INSERT INTO companies (name, domain, is_competitor)
SELECT 'Temenos', 'temenos.com', true
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE domain = 'temenos.com');

INSERT INTO companies (name, domain, is_competitor)
SELECT 'FIS', 'fisglobal.com', true
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE domain = 'fisglobal.com');

INSERT INTO companies (name, domain, is_competitor)
SELECT 'Jack Henry', 'jackhenry.com', true
WHERE NOT EXISTS (SELECT 1 FROM companies WHERE domain = 'jackhenry.com');

