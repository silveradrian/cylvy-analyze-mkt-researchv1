-- Create default pipeline schedule with 5 regions
INSERT INTO pipeline_schedules (
    name, 
    regions, 
    content_schedules, 
    is_active,
    serp_scheduling_config
) VALUES (
    'Default Schedule',
    ARRAY['US', 'UK', 'CA', 'AU', 'DE'],
    '[
        {"content_type": "organic", "enabled": true, "frequency": "daily"},
        {"content_type": "news", "enabled": true, "frequency": "daily"},
        {"content_type": "video", "enabled": true, "frequency": "daily"}
    ]'::jsonb,
    true,
    '{"frequency": "immediate", "priority": "normal"}'::jsonb
);
