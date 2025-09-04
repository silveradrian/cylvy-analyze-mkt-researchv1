-- Add keyword metrics tracking to pipeline executions
-- Migration: 007_add_keyword_metrics_tracking.sql

-- Add keywords_with_metrics column to pipeline_executions table
ALTER TABLE pipeline_executions 
ADD COLUMN IF NOT EXISTS keywords_with_metrics INTEGER DEFAULT 0;

-- Add comment for documentation
COMMENT ON COLUMN pipeline_executions.keywords_with_metrics IS 'Number of keywords that received Google Ads historical metrics during this pipeline execution';

-- Create index for querying pipelines by keyword metrics status
CREATE INDEX IF NOT EXISTS idx_pipeline_executions_keyword_metrics 
ON pipeline_executions(keywords_with_metrics);

-- Add keyword metrics success rate view for monitoring
CREATE OR REPLACE VIEW pipeline_keyword_metrics_performance AS
SELECT 
    DATE(started_at) as execution_date,
    COUNT(*) as total_pipelines,
    AVG(keywords_processed) as avg_keywords_per_pipeline,
    AVG(keywords_with_metrics) as avg_keywords_with_metrics_per_pipeline,
    SUM(keywords_with_metrics) as total_keywords_enriched,
    COUNT(*) FILTER (WHERE keywords_with_metrics > 0) as pipelines_with_keyword_metrics,
    ROUND(
        (AVG(keywords_with_metrics::DECIMAL) / NULLIF(AVG(keywords_processed), 0)) * 100, 
        2
    ) as keyword_metrics_success_rate_percent
FROM pipeline_executions 
WHERE started_at >= CURRENT_DATE - INTERVAL '30 days'
  AND keywords_processed > 0
GROUP BY DATE(started_at)
ORDER BY execution_date DESC;

-- Add comment for the view
COMMENT ON VIEW pipeline_keyword_metrics_performance IS 'Daily metrics showing Google Ads keyword metrics enrichment performance across pipeline executions';

