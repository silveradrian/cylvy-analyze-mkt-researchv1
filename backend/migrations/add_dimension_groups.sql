-- Add dimension grouping capabilities
-- Allows organizing dimensions into categories and tracking primary dimensions per group

-- Dimension groups table
CREATE TABLE IF NOT EXISTS dimension_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    group_id VARCHAR(100) NOT NULL,
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
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(project_id, group_id)
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
    analysis_id UUID NOT NULL REFERENCES advanced_content_analysis(id) ON DELETE CASCADE,
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

-- Add group reference to dimensions
ALTER TABLE generic_custom_dimensions 
ADD COLUMN IF NOT EXISTS group_ids UUID[] DEFAULT '{}';

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_dimension_groups_project ON dimension_groups(project_id);
CREATE INDEX IF NOT EXISTS idx_dimension_groups_active ON dimension_groups(is_active);
CREATE INDEX IF NOT EXISTS idx_dimension_group_members_group ON dimension_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_dimension_group_members_dimension ON dimension_group_members(dimension_id);
CREATE INDEX IF NOT EXISTS idx_analysis_primary_dimensions_analysis ON analysis_primary_dimensions(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_primary_dimensions_group ON analysis_primary_dimensions(group_id);

-- Views for easy querying

-- View showing dimensions with their groups
CREATE OR REPLACE VIEW dimensions_with_groups AS
SELECT 
    d.dimension_id,
    d.name as dimension_name,
    d.metadata->>'dimension_type' as dimension_type,
    g.id as group_id,
    g.name as group_name,
    g.selection_strategy,
    dgm.priority
FROM generic_custom_dimensions d
CROSS JOIN LATERAL unnest(d.group_ids) AS group_id
JOIN dimension_groups g ON g.id = group_id::uuid
LEFT JOIN dimension_group_members dgm ON dgm.group_id = g.id AND dgm.dimension_id = d.dimension_id
WHERE d.is_active = true AND g.is_active = true
ORDER BY g.display_order, dgm.priority, d.name;

-- View showing primary dimensions for recent analyses
CREATE OR REPLACE VIEW recent_primary_dimensions AS
SELECT 
    aca.url,
    aca.analyzed_at,
    dg.name as group_name,
    gcd.name as primary_dimension_name,
    apd.selection_score,
    apd.selection_reason,
    p.company_name
FROM analysis_primary_dimensions apd
JOIN advanced_content_analysis aca ON apd.analysis_id = aca.id
JOIN dimension_groups dg ON apd.group_id = dg.id
JOIN generic_custom_dimensions gcd ON apd.dimension_id = gcd.dimension_id
LEFT JOIN projects p ON aca.project_id = p.id
ORDER BY aca.analyzed_at DESC, dg.display_order;

-- Function to get dimension group performance
CREATE OR REPLACE FUNCTION get_dimension_group_performance(
    p_project_id UUID,
    p_group_id UUID DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    group_id UUID,
    group_name VARCHAR,
    avg_primary_score NUMERIC,
    primary_dimension_diversity INTEGER,
    most_common_primary VARCHAR,
    content_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH group_stats AS (
        SELECT 
            dg.id as group_id,
            dg.name as group_name,
            AVG(apd.selection_score) as avg_primary_score,
            COUNT(DISTINCT apd.dimension_id) as primary_dimension_diversity,
            MODE() WITHIN GROUP (ORDER BY apd.dimension_id) as most_common_primary_id,
            COUNT(DISTINCT aca.url) as content_count
        FROM dimension_groups dg
        JOIN analysis_primary_dimensions apd ON dg.id = apd.group_id
        JOIN advanced_content_analysis aca ON apd.analysis_id = aca.id
        WHERE dg.project_id = p_project_id
            AND (p_group_id IS NULL OR dg.id = p_group_id)
        GROUP BY dg.id, dg.name
    )
    SELECT 
        gs.group_id,
        gs.group_name,
        ROUND(gs.avg_primary_score, 2),
        gs.primary_dimension_diversity::INTEGER,
        gcd.name as most_common_primary,
        gs.content_count::INTEGER
    FROM group_stats gs
    LEFT JOIN generic_custom_dimensions gcd ON gs.most_common_primary_id = gcd.dimension_id
    ORDER BY gs.avg_primary_score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Sample dimension groups for diverse content attributes
INSERT INTO dimension_groups (project_id, group_id, name, description, selection_strategy, color_hex, icon) VALUES
(NULL, 'content_style', 'Content Style & Tone', 'Writing style, tone of voice, and communication approach', 'highest_confidence', '#8B5CF6', 'pen-tool'),
(NULL, 'audience_alignment', 'Audience Targeting', 'How well content aligns with different audience segments', 'highest_score', '#3B82F6', 'users'),
(NULL, 'information_quality', 'Information Quality', 'Depth, accuracy, and completeness of information', 'most_evidence', '#10B981', 'file-text'),
(NULL, 'engagement_factors', 'Engagement & Impact', 'Factors that drive reader engagement and action', 'highest_score', '#F59E0B', 'trending-up')
ON CONFLICT (project_id, group_id) DO NOTHING;
