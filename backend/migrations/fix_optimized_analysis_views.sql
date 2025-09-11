-- Fix optimized analysis views to remove references to non-existent tables

-- Drop the problematic views first
DROP VIEW IF EXISTS optimized_analysis_summary CASCADE;
DROP VIEW IF EXISTS analysis_storage_comparison CASCADE;

-- Recreate summary view without the missing tables
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
    ) FILTER (WHERE oda.score >= 7) as high_scoring_dimensions
    
FROM optimized_content_analysis oca
LEFT JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
GROUP BY oca.id, oca.url, oca.project_id, oca.overall_insights, oca.analyzed_at;

-- Simple storage comparison view
CREATE OR REPLACE VIEW analysis_storage_info AS
SELECT 
    'Optimized' as version,
    COUNT(*) as analyses_count,
    COUNT(DISTINCT oca.project_id) as projects_count,
    AVG(LENGTH(oda.key_evidence)) as avg_evidence_length,
    AVG(oda.score)::NUMERIC(3,1) as avg_score,
    AVG(oda.confidence)::NUMERIC(3,1) as avg_confidence
FROM optimized_content_analysis oca
LEFT JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id;

COMMENT ON VIEW optimized_analysis_summary IS 'Summary view of optimized content analyses';
COMMENT ON VIEW analysis_storage_info IS 'Storage and performance metrics for optimized analyses';

