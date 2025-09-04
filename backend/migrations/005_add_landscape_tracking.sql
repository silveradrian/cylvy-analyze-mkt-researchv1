-- Add landscape calculation tracking to pipeline executions
-- Migration: 005_add_landscape_tracking.sql

-- Add landscapes_calculated column to pipeline_executions table
ALTER TABLE pipeline_executions 
ADD COLUMN IF NOT EXISTS landscapes_calculated INTEGER DEFAULT 0;

-- Add comment for documentation
COMMENT ON COLUMN pipeline_executions.landscapes_calculated IS 'Number of digital landscapes that had DSI calculations performed during this pipeline execution';

-- Create index for querying pipelines by landscape calculation status
CREATE INDEX IF NOT EXISTS idx_pipeline_executions_landscapes_calculated 
ON pipeline_executions(landscapes_calculated);

-- Add landscape calculation success rate view for monitoring
CREATE OR REPLACE VIEW pipeline_landscape_metrics AS
SELECT 
    DATE(started_at) as execution_date,
    COUNT(*) as total_pipelines,
    AVG(landscapes_calculated) as avg_landscapes_per_pipeline,
    SUM(landscapes_calculated) as total_landscapes_calculated,
    COUNT(*) FILTER (WHERE landscapes_calculated > 0) as pipelines_with_landscapes,
    ROUND(
        (COUNT(*) FILTER (WHERE landscapes_calculated > 0)::DECIMAL / COUNT(*)) * 100, 
        2
    ) as landscape_calculation_rate_percent
FROM pipeline_executions 
WHERE started_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(started_at)
ORDER BY execution_date DESC;

-- Add comment for the view
COMMENT ON VIEW pipeline_landscape_metrics IS 'Daily metrics showing landscape DSI calculation performance across pipeline executions';

