-- Fix missing serp_scheduling_config column
-- This column is referenced but doesn't exist in the pipeline_schedules table

ALTER TABLE pipeline_schedules 
ADD COLUMN IF NOT EXISTS serp_scheduling_config JSONB DEFAULT '{"frequency": "immediate", "priority": "normal"}'::jsonb;

-- Add comment to document the field
COMMENT ON COLUMN pipeline_schedules.serp_scheduling_config IS 'SERP batch scheduling configuration including frequency and priority';
