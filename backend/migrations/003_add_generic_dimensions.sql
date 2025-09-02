-- Migration 003: Add Generic Custom Dimensions Support
-- This migration creates completely dimension-agnostic tables that can handle
-- any type of custom analysis framework without hardcoded logic

-- Generic custom dimensions configuration (completely dimension-agnostic)
CREATE TABLE generic_custom_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id VARCHAR(100) NOT NULL,
    dimension_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- AI context for overall understanding (stored as JSONB)
    ai_context JSONB NOT NULL DEFAULT '{}', 
    -- Structure: {
    --   "general_description": "string",
    --   "purpose": "string", 
    --   "scope": "string",
    --   "key_focus_areas": ["string"],
    --   "analysis_approach": "string"
    -- }
    
    -- Flexible criteria structure (stored as JSONB for complete flexibility)
    criteria JSONB NOT NULL DEFAULT '{}',
    -- Structure: {
    --   "what_counts": "string",
    --   "positive_signals": ["string"],
    --   "negative_signals": ["string"],
    --   "exclusions": ["string"], 
    --   "additional_context": "string"
    -- }
    
    -- Configurable scoring framework
    scoring_framework JSONB NOT NULL DEFAULT '{}',
    -- Structure: {
    --   "levels": [{"range": [min, max], "label": "string", "description": "string", "requirements": ["string"]}],
    --   "evidence_requirements": {"min_words": int, "word_increment": int, "max_score_per_increment": int, "specificity_weight": float},
    --   "contextual_rules": [{"name": "string", "description": "string", "condition": "string", "adjustment_type": "string", "adjustment_value": number}]
    -- }
    
    -- Client-specific metadata (completely open-ended)
    metadata JSONB DEFAULT '{}',
    
    -- System metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(client_id, dimension_id)
);

-- Create indexes for performance
CREATE INDEX idx_generic_dimensions_client_id ON generic_custom_dimensions(client_id);
CREATE INDEX idx_generic_dimensions_dimension_id ON generic_custom_dimensions(dimension_id);
CREATE INDEX idx_generic_dimensions_active ON generic_custom_dimensions(is_active);
CREATE INDEX idx_generic_dimensions_client_dimension ON generic_custom_dimensions(client_id, dimension_id);

-- Generic analysis results (no hardcoded fields)
CREATE TABLE generic_dimension_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_analysis_id UUID NOT NULL REFERENCES content_analysis(id) ON DELETE CASCADE,
    dimension_id VARCHAR(100) NOT NULL,
    
    -- Core analysis result
    final_score INTEGER NOT NULL CHECK (final_score >= 0 AND final_score <= 10),
    evidence_summary TEXT,
    
    -- Flexible evidence analysis (structure defined by dimension config)
    evidence_analysis JSONB DEFAULT '{}',
    -- Structure: {
    --   "total_relevant_words": int,
    --   "evidence_threshold_met": bool,
    --   "specificity_score": int,
    --   "quality_indicators": {"key": number}
    -- }
    
    -- Dynamic scoring breakdown (accommodates any scoring logic)
    scoring_breakdown JSONB DEFAULT '{}',
    -- Structure: {
    --   "base_score": int,
    --   "evidence_adjustments": {"key": number},
    --   "contextual_adjustments": {"key": number},
    --   "scoring_rationale": "string"
    -- }
    
    -- AI outputs
    confidence_score INTEGER DEFAULT 0 CHECK (confidence_score >= 0 AND confidence_score <= 10),
    detailed_reasoning TEXT,
    matched_criteria JSONB DEFAULT '[]', -- Array of matched criteria
    
    -- Extensible analysis metadata
    analysis_metadata JSONB DEFAULT '{}',
    
    -- System metadata
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_used VARCHAR(100),
    analysis_version VARCHAR(20) DEFAULT '3.0'
);

-- Create indexes for performance
CREATE INDEX idx_generic_analysis_content_id ON generic_dimension_analysis(content_analysis_id);
CREATE INDEX idx_generic_analysis_dimension_id ON generic_dimension_analysis(dimension_id);
CREATE INDEX idx_generic_analysis_score ON generic_dimension_analysis(final_score);
CREATE INDEX idx_generic_analysis_analyzed_at ON generic_dimension_analysis(analyzed_at);
CREATE INDEX idx_generic_analysis_content_dimension ON generic_dimension_analysis(content_analysis_id, dimension_id);

-- Migration: Add generic dimensions support to existing tables
ALTER TABLE client_analysis_config 
ADD COLUMN generic_dimensions_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN generic_dimensions_config JSONB DEFAULT '{}';

-- Migration: Update content_analysis table
ALTER TABLE content_analysis 
ADD COLUMN generic_dimension_scores JSONB DEFAULT '{}',
ADD COLUMN evidence_analysis JSONB DEFAULT '{}';

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_generic_dimensions_updated_at 
    BEFORE UPDATE ON generic_custom_dimensions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE generic_custom_dimensions IS 'Completely generic custom dimensions configuration that can handle any analysis framework';
COMMENT ON TABLE generic_dimension_analysis IS 'Generic analysis results with flexible evidence analysis and scoring breakdown';
COMMENT ON COLUMN generic_custom_dimensions.ai_context IS 'AI context providing overall understanding of the dimension purpose and approach';
COMMENT ON COLUMN generic_custom_dimensions.criteria IS 'Flexible criteria structure defining what counts, signals, and exclusions';
COMMENT ON COLUMN generic_custom_dimensions.scoring_framework IS 'Configurable scoring framework with levels, evidence requirements, and contextual rules';
COMMENT ON COLUMN generic_dimension_analysis.evidence_analysis IS 'Flexible evidence analysis structure defined by dimension configuration';
COMMENT ON COLUMN generic_dimension_analysis.scoring_breakdown IS 'Dynamic scoring breakdown accommodating any scoring logic';
