-- Add channel_company_domain and channel_source_type columns to video_snapshots table

ALTER TABLE video_snapshots
ADD COLUMN IF NOT EXISTS channel_company_domain VARCHAR(255),
ADD COLUMN IF NOT EXISTS channel_source_type VARCHAR(50);

-- Create index for better query performance on company domain lookups
CREATE INDEX IF NOT EXISTS idx_video_snapshots_channel_company_domain 
ON video_snapshots(channel_company_domain) 
WHERE channel_company_domain IS NOT NULL;

-- Add comment explaining the fields
COMMENT ON COLUMN video_snapshots.channel_company_domain IS 'AI-extracted company domain associated with the YouTube channel';
COMMENT ON COLUMN video_snapshots.channel_source_type IS 'Source type indicating how the domain was identified (e.g., direct_link, about_section, ai_inference)';
