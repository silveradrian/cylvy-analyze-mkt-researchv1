-- Add expires_at column to company_profiles_cache table
ALTER TABLE company_profiles_cache 
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;

-- Set default expiration to 30 days from created_at for existing records
UPDATE company_profiles_cache 
SET expires_at = created_at + INTERVAL '30 days'
WHERE expires_at IS NULL;

-- Make expires_at NOT NULL for future inserts
ALTER TABLE company_profiles_cache 
ALTER COLUMN expires_at SET NOT NULL;

-- Create index for efficient cleanup of expired cache entries
CREATE INDEX IF NOT EXISTS idx_company_profiles_cache_expires_at 
ON company_profiles_cache(expires_at);

-- Add comment explaining the column
COMMENT ON COLUMN company_profiles_cache.expires_at IS 'Timestamp when this cache entry expires and should be refreshed';
