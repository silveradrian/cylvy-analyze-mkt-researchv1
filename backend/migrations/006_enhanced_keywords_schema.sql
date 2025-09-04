-- Enhanced Keywords Schema for Complete CSV Support
-- Migration: 006_enhanced_keywords_schema.sql

-- Add missing columns to keywords table
ALTER TABLE keywords 
ADD COLUMN IF NOT EXISTS all_categories TEXT, -- Semicolon separated categories
ADD COLUMN IF NOT EXISTS client_rationale TEXT, -- Why this keyword matters to client
ADD COLUMN IF NOT EXISTS persona_rationale TEXT, -- Why this keyword matches personas  
ADD COLUMN IF NOT EXISTS seo_rationale TEXT, -- SEO strategy reasoning
ADD COLUMN IF NOT EXISTS country_focus VARCHAR(10)[] DEFAULT '{US,UK}'; -- Array of target countries

-- Update the is_brand column to be more flexible (keeping existing boolean for compatibility)
ALTER TABLE keywords 
ADD COLUMN IF NOT EXISTS brand_keywords TEXT[]; -- Array of branded terms to check against

-- Create index for country-specific queries
CREATE INDEX IF NOT EXISTS idx_keywords_country_focus ON keywords USING GIN(country_focus);

-- Create index for category searching
CREATE INDEX IF NOT EXISTS idx_keywords_all_categories ON keywords(all_categories);
CREATE INDEX IF NOT EXISTS idx_keywords_category ON keywords(category);

-- Add constraint to ensure valid JTBD stages
ALTER TABLE keywords 
ADD CONSTRAINT IF NOT EXISTS chk_jtbd_stage 
CHECK (jtbd_stage IS NULL OR jtbd_stage IN ('Awareness', 'Consideration', 'Decision', 'Retention', 'Advocacy'));

-- Create a view for easier keyword querying with country filtering
CREATE OR REPLACE VIEW keywords_by_country AS
SELECT 
    k.id,
    k.keyword,
    k.category,
    k.all_categories,
    k.jtbd_stage,
    k.avg_monthly_searches,
    k.client_score,
    k.persona_score,
    k.seo_score,
    k.composite_score,
    k.client_rationale,
    k.persona_rationale,
    k.seo_rationale,
    k.is_brand,
    unnest(k.country_focus) as country,
    k.created_at,
    k.updated_at
FROM keywords k;

-- Create country-specific keyword counts view for analytics
CREATE OR REPLACE VIEW keyword_country_stats AS
SELECT 
    unnest(country_focus) as country,
    COUNT(*) as keyword_count,
    AVG(client_score) as avg_client_score,
    AVG(persona_score) as avg_persona_score,
    AVG(seo_score) as avg_seo_score,
    COUNT(*) FILTER (WHERE is_brand = true) as branded_keywords
FROM keywords 
GROUP BY unnest(country_focus);

-- Add comment for documentation
COMMENT ON COLUMN keywords.all_categories IS 'Semicolon-separated list of all relevant categories';
COMMENT ON COLUMN keywords.client_rationale IS 'Business justification for why this keyword is important';
COMMENT ON COLUMN keywords.persona_rationale IS 'Explanation of how this keyword aligns with target personas';
COMMENT ON COLUMN keywords.seo_rationale IS 'SEO strategy reasoning for targeting this keyword';
COMMENT ON COLUMN keywords.country_focus IS 'Array of country codes where this keyword should be tracked';

-- Create function to parse and clean categories
CREATE OR REPLACE FUNCTION parse_categories(categories_text TEXT)
RETURNS TEXT[] AS $$
BEGIN
    IF categories_text IS NULL OR trim(categories_text) = '' THEN
        RETURN '{}';
    END IF;
    
    -- Split by semicolon, trim whitespace, and filter empty values
    RETURN ARRAY(
        SELECT trim(category) 
        FROM unnest(string_to_array(categories_text, ';')) AS category
        WHERE trim(category) != ''
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

