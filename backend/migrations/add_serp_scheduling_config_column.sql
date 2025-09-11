-- Add serp_scheduling_config column to analysis_config if it doesn't exist
ALTER TABLE analysis_config 
ADD COLUMN IF NOT EXISTS serp_scheduling_config JSONB DEFAULT '{
    "organic": {
        "frequency": "daily",
        "priority": "normal",
        "time_of_day": "09:00"
    },
    "news": {
        "frequency": "daily", 
        "priority": "high",
        "time_of_day": "08:00"
    },
    "video": {
        "frequency": "weekly",
        "priority": "low",
        "days_of_week": [1],
        "time_of_day": "10:00"
    }
}';

-- Also ensure the pipeline_schedules table has the necessary column
ALTER TABLE pipeline_schedules
ADD COLUMN IF NOT EXISTS content_schedules JSONB DEFAULT '[]';
