-- Enhanced Historical Keyword Metrics for Multi-Country Google Ads Integration
-- Migration: 008_enhance_historical_keyword_metrics.sql

-- First, rename the existing table to preserve data
ALTER TABLE historical_keyword_metrics RENAME TO historical_keyword_metrics_old;

-- Create enhanced historical keyword metrics table
CREATE TABLE historical_keyword_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,
    keyword_id UUID NOT NULL REFERENCES keywords(id),
    keyword_text VARCHAR(255) NOT NULL,
    
    -- Country/Geo Support (CRITICAL for multi-country clients)
    country_code VARCHAR(10) NOT NULL,
    geo_target_id VARCHAR(20),
    
    -- Data Source Tracking
    source VARCHAR(50) NOT NULL DEFAULT 'SERP', -- 'SERP', 'GOOGLE_ADS', 'MANUAL'
    
    -- Pipeline Integration
    pipeline_execution_id UUID REFERENCES pipeline_executions(id),
    calculation_frequency VARCHAR(20) DEFAULT 'monthly', -- 'daily', 'weekly', 'monthly'
    
    -- SERP Performance Metrics (preserved from old table)
    total_results INTEGER DEFAULT 0,
    avg_position DECIMAL(4,1) DEFAULT 0,
    top_10_results INTEGER DEFAULT 0,
    organic_results INTEGER DEFAULT 0,
    news_results INTEGER DEFAULT 0,
    video_results INTEGER DEFAULT 0,
    estimated_monthly_traffic INTEGER DEFAULT 0,
    
    -- Google Ads Historical Metrics (NEW)
    avg_monthly_searches INTEGER DEFAULT 0,
    competition_level VARCHAR(20), -- 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'
    low_top_of_page_bid_micros BIGINT DEFAULT 0,
    high_top_of_page_bid_micros BIGINT DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Enhanced constraints for multi-country support
    UNIQUE(snapshot_date, keyword_id, country_code, source),
    
    -- Ensure valid values
    CONSTRAINT chk_competition_level CHECK (
        competition_level IS NULL OR 
        competition_level IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')
    ),
    CONSTRAINT chk_source CHECK (
        source IN ('SERP', 'GOOGLE_ADS', 'MANUAL', 'COMBINED')
    ),
    CONSTRAINT chk_frequency CHECK (
        calculation_frequency IN ('daily', 'weekly', 'monthly', 'ad_hoc')
    )
);

-- Migrate data from old table (SERP metrics only, no country data available)
INSERT INTO historical_keyword_metrics (
    snapshot_date, keyword_id, keyword_text, country_code, source,
    total_results, avg_position, top_10_results, organic_results, 
    news_results, video_results, estimated_monthly_traffic, created_at
)
SELECT 
    snapshot_date, keyword_id, keyword_text, 
    'US' as country_code,  -- Default to US for historical data
    'SERP' as source,
    total_results, avg_position, top_10_results, organic_results,
    news_results, video_results, estimated_monthly_traffic, created_at
FROM historical_keyword_metrics_old;

-- Create optimized indexes for multi-country queries
CREATE INDEX idx_historical_keyword_metrics_snapshot_country 
ON historical_keyword_metrics(snapshot_date DESC, country_code);

CREATE INDEX idx_historical_keyword_metrics_keyword_country_source 
ON historical_keyword_metrics(keyword_id, country_code, source);

CREATE INDEX idx_historical_keyword_metrics_pipeline 
ON historical_keyword_metrics(pipeline_execution_id);

CREATE INDEX idx_historical_keyword_metrics_frequency 
ON historical_keyword_metrics(calculation_frequency, snapshot_date DESC);

-- Create TimescaleDB hypertable for time-series optimization (if available)
DO $$
BEGIN
    PERFORM create_hypertable('historical_keyword_metrics', 'snapshot_date', if_not_exists => TRUE);
    RAISE NOTICE 'Created TimescaleDB hypertable for historical_keyword_metrics';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'TimescaleDB not available, using regular table for historical_keyword_metrics';
END
$$;

-- Create views for easy querying

-- 1. Latest metrics per keyword per country
CREATE OR REPLACE VIEW latest_keyword_metrics_by_country AS
SELECT DISTINCT ON (keyword_id, country_code) 
    keyword_id,
    keyword_text,
    country_code,
    source,
    avg_monthly_searches,
    competition_level,
    avg_position,
    estimated_monthly_traffic,
    snapshot_date
FROM historical_keyword_metrics
ORDER BY keyword_id, country_code, snapshot_date DESC;

-- 2. Pipeline keyword metrics summary
CREATE OR REPLACE VIEW pipeline_keyword_metrics_summary AS
SELECT 
    pe.id as pipeline_id,
    pe.started_at,
    pe.status,
    COUNT(DISTINCT hkm.keyword_id) as unique_keywords,
    COUNT(DISTINCT hkm.country_code) as countries_processed,
    COUNT(*) FILTER (WHERE hkm.source = 'GOOGLE_ADS') as google_ads_metrics,
    COUNT(*) FILTER (WHERE hkm.source = 'SERP') as serp_metrics,
    AVG(hkm.avg_monthly_searches) FILTER (WHERE hkm.avg_monthly_searches > 0) as avg_search_volume,
    COUNT(*) FILTER (WHERE hkm.competition_level = 'HIGH') as high_competition_keywords
FROM pipeline_executions pe
LEFT JOIN historical_keyword_metrics hkm ON pe.id = hkm.pipeline_execution_id
GROUP BY pe.id, pe.started_at, pe.status
ORDER BY pe.started_at DESC;

-- 3. Monthly keyword performance trends
CREATE OR REPLACE VIEW monthly_keyword_trends AS
SELECT 
    DATE_TRUNC('month', snapshot_date) as month,
    keyword_text,
    country_code,
    source,
    AVG(avg_monthly_searches) as avg_monthly_searches,
    AVG(avg_position) as avg_position,
    AVG(estimated_monthly_traffic) as avg_estimated_traffic,
    COUNT(*) as snapshots_count
FROM historical_keyword_metrics
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', snapshot_date), keyword_text, country_code, source
ORDER BY month DESC, avg_monthly_searches DESC;

-- Drop old table after successful migration
DROP TABLE IF EXISTS historical_keyword_metrics_old;

-- Add comments for documentation
COMMENT ON TABLE historical_keyword_metrics IS 'Historical keyword performance metrics from SERP analysis and Google Ads API, tracked per country and pipeline execution';
COMMENT ON COLUMN historical_keyword_metrics.country_code IS 'Country code (US, UK, DE, etc.) for geo-specific metrics';
COMMENT ON COLUMN historical_keyword_metrics.source IS 'Data source: SERP (from search results), GOOGLE_ADS (from API), MANUAL (user input)';
COMMENT ON COLUMN historical_keyword_metrics.pipeline_execution_id IS 'Links metrics to specific pipeline run for tracking';
COMMENT ON COLUMN historical_keyword_metrics.avg_monthly_searches IS 'Average monthly search volume from Google Ads API';
COMMENT ON COLUMN historical_keyword_metrics.competition_level IS 'Competition level from Google Ads: HIGH, MEDIUM, LOW';

