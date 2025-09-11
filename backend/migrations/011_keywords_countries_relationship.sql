-- Add support for keyword-country relationships
-- This allows keywords to be tracked in multiple countries and enables proper DSI landscape filtering

-- 1. Create keywords_countries relationship table
CREATE TABLE IF NOT EXISTS keywords_countries (
    keyword_id UUID NOT NULL,
    country_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (keyword_id, country_code),
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_keywords_countries_keyword ON keywords_countries(keyword_id);
CREATE INDEX IF NOT EXISTS idx_keywords_countries_country ON keywords_countries(country_code);

-- 2. Migrate any existing country data from keywords table
-- If keywords have a single country field, migrate it to the relationship table
DO $$
BEGIN
    -- Check if country column exists in keywords table
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'keywords' AND column_name = 'country') THEN
        -- Migrate existing country data
        INSERT INTO keywords_countries (keyword_id, country_code)
        SELECT id, UPPER(country) 
        FROM keywords 
        WHERE country IS NOT NULL AND country != ''
        ON CONFLICT DO NOTHING;
        
        RAISE NOTICE 'Migrated existing country data to keywords_countries table';
    END IF;
END $$;

-- 3. Create view for easy querying of keywords with their countries
CREATE OR REPLACE VIEW keywords_with_countries AS
SELECT 
    k.*,
    ARRAY_AGG(kc.country_code ORDER BY kc.country_code) as countries
FROM keywords k
LEFT JOIN keywords_countries kc ON k.id = kc.keyword_id
GROUP BY k.id;

-- 4. Create function to update keyword countries
CREATE OR REPLACE FUNCTION update_keyword_countries(
    p_keyword_id UUID,
    p_country_codes VARCHAR[]
) RETURNS VOID AS $$
BEGIN
    -- Delete existing countries
    DELETE FROM keywords_countries WHERE keyword_id = p_keyword_id;
    
    -- Insert new countries
    IF p_country_codes IS NOT NULL AND array_length(p_country_codes, 1) > 0 THEN
        INSERT INTO keywords_countries (keyword_id, country_code)
        SELECT p_keyword_id, UPPER(unnest(p_country_codes))
        ON CONFLICT DO NOTHING;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 5. Create function to bulk assign countries to keywords
CREATE OR REPLACE FUNCTION bulk_assign_keyword_countries(
    p_keyword_ids UUID[],
    p_country_codes VARCHAR[]
) RETURNS TABLE(keywords_updated INT, countries_assigned INT) AS $$
DECLARE
    v_keywords_updated INT;
    v_countries_assigned INT;
BEGIN
    -- Count keywords to update
    v_keywords_updated := array_length(p_keyword_ids, 1);
    
    -- Insert country assignments for all keywords
    INSERT INTO keywords_countries (keyword_id, country_code)
    SELECT keyword_id, UPPER(country_code)
    FROM unnest(p_keyword_ids) AS keyword_id
    CROSS JOIN unnest(p_country_codes) AS country_code
    ON CONFLICT DO NOTHING;
    
    -- Count actual insertions
    GET DIAGNOSTICS v_countries_assigned = ROW_COUNT;
    
    RETURN QUERY SELECT v_keywords_updated, v_countries_assigned;
END;
$$ LANGUAGE plpgsql;

-- 6. Update landscape assignment logic to consider countries
-- Create view that shows keywords available for landscape assignment based on country
CREATE OR REPLACE VIEW landscape_available_keywords AS
WITH keyword_country_data AS (
    SELECT 
        k.*,
        kc.country_code
    FROM keywords k
    LEFT JOIN keywords_countries kc ON k.id = kc.keyword_id
)
SELECT DISTINCT
    kcd.id,
    kcd.keyword,
    kcd.category,
    kcd.avg_monthly_searches,
    kcd.country_code,
    CASE 
        WHEN kcd.country_code = 'US' THEN 'DSI - USA Market'
        WHEN kcd.country_code = 'UK' THEN 'DSI - UK Market'
        WHEN kcd.country_code = 'DE' THEN 'DSI - Germany Market'
        WHEN kcd.country_code = 'SA' THEN 'DSI - Saudi Arabia Market'
        WHEN kcd.country_code = 'VN' THEN 'DSI - Vietnam Market'
        ELSE NULL
    END as suggested_country_landscape,
    CASE
        WHEN LOWER(kcd.category) LIKE '%payment%' THEN 'DSI - Payments'
        WHEN LOWER(kcd.category) LIKE '%lending%' THEN 'DSI - Lending'
        WHEN LOWER(kcd.category) LIKE '%universal banking%' THEN 'DSI - Universal Banking'
        ELSE NULL
    END as suggested_business_landscape
FROM keyword_country_data kcd;

-- Add comments for documentation
COMMENT ON TABLE keywords_countries IS 'Maps keywords to countries where they should be tracked for SERP analysis';
COMMENT ON COLUMN keywords_countries.country_code IS 'ISO country code (US, UK, DE, etc.)';
COMMENT ON FUNCTION update_keyword_countries IS 'Updates the countries assigned to a specific keyword';
COMMENT ON FUNCTION bulk_assign_keyword_countries IS 'Assigns multiple countries to multiple keywords in bulk';
COMMENT ON VIEW keywords_with_countries IS 'Keywords with their assigned countries as an array';
COMMENT ON VIEW landscape_available_keywords IS 'Keywords with suggested landscape assignments based on country and category';

