-- Add mentions field to optimized content analysis table

-- Add mentions column to the optimized_content_analysis table
ALTER TABLE optimized_content_analysis
ADD COLUMN IF NOT EXISTS mentions JSONB DEFAULT '[]';

-- Add index for mentions
CREATE INDEX IF NOT EXISTS idx_optimized_analysis_mentions 
ON optimized_content_analysis USING gin(mentions);

-- Update the view to include mentions
DROP VIEW IF EXISTS optimized_analysis_summary;

CREATE OR REPLACE VIEW optimized_analysis_summary AS
SELECT 
    oca.id,
    oca.url,
    oca.project_id,
    oca.overall_insights,
    oca.mentions,
    oca.analyzed_at,
    
    -- Aggregate dimension scores
    COALESCE(
        jsonb_object_agg(
            oda.dimension_name,
            jsonb_build_object(
                'score', oda.score,
                'confidence', oda.confidence,
                'evidence', oda.key_evidence
            )
        ) FILTER (WHERE oda.dimension_name IS NOT NULL),
        '{}'::jsonb
    ) as dimension_scores,
    
    -- Extract top personas
    COALESCE(
        (SELECT dimension_name 
         FROM optimized_dimension_analysis 
         WHERE analysis_id = oca.id 
         AND dimension_type = 'PERSONA' 
         ORDER BY score DESC 
         LIMIT 1),
        'Unknown'
    ) as primary_persona,
    
    -- Extract top JTBD phase
    COALESCE(
        (SELECT dimension_name 
         FROM optimized_dimension_analysis 
         WHERE analysis_id = oca.id 
         AND dimension_type = 'JTBD_PHASE' 
         ORDER BY score DESC 
         LIMIT 1),
        'Unknown'
    ) as primary_jtbd_phase
    
FROM optimized_content_analysis oca
LEFT JOIN optimized_dimension_analysis oda ON oda.analysis_id = oca.id
GROUP BY oca.id, oca.url, oca.project_id, oca.overall_insights, oca.mentions, oca.analyzed_at;

-- Add comment
COMMENT ON COLUMN optimized_content_analysis.mentions IS 
'Array of brand and competitor mentions with sentiment analysis: [{"entity": "Brand/Competitor", "type": "brand|competitor", "sentiment": "positive|negative|neutral", "confidence": 0-10, "context": "...", "position": 123}]';

