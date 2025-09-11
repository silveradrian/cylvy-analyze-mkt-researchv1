-- Advanced Unified Analysis Tables
-- Supports personas, JTBD, and custom dimensions all using the same framework

-- Drop existing tables if needed (be careful in production!)
DROP TABLE IF EXISTS advanced_dimension_analysis CASCADE;
DROP TABLE IF EXISTS advanced_content_analysis CASCADE;
DROP TABLE IF EXISTS generic_custom_dimensions CASCADE;

-- Generic custom dimensions configuration (works for ANY dimension type)
CREATE TABLE generic_custom_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    dimension_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- AI context for overall understanding
    ai_context JSONB NOT NULL DEFAULT '{}', -- general_description, purpose, scope, key_focus_areas, analysis_approach
    
    -- Flexible criteria structure
    criteria JSONB NOT NULL DEFAULT '{}', -- what_counts, positive_signals, negative_signals, exclusions, additional_context
    
    -- Configurable scoring framework
    scoring_framework JSONB NOT NULL DEFAULT '{}', -- levels, evidence_requirements, contextual_rules
    
    -- Client-specific metadata
    metadata JSONB DEFAULT '{}',
    
    -- System metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(project_id, dimension_id)
);

-- Main analysis table for unified results
CREATE TABLE advanced_content_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    project_id UUID REFERENCES projects(id),
    analyzed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Overall analysis summary
    overall_summary TEXT,
    key_insights TEXT[] DEFAULT '{}',
    
    -- Analysis metadata
    metadata JSONB DEFAULT '{}', -- total_dimensions_analyzed, framework_version, etc.
    
    -- System fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint
    CONSTRAINT unique_url_per_project_advanced UNIQUE (url, project_id)
);

-- Individual dimension analysis results (generic structure)
CREATE TABLE advanced_dimension_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES advanced_content_analysis(id) ON DELETE CASCADE,
    dimension_id VARCHAR(100) NOT NULL,
    dimension_name VARCHAR(255) NOT NULL,
    dimension_type VARCHAR(50), -- persona, jtbd_phase, custom, etc.
    
    -- Core analysis result
    final_score INTEGER NOT NULL CHECK (final_score >= 0 AND final_score <= 10),
    evidence_summary TEXT,
    
    -- Evidence analysis (flexible structure)
    evidence_analysis JSONB DEFAULT '{}', -- total_relevant_words, evidence_threshold_met, specificity_score, quality_indicators
    
    -- Scoring breakdown
    scoring_breakdown JSONB DEFAULT '{}', -- base_score, evidence_adjustments, contextual_adjustments, scoring_rationale
    
    -- AI outputs
    confidence_score INTEGER DEFAULT 0 CHECK (confidence_score >= 0 AND confidence_score <= 10),
    detailed_reasoning TEXT,
    matched_criteria JSONB DEFAULT '[]', -- Array of matched criteria
    
    -- Dimension-specific metadata
    analysis_metadata JSONB DEFAULT '{}',
    
    -- System metadata
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_used VARCHAR(100) DEFAULT 'gpt-4-turbo-preview',
    analysis_version VARCHAR(20) DEFAULT 'advanced_v1.0',
    
    -- Indexes
    CONSTRAINT unique_analysis_dimension UNIQUE (analysis_id, dimension_id),
    INDEX idx_analysis_id (analysis_id),
    INDEX idx_dimension_id (dimension_id),
    INDEX idx_final_score (final_score),
    INDEX idx_dimension_type (dimension_type)
);

-- Create indexes for performance
CREATE INDEX idx_advanced_content_project ON advanced_content_analysis(project_id);
CREATE INDEX idx_advanced_content_analyzed_at ON advanced_content_analysis(analyzed_at DESC);
CREATE INDEX idx_advanced_content_url ON advanced_content_analysis(url);

CREATE INDEX idx_generic_dimensions_project ON generic_custom_dimensions(project_id);
CREATE INDEX idx_generic_dimensions_active ON generic_custom_dimensions(is_active);

-- Views for easy querying

-- Persona alignment view
CREATE OR REPLACE VIEW persona_alignment_analysis AS
SELECT 
    aca.url,
    aca.analyzed_at,
    ada.dimension_id,
    ada.dimension_name,
    ada.final_score,
    ada.evidence_summary,
    ada.confidence_score,
    ada.analysis_metadata->>'department' as persona_department,
    ada.analysis_metadata->>'influence_level' as influence_level,
    p.company_name
FROM advanced_dimension_analysis ada
JOIN advanced_content_analysis aca ON ada.analysis_id = aca.id
LEFT JOIN projects p ON aca.project_id = p.id
WHERE ada.dimension_type = 'persona'
ORDER BY aca.analyzed_at DESC, ada.final_score DESC;

-- JTBD phase alignment view
CREATE OR REPLACE VIEW jtbd_phase_analysis AS
SELECT 
    aca.url,
    aca.analyzed_at,
    ada.dimension_id,
    ada.dimension_name,
    ada.final_score,
    ada.evidence_summary,
    ada.analysis_metadata->>'phase_number' as phase_number,
    ada.analysis_metadata->>'phase_name' as phase_name,
    p.company_name
FROM advanced_dimension_analysis ada
JOIN advanced_content_analysis aca ON ada.analysis_id = aca.id
LEFT JOIN projects p ON aca.project_id = p.id
WHERE ada.dimension_type = 'jtbd_phase'
ORDER BY aca.analyzed_at DESC, (ada.analysis_metadata->>'phase_number')::int;

-- Custom dimension performance view
CREATE OR REPLACE VIEW custom_dimension_performance AS
SELECT 
    aca.url,
    aca.analyzed_at,
    ada.dimension_id,
    ada.dimension_name,
    ada.final_score,
    ada.evidence_summary,
    ada.confidence_score,
    ada.scoring_breakdown,
    p.company_name
FROM advanced_dimension_analysis ada
JOIN advanced_content_analysis aca ON ada.analysis_id = aca.id
LEFT JOIN projects p ON aca.project_id = p.id
WHERE ada.dimension_type = 'custom' OR ada.dimension_type IS NULL
ORDER BY aca.analyzed_at DESC, ada.final_score DESC;

-- Functions for analysis

-- Get dimension performance summary
CREATE OR REPLACE FUNCTION get_dimension_performance_summary(p_project_id UUID, p_dimension_type VARCHAR DEFAULT NULL)
RETURNS TABLE (
    dimension_id VARCHAR,
    dimension_name VARCHAR,
    avg_score NUMERIC,
    min_score INTEGER,
    max_score INTEGER,
    content_count INTEGER,
    avg_confidence NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ada.dimension_id,
        ada.dimension_name,
        ROUND(AVG(ada.final_score), 2) as avg_score,
        MIN(ada.final_score) as min_score,
        MAX(ada.final_score) as max_score,
        COUNT(DISTINCT aca.url)::INTEGER as content_count,
        ROUND(AVG(ada.confidence_score), 2) as avg_confidence
    FROM advanced_dimension_analysis ada
    JOIN advanced_content_analysis aca ON ada.analysis_id = aca.id
    WHERE aca.project_id = p_project_id
        AND (p_dimension_type IS NULL OR ada.dimension_type = p_dimension_type)
    GROUP BY ada.dimension_id, ada.dimension_name
    ORDER BY avg_score DESC;
END;
$$ LANGUAGE plpgsql;

-- Get content performance across all dimensions
CREATE OR REPLACE FUNCTION get_content_dimension_matrix(p_project_id UUID, p_limit INTEGER DEFAULT 20)
RETURNS TABLE (
    url TEXT,
    analyzed_at TIMESTAMP WITH TIME ZONE,
    dimension_scores JSONB,
    avg_score NUMERIC,
    total_dimensions INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH content_scores AS (
        SELECT 
            aca.url,
            aca.analyzed_at,
            jsonb_object_agg(
                ada.dimension_id, 
                jsonb_build_object(
                    'name', ada.dimension_name,
                    'score', ada.final_score,
                    'confidence', ada.confidence_score
                )
            ) as dimension_scores,
            AVG(ada.final_score) as avg_score,
            COUNT(ada.dimension_id)::INTEGER as total_dimensions
        FROM advanced_content_analysis aca
        JOIN advanced_dimension_analysis ada ON aca.id = ada.analysis_id
        WHERE aca.project_id = p_project_id
        GROUP BY aca.url, aca.analyzed_at
    )
    SELECT * FROM content_scores
    ORDER BY analyzed_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Migration helper to convert existing data
CREATE OR REPLACE FUNCTION migrate_to_advanced_framework()
RETURNS void AS $$
BEGIN
    -- Log migration start
    RAISE NOTICE 'Starting migration to advanced framework...';
    
    -- Create temporary mapping table
    CREATE TEMP TABLE IF NOT EXISTS dimension_mapping (
        old_id VARCHAR,
        new_id VARCHAR,
        dimension_type VARCHAR
    );
    
    -- Migrate personas as dimensions
    INSERT INTO dimension_mapping (old_id, new_id, dimension_type)
    SELECT 
        'persona_' || id::text,
        'persona_' || LOWER(REPLACE(name, ' ', '_')),
        'persona'
    FROM personas;
    
    -- Log completion
    RAISE NOTICE 'Migration completed successfully';
END;
$$ LANGUAGE plpgsql;

