-- Clean up redundant company profile fields after simplification

-- Drop the view that depends on company_profile
DROP VIEW IF EXISTS company_analysis_context;

-- Drop the function that depends on company_profile
DROP FUNCTION IF EXISTS get_company_ai_context(UUID);

-- Drop the constraint that uses validate_company_profile
ALTER TABLE client_config DROP CONSTRAINT IF EXISTS valid_company_profile;

-- Drop the validation function
DROP FUNCTION IF EXISTS validate_company_profile(jsonb);

-- Drop the comprehensive company_profile column (no longer needed with simplified approach)
ALTER TABLE client_config DROP COLUMN IF EXISTS company_profile;

-- Drop the industry column (not used in simplified version)
ALTER TABLE client_config DROP COLUMN IF EXISTS industry;

-- Add comments to document the simplified structure
COMMENT ON TABLE client_config IS 'Simplified client configuration with basic company info and competitors';
COMMENT ON COLUMN client_config.company_name IS 'Company display name';
COMMENT ON COLUMN client_config.company_domain IS 'Primary company domain';
COMMENT ON COLUMN client_config.legal_name IS 'Full legal name of the company';
COMMENT ON COLUMN client_config.additional_domains IS 'Additional domains owned by the company';
COMMENT ON COLUMN client_config.competitors IS 'Competitor companies with their domains';
COMMENT ON COLUMN client_config.description IS 'Company description (max 1000 words) for AI context';

