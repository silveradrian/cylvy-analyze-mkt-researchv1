-- Database Schema Cleanup Recommendations
-- WARNING: This is a recommendation script - review carefully before executing
-- Always backup your database before making schema changes

-- =====================================================
-- PHASE 1: Document Current State
-- =====================================================

-- Add comments to clarify table purposes
COMMENT ON TABLE content_analysis IS 'DEPRECATED - Original content analysis table. Use optimized_content_analysis instead';
COMMENT ON TABLE generic_dimension_analysis IS 'DEPRECATED - Generic dimension analysis. Merged into optimized_dimension_analysis';
COMMENT ON TABLE scraped_content IS 'Stores raw scraped HTML content from URLs';
COMMENT ON TABLE optimized_content_analysis IS 'Current production content analysis table with reduced verbosity';

-- =====================================================
-- PHASE 2: Add Missing Foreign Keys
-- =====================================================

-- Link scraped content to SERP results
ALTER TABLE scraped_content 
ADD COLUMN serp_result_id UUID,
ADD CONSTRAINT scraped_content_serp_result_id_fkey 
    FOREIGN KEY (serp_result_id) REFERENCES serp_results(id);

-- Link content analysis to projects
ALTER TABLE content_analysis 
ADD COLUMN project_id UUID,
ADD CONSTRAINT content_analysis_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES client_config(id);

-- Link SERP results to projects
ALTER TABLE serp_results 
ADD COLUMN project_id UUID,
ADD CONSTRAINT serp_results_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES client_config(id);

-- =====================================================
-- PHASE 3: Clean Up Unused Tables (After Verification)
-- =====================================================

-- First, verify these tables are truly empty and unused
DO $$
DECLARE
    table_name TEXT;
    row_count INTEGER;
BEGIN
    FOR table_name IN 
        SELECT unnest(ARRAY[
            'job_queue',
            'error_categories', 
            'retry_history',
            'service_health_metrics',
            'pipeline_phase_status',
            'historical_page_content_changes',
            'historical_page_lifecycle'
        ])
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I', table_name) INTO row_count;
        RAISE NOTICE 'Table % has % rows', table_name, row_count;
    END LOOP;
END $$;

-- After verification, drop unused tables
-- DROP TABLE IF EXISTS job_queue CASCADE;
-- DROP TABLE IF EXISTS error_categories CASCADE;
-- DROP TABLE IF EXISTS retry_history CASCADE;
-- DROP TABLE IF EXISTS service_health_metrics CASCADE;
-- DROP TABLE IF EXISTS pipeline_phase_status CASCADE;

-- =====================================================
-- PHASE 4: Consolidate Company Data
-- =====================================================

-- Create a unified company view combining all sources
CREATE OR REPLACE VIEW unified_company_data AS
SELECT 
    COALESCE(cp.domain, cd.domain, cc.company_domain) as domain,
    COALESCE(cp.name, cc.company_name) as company_name,
    CASE 
        WHEN cc.company_profile IS NOT NULL THEN cc.company_profile
        WHEN cp.profile_data IS NOT NULL THEN cp.profile_data
        ELSE '{}'::jsonb
    END as profile_data,
    GREATEST(
        cp.updated_at,
        cd.created_at,
        cc.updated_at
    ) as last_updated
FROM company_profiles cp
FULL OUTER JOIN company_domains cd ON cp.id = cd.company_id  
FULL OUTER JOIN client_config cc ON cp.domain = cc.company_domain;

-- =====================================================
-- PHASE 5: Create Consolidated Pipeline View
-- =====================================================

CREATE OR REPLACE VIEW pipeline_status_unified AS
SELECT 
    pe.id as execution_id,
    pe.pipeline_mode,
    pe.started_at,
    pe.completed_at,
    ps.current_phase,
    ps.phase_started_at,
    ps.phase_data,
    ps.updated_at as state_updated_at,
    pch.phase as checkpoint_phase,
    pch.checkpoint_data,
    pch.created_at as checkpoint_at
FROM pipeline_executions pe
LEFT JOIN pipeline_state ps ON pe.id = ps.pipeline_execution_id
LEFT JOIN pipeline_checkpoints pch ON pe.id = pch.pipeline_execution_id
ORDER BY pe.started_at DESC, pch.created_at DESC;

-- =====================================================
-- PHASE 6: Add Indexes for Performance
-- =====================================================

-- Critical missing indexes
CREATE INDEX IF NOT EXISTS idx_serp_results_url ON serp_results(url);
CREATE INDEX IF NOT EXISTS idx_serp_results_project ON serp_results(project_id);
CREATE INDEX IF NOT EXISTS idx_content_analysis_analyzed_at ON content_analysis(analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_content_url_hash ON scraped_content(md5(url));

-- =====================================================
-- PHASE 7: Add Consistency Constraints
-- =====================================================

-- Ensure pipeline states are consistent
ALTER TABLE pipeline_state 
ADD CONSTRAINT check_phase_valid 
CHECK (current_phase IN (
    'keyword_metrics_enrichment',
    'serp_collection', 
    'company_enrichment',
    'video_enrichment',
    'content_scraping',
    'content_analysis',
    'dsi_calculation'
));

-- Ensure scores are within valid range
ALTER TABLE optimized_dimension_analysis
ADD CONSTRAINT check_score_range CHECK (score >= 0 AND score <= 10),
ADD CONSTRAINT check_confidence_range CHECK (confidence >= 0 AND confidence <= 10);

-- =====================================================
-- PHASE 8: Create Migration Path
-- =====================================================

-- Helper function to migrate content analysis data
CREATE OR REPLACE FUNCTION migrate_to_optimized_analysis()
RETURNS void AS $$
BEGIN
    -- Migrate from content_analysis to optimized_content_analysis
    INSERT INTO optimized_content_analysis (
        url,
        project_id,
        overall_insights,
        analyzer_version,
        analyzed_at
    )
    SELECT 
        url,
        NULL, -- Add project_id if available
        summary as overall_insights,
        'migrated-1.0' as analyzer_version,
        analyzed_at
    FROM content_analysis
    WHERE NOT EXISTS (
        SELECT 1 FROM optimized_content_analysis oca 
        WHERE oca.url = content_analysis.url
    );
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- PHASE 9: Data Integrity Report
-- =====================================================

CREATE OR REPLACE VIEW data_integrity_report AS
SELECT 
    'Orphaned SERP results' as issue,
    COUNT(*) as count
FROM serp_results s
WHERE NOT EXISTS (
    SELECT 1 FROM scraped_content sc WHERE sc.url = s.url
)
UNION ALL
SELECT 
    'Unanalyzed content',
    COUNT(*)
FROM scraped_content sc
WHERE NOT EXISTS (
    SELECT 1 FROM optimized_content_analysis oca WHERE oca.url = sc.url
)
UNION ALL
SELECT 
    'Keywords without SERP results',
    COUNT(*)
FROM keywords k
WHERE NOT EXISTS (
    SELECT 1 FROM serp_results s WHERE s.keyword_id = k.id
);

-- =====================================================
-- PHASE 10: Create Simplified Schema Documentation
-- =====================================================

COMMENT ON TABLE client_config IS 'Main project/client configuration including company profile';
COMMENT ON TABLE keywords IS 'Keywords to track for each project';
COMMENT ON TABLE serp_results IS 'Search engine results for tracked keywords';
COMMENT ON TABLE scraped_content IS 'Raw HTML content from discovered URLs';
COMMENT ON TABLE optimized_content_analysis IS 'AI analysis results with concise insights';
COMMENT ON TABLE pipeline_executions IS 'Pipeline run history and status';

-- View the current state
SELECT 
    schemaname,
    tablename,
    obj_description((schemaname||'.'||tablename)::regclass, 'pg_class') as description
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;

