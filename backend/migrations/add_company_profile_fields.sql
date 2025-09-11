-- Add new fields to client_config table for simplified company profile

-- Add legal_name field
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS legal_name VARCHAR(500);

-- Add additional_domains as array field
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS additional_domains TEXT[] DEFAULT '{}';

-- Add competitors as JSONB field (array of objects with name and domains)
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS competitors JSONB DEFAULT '[]';

-- Add index on additional_domains for faster lookups
CREATE INDEX IF NOT EXISTS idx_client_config_additional_domains ON client_config USING GIN(additional_domains);

-- Add index on competitors for faster searches
CREATE INDEX IF NOT EXISTS idx_client_config_competitors ON client_config USING GIN(competitors);

-- Add comments
COMMENT ON COLUMN client_config.legal_name IS 'Full legal name of the company';
COMMENT ON COLUMN client_config.additional_domains IS 'Additional domains owned by the company beyond the primary domain';
COMMENT ON COLUMN client_config.competitors IS 'Array of competitor objects containing name and domains';

