-- Create simplified content analysis table
-- This replaces the complex multi-table structure with a single unified table

-- Drop existing table if it exists (be careful in production!)
DROP TABLE IF EXISTS content_analysis CASCADE;

-- Create the new simplified table
CREATE TABLE content_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    project_id UUID REFERENCES projects(id),
    analyzed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Persona analysis (mandatory)
    primary_persona TEXT NOT NULL,
    persona_scores JSONB NOT NULL DEFAULT '{}',  -- {"Technical DM": 8, "Business DM": 3}
    persona_reasoning TEXT,
    
    -- JTBD phase analysis (mandatory)  
    primary_jtbd_phase INTEGER NOT NULL CHECK (primary_jtbd_phase BETWEEN 1 AND 6),
    phase_alignment_score INTEGER NOT NULL CHECK (phase_alignment_score BETWEEN 0 AND 10),
    phase_reasoning TEXT,
    
    -- Custom dimension scores (optional)
    dimension_scores JSONB NOT NULL DEFAULT '{}',  -- {"Cloud Maturity": 5, "Security": 10}
    dimension_evidence JSONB NOT NULL DEFAULT '{}',  -- {"Cloud Maturity": "AWS certified..."}
    
    -- Competitive mentions
    mentions JSONB NOT NULL DEFAULT '[]',  -- [{"entity": "Competitor X", "sentiment": "positive", "context": "..."}]
    
    -- Summary and signals
    summary TEXT,
    buyer_intent_signals TEXT[] DEFAULT '{}',
    
    -- Full AI response for debugging
    ai_response JSONB,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint on URL per project
    CONSTRAINT unique_url_per_project UNIQUE (url, project_id)
);

-- Create indexes for performance
CREATE INDEX idx_content_analysis_project ON content_analysis(project_id);
CREATE INDEX idx_content_analysis_analyzed_at ON content_analysis(analyzed_at DESC);
CREATE INDEX idx_content_analysis_primary_persona ON content_analysis(primary_persona);
CREATE INDEX idx_content_analysis_jtbd_phase ON content_analysis(primary_jtbd_phase);
CREATE INDEX idx_content_analysis_mentions ON content_analysis USING gin(mentions);
CREATE INDEX idx_content_analysis_dimension_scores ON content_analysis USING gin(dimension_scores);

-- Create view for easy querying
CREATE OR REPLACE VIEW content_analysis_summary AS
SELECT 
    ca.id,
    ca.url,
    ca.analyzed_at,
    ca.primary_persona,
    ca.persona_scores,
    ca.primary_jtbd_phase,
    ca.phase_alignment_score,
    ca.dimension_scores,
    ca.summary,
    ca.buyer_intent_signals,
    p.company_name,
    p.company_domain
FROM content_analysis ca
LEFT JOIN projects p ON ca.project_id = p.id
ORDER BY ca.analyzed_at DESC;

-- Function to get persona alignment stats
CREATE OR REPLACE FUNCTION get_persona_alignment_stats(p_project_id UUID)
RETURNS TABLE (
    persona_name TEXT,
    content_count INTEGER,
    avg_score NUMERIC,
    as_primary_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH persona_data AS (
        SELECT 
            jsonb_object_keys(persona_scores) as persona,
            persona_scores,
            primary_persona
        FROM content_analysis
        WHERE project_id = p_project_id
    )
    SELECT 
        pd.persona as persona_name,
        COUNT(*)::INTEGER as content_count,
        AVG((pd.persona_scores->>pd.persona)::NUMERIC) as avg_score,
        SUM(CASE WHEN pd.primary_persona = pd.persona THEN 1 ELSE 0 END)::INTEGER as as_primary_count
    FROM persona_data pd
    GROUP BY pd.persona
    ORDER BY as_primary_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get JTBD phase distribution
CREATE OR REPLACE FUNCTION get_jtbd_phase_distribution(p_project_id UUID)
RETURNS TABLE (
    phase_number INTEGER,
    content_count INTEGER,
    avg_alignment_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        primary_jtbd_phase as phase_number,
        COUNT(*)::INTEGER as content_count,
        AVG(phase_alignment_score) as avg_alignment_score
    FROM content_analysis
    WHERE project_id = p_project_id
    GROUP BY primary_jtbd_phase
    ORDER BY primary_jtbd_phase;
END;
$$ LANGUAGE plpgsql;

-- Function to get dimension performance
CREATE OR REPLACE FUNCTION get_dimension_performance(p_project_id UUID)
RETURNS TABLE (
    dimension_name TEXT,
    avg_score NUMERIC,
    score_distribution JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH dimension_data AS (
        SELECT 
            jsonb_object_keys(dimension_scores) as dimension,
            dimension_scores
        FROM content_analysis
        WHERE project_id = p_project_id
            AND dimension_scores != '{}'
    )
    SELECT 
        dd.dimension as dimension_name,
        AVG((dd.dimension_scores->>dd.dimension)::NUMERIC) as avg_score,
        jsonb_build_object(
            '0', SUM(CASE WHEN (dd.dimension_scores->>dd.dimension)::INTEGER = 0 THEN 1 ELSE 0 END),
            '5', SUM(CASE WHEN (dd.dimension_scores->>dd.dimension)::INTEGER = 5 THEN 1 ELSE 0 END),
            '10', SUM(CASE WHEN (dd.dimension_scores->>dd.dimension)::INTEGER = 10 THEN 1 ELSE 0 END)
        ) as score_distribution
    FROM dimension_data dd
    GROUP BY dd.dimension
    ORDER BY avg_score DESC;
END;
$$ LANGUAGE plpgsql;

