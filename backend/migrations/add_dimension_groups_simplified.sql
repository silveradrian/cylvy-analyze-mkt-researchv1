-- Add dimension grouping capabilities (simplified for single-tenant)
-- Allows organizing dimensions into categories and tracking primary dimensions per group

-- Dimension groups table
CREATE TABLE IF NOT EXISTS dimension_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Group configuration
    selection_strategy VARCHAR(50) DEFAULT 'highest_score', -- highest_score, highest_confidence, most_evidence, manual
    max_primary_dimensions INTEGER DEFAULT 1, -- How many dimensions can be primary in this group
    
    -- Display and filtering
    display_order INTEGER DEFAULT 0,
    color_hex VARCHAR(7), -- For UI display
    icon VARCHAR(50), -- Icon identifier for UI
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Link dimensions to groups (many-to-many)
CREATE TABLE IF NOT EXISTS dimension_group_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID REFERENCES dimension_groups(id) ON DELETE CASCADE,
    dimension_id VARCHAR(100) NOT NULL,
    
    -- Priority within group (lower number = higher priority for manual selection)
    priority INTEGER DEFAULT 100,
    
    -- Metadata
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    added_by VARCHAR(100),
    
    UNIQUE(group_id, dimension_id)
);

-- Track primary dimensions selected for each analysis
CREATE TABLE IF NOT EXISTS analysis_primary_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES optimized_content_analysis(id) ON DELETE CASCADE,
    group_id UUID REFERENCES dimension_groups(id) ON DELETE CASCADE,
    dimension_id VARCHAR(100) NOT NULL,
    
    -- Why this dimension was selected as primary
    selection_reason VARCHAR(255),
    selection_score NUMERIC(5,2), -- Score used for selection
    selection_metadata JSONB DEFAULT '{}', -- Additional selection data
    
    -- Timestamp
    selected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(analysis_id, group_id)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_dimension_groups_active ON dimension_groups(is_active);
CREATE INDEX IF NOT EXISTS idx_dimension_groups_order ON dimension_groups(display_order);

CREATE INDEX IF NOT EXISTS idx_dimension_group_members_group ON dimension_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_dimension_group_members_dimension ON dimension_group_members(dimension_id);

CREATE INDEX IF NOT EXISTS idx_analysis_primary_dimensions_analysis ON analysis_primary_dimensions(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_primary_dimensions_group ON analysis_primary_dimensions(group_id);
CREATE INDEX IF NOT EXISTS idx_analysis_primary_dimensions_dimension ON analysis_primary_dimensions(dimension_id);

-- View to easily see dimension group memberships
CREATE OR REPLACE VIEW dimension_groups_expanded AS
SELECT 
    g.id as group_id,
    g.group_id as group_code,
    g.name as group_name,
    g.selection_strategy,
    g.display_order,
    d.dimension_id,
    d.name as dimension_name,
    d.ai_context->>'scope' as dimension_type,
    dgm.priority
FROM dimension_groups g
JOIN dimension_group_members dgm ON g.id = dgm.group_id
JOIN generic_custom_dimensions d ON dgm.dimension_id = d.dimension_id
WHERE g.is_active = true AND d.is_active = true
ORDER BY g.display_order, dgm.priority;

-- View to see primary dimensions selected per analysis
CREATE OR REPLACE VIEW analysis_primary_dimensions_summary AS
SELECT 
    apd.analysis_id,
    apd.group_id,
    dg.name as group_name,
    apd.dimension_id,
    gcd.name as dimension_name,
    apd.selection_score,
    apd.selection_reason,
    apd.selected_at
FROM analysis_primary_dimensions apd
JOIN dimension_groups dg ON apd.group_id = dg.id
JOIN generic_custom_dimensions gcd ON apd.dimension_id = gcd.dimension_id
ORDER BY apd.analysis_id, dg.display_order;

-- Function to select primary dimensions for an analysis based on scores
CREATE OR REPLACE FUNCTION select_primary_dimensions(
    p_analysis_id UUID,
    p_dimension_scores JSONB -- Expected format: {"dim_001": {"score": 8.5, "confidence": 0.9}, ...}
) RETURNS TABLE (
    group_id UUID,
    dimension_id VARCHAR(100),
    score NUMERIC(5,2),
    reason TEXT
) AS $$
DECLARE
    v_group RECORD;
    v_primary RECORD;
BEGIN
    -- For each active dimension group
    FOR v_group IN 
        SELECT id, group_id, name, selection_strategy, max_primary_dimensions
        FROM dimension_groups
        WHERE is_active = true
        ORDER BY display_order
    LOOP
        -- Select primary dimension(s) based on strategy
        FOR v_primary IN
            WITH group_dimensions AS (
                SELECT 
                    dgm.dimension_id,
                    dgm.priority,
                    COALESCE((p_dimension_scores->dgm.dimension_id->>'score')::NUMERIC, 0) as score,
                    COALESCE((p_dimension_scores->dgm.dimension_id->>'confidence')::NUMERIC, 0) as confidence,
                    COALESCE(jsonb_array_length(p_dimension_scores->dgm.dimension_id->'evidence'), 0) as evidence_count
                FROM dimension_group_members dgm
                WHERE dgm.group_id = v_group.id
            )
            SELECT 
                dimension_id,
                score,
                CASE 
                    WHEN v_group.selection_strategy = 'highest_score' THEN 
                        'Highest score in ' || v_group.name
                    WHEN v_group.selection_strategy = 'highest_confidence' THEN 
                        'Highest confidence in ' || v_group.name
                    WHEN v_group.selection_strategy = 'most_evidence' THEN 
                        'Most evidence in ' || v_group.name
                    WHEN v_group.selection_strategy = 'manual' THEN 
                        'Manual priority in ' || v_group.name
                END as reason
            FROM group_dimensions
            WHERE score > 0  -- Only consider dimensions with positive scores
            ORDER BY 
                CASE 
                    WHEN v_group.selection_strategy = 'highest_score' THEN score
                    WHEN v_group.selection_strategy = 'highest_confidence' THEN confidence
                    WHEN v_group.selection_strategy = 'most_evidence' THEN evidence_count::NUMERIC
                    WHEN v_group.selection_strategy = 'manual' THEN -priority::NUMERIC -- Lower priority number = higher priority
                END DESC
            LIMIT v_group.max_primary_dimensions
        LOOP
            -- Return the selected primary dimension
            group_id := v_group.id;
            dimension_id := v_primary.dimension_id;
            score := v_primary.score;
            reason := v_primary.reason;
            RETURN NEXT;
        END LOOP;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Add comments
COMMENT ON TABLE dimension_groups IS 'Defines groups for organizing custom dimensions';
COMMENT ON TABLE dimension_group_members IS 'Links dimensions to their groups';
COMMENT ON TABLE analysis_primary_dimensions IS 'Tracks which dimensions were selected as primary for each analysis';
COMMENT ON FUNCTION select_primary_dimensions IS 'Selects primary dimensions for an analysis based on group strategies';

