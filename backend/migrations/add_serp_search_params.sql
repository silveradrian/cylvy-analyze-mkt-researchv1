-- Add search parameter fields to serp_results table
-- These fields help track exactly how each search was performed

ALTER TABLE serp_results 
ADD COLUMN IF NOT EXISTS device VARCHAR(20),
ADD COLUMN IF NOT EXISTS google_domain VARCHAR(50),
ADD COLUMN IF NOT EXISTS language_code VARCHAR(10),
ADD COLUMN IF NOT EXISTS time_period VARCHAR(50),
ADD COLUMN IF NOT EXISTS news_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS query_displayed TEXT,
ADD COLUMN IF NOT EXISTS time_taken_displayed VARCHAR(50);

-- Add indexes for commonly filtered fields
CREATE INDEX IF NOT EXISTS idx_serp_device ON serp_results(device) WHERE device IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_serp_time_period ON serp_results(time_period) WHERE time_period IS NOT NULL;

-- Add comments to document the fields
COMMENT ON COLUMN serp_results.device IS 'Device type used for search: desktop, mobile, tablet';
COMMENT ON COLUMN serp_results.google_domain IS 'Google domain used: google.com, google.co.uk, etc';
COMMENT ON COLUMN serp_results.language_code IS 'Language code (hl parameter) used for search';
COMMENT ON COLUMN serp_results.time_period IS 'Time filter applied: past 24h, past week, past month, etc';
COMMENT ON COLUMN serp_results.news_type IS 'News type filter: blogs, press releases, general news';
COMMENT ON COLUMN serp_results.query_displayed IS 'Normalized query as displayed by Google';
COMMENT ON COLUMN serp_results.time_taken_displayed IS 'Search time as reported by Google';


