-- Add additional fields to serp_results table for CSV data
-- These fields accommodate the new CSV format from Scale SERP

-- Add source field for news results (publisher name)
ALTER TABLE serp_results 
ADD COLUMN IF NOT EXISTS source VARCHAR(255);

-- Add published_date for content publication date
ALTER TABLE serp_results 
ADD COLUMN IF NOT EXISTS published_date TIMESTAMP;

-- Add video_length for video duration
ALTER TABLE serp_results 
ADD COLUMN IF NOT EXISTS video_length VARCHAR(50);

-- Add total_results to track how many results Google reported
ALTER TABLE serp_results 
ADD COLUMN IF NOT EXISTS total_results BIGINT;

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_serp_source ON serp_results(source) WHERE source IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_serp_published_date ON serp_results(published_date DESC) WHERE published_date IS NOT NULL;

-- Add comments to document the fields
COMMENT ON COLUMN serp_results.source IS 'News publisher or content source name';
COMMENT ON COLUMN serp_results.published_date IS 'Date when the content was published';
COMMENT ON COLUMN serp_results.video_length IS 'Video duration in format like "4:32" for videos';
COMMENT ON COLUMN serp_results.total_results IS 'Total number of results Google reported for this search';


