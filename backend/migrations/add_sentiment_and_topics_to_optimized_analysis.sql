-- Add overall sentiment and key topics to optimized content analysis table

-- Add overall_sentiment column
ALTER TABLE optimized_content_analysis
ADD COLUMN IF NOT EXISTS overall_sentiment VARCHAR(20);

-- Add key_topics column
ALTER TABLE optimized_content_analysis
ADD COLUMN IF NOT EXISTS key_topics JSONB DEFAULT '[]';

-- Add index for sentiment
CREATE INDEX IF NOT EXISTS idx_optimized_analysis_sentiment 
ON optimized_content_analysis(overall_sentiment);

-- Update the view to include new fields
DROP VIEW IF EXISTS optimized_analysis_summary;

CREATE OR REPLACE VIEW optimized_analysis_summary AS
SELECT 
    oca.id,
    oca.url,
    oca.project_id,
    oca.overall_insights,
    oca.mentions,
    oca.overall_sentiment,
    oca.key_topics,
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
GROUP BY oca.id, oca.url, oca.project_id, oca.overall_insights, oca.mentions, 
         oca.overall_sentiment, oca.key_topics, oca.analyzed_at;

-- Add comments
COMMENT ON COLUMN optimized_content_analysis.overall_sentiment IS 
'Overall sentiment of the content: positive, negative, or neutral';

COMMENT ON COLUMN optimized_content_analysis.key_topics IS 
'Array of 5 main topics/themes the content covers';

