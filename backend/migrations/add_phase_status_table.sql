-- Add pipeline phase status tracking table
CREATE TABLE IF NOT EXISTS pipeline_phase_status (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    pipeline_execution_id UUID NOT NULL,
    phase_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    result_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    UNIQUE(pipeline_execution_id, phase_name),
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped', 'blocked'))
);

-- Add indexes for performance
CREATE INDEX idx_pipeline_phase_status_execution_id ON pipeline_phase_status(pipeline_execution_id);
CREATE INDEX idx_pipeline_phase_status_phase_name ON pipeline_phase_status(phase_name);
CREATE INDEX idx_pipeline_phase_status_status ON pipeline_phase_status(status);
CREATE INDEX idx_pipeline_phase_status_created_at ON pipeline_phase_status(created_at);

-- Add phase dependencies table
CREATE TABLE IF NOT EXISTS pipeline_phase_dependencies (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    phase_name VARCHAR(100) NOT NULL,
    depends_on_phase VARCHAR(100) NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(phase_name, depends_on_phase)
);

-- Insert default phase dependencies
INSERT INTO pipeline_phase_dependencies (phase_name, depends_on_phase) VALUES
    ('serp_collection', 'keyword_metrics'),
    ('company_enrichment_serp', 'serp_collection'),
    ('youtube_enrichment', 'serp_collection'),
    ('company_enrichment_youtube', 'youtube_enrichment'),
    ('company_enrichment_youtube', 'company_enrichment_serp'),
    ('content_analysis', 'company_enrichment_serp'),
    ('content_analysis', 'youtube_enrichment'),
    ('dsi_calculation', 'content_analysis'),
    ('dsi_calculation', 'company_enrichment_youtube')
ON CONFLICT DO NOTHING;


