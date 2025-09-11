-- Optimized content analysis tables with reduced verbosity

-- Main analysis table
CREATE TABLE IF NOT EXISTS optimized_content_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    project_id UUID REFERENCES client_config(id),
    overall_insights TEXT,
    analyzer_version VARCHAR(50),
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for performance
    CONSTRAINT uk_optimized_url_project UNIQUE (url, project_id)
);

CREATE INDEX IF NOT EXISTS idx_optimized_analysis_project ON optimized_content_analysis(project_id);
CREATE INDEX IF NOT EXISTS idx_optimized_analysis_date ON optimized_content_analysis(analyzed_at DESC);

-- Optimized dimension analysis with concise fields
CREATE TABLE IF NOT EXISTS optimized_dimension_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES optimized_content_analysis(id) ON DELETE CASCADE,
    dimension_id VARCHAR(255) NOT NULL,
    dimension_name VARCHAR(255) NOT NULL,
    dimension_type VARCHAR(50) NOT NULL,
    
    -- Core scoring (reduced from 7 fields to 2)
    score INTEGER CHECK (score >= 0 AND score <= 10),
    confidence INTEGER CHECK (confidence >= 0 AND confidence <= 10),
    
    -- Evidence (reduced from multiple fields to 1)
    key_evidence TEXT,
    
    -- Signals and factors (simplified)
    primary_signals JSONB DEFAULT '[]',
    score_factors JSONB DEFAULT '{"positive": [], "negative": []}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_optimized_dim_analysis ON optimized_dimension_analysis(analysis_id);
CREATE INDEX IF NOT EXISTS idx_optimized_dim_score ON optimized_dimension_analysis(score DESC);
CREATE INDEX IF NOT EXISTS idx_optimized_dim_type ON optimized_dimension_analysis(dimension_type);

-- View for easy querying
CREATE OR REPLACE VIEW optimized_analysis_summary AS
SELECT 
    oca.id,
    oca.url,
    oca.project_id,
    oca.overall_insights,
    oca.analyzed_at,
    
    -- Aggregate dimension scores
    COUNT(oda.id) as dimension_count,
    AVG(oda.score)::NUMERIC(3,1) as avg_score,
    AVG(oda.confidence)::NUMERIC(3,1) as avg_confidence,
    
    -- Top performing dimensions
    JSONB_AGG(
        JSONB_BUILD_OBJECT(
            'dimension', oda.dimension_name,
            'type', oda.dimension_type,
            'score', oda.score,
            'evidence', oda.key_evidence
        ) ORDER BY oda.score DESC
    ) FILTER (WHERE oda.score >= 7) as high_scoring_dimensions,
    
    -- Primary dimensions per group
    JSONB_OBJECT_AGG(
        apd.group_id,
        JSONB_BUILD_OBJECT(
            'dimension_id', apd.dimension_id,
            'dimension_name', oda.dimension_name,
            'score', oda.score
        )
    ) FILTER (WHERE apd.dimension_id IS NOT NULL) as primary_dimensions
    
FROM optimized_content_analysis oca
LEFT JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
LEFT JOIN analysis_primary_dimensions apd ON oca.id = apd.analysis_id AND oda.dimension_id = apd.dimension_id
GROUP BY oca.id, oca.url, oca.project_id, oca.overall_insights, oca.analyzed_at;

-- Comparison view: Original vs Optimized storage
CREATE OR REPLACE VIEW analysis_storage_comparison AS
WITH original_size AS (
    SELECT 
        COUNT(*) as record_count,
        pg_size_pretty(SUM(pg_column_size(row_to_json(ada)))) as total_size,
        AVG(pg_column_size(row_to_json(ada))) as avg_record_size
    FROM advanced_dimension_analysis ada
),
optimized_size AS (
    SELECT 
        COUNT(*) as record_count,
        pg_size_pretty(SUM(pg_column_size(row_to_json(oda)))) as total_size,
        AVG(pg_column_size(row_to_json(oda))) as avg_record_size
    FROM optimized_dimension_analysis oda
)
SELECT 
    'Original' as version,
    o.record_count,
    o.total_size,
    o.avg_record_size
FROM original_size o
UNION ALL
SELECT 
    'Optimized' as version,
    p.record_count,
    p.total_size,
    p.avg_record_size
FROM optimized_size p;

-- Add comments for documentation
COMMENT ON TABLE optimized_content_analysis IS 'Streamlined content analysis with reduced verbosity';
COMMENT ON TABLE optimized_dimension_analysis IS 'Concise dimension scoring focused on actionable insights';
COMMENT ON COLUMN optimized_dimension_analysis.key_evidence IS 'Brief 1-2 sentence summary of strongest evidence';
COMMENT ON COLUMN optimized_dimension_analysis.primary_signals IS 'Top 3 matched criteria as brief labels';
COMMENT ON COLUMN optimized_dimension_analysis.score_factors IS 'Brief positive and negative factors affecting the score';

