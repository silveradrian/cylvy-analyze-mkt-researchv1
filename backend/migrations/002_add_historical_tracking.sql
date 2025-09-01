-- Migration: Add Historical Data Tracking Tables
-- Purpose: Enable month-over-month DSI and page-level analytics
-- Single-instance deployment (no multi-tenancy)

-- Historical DSI snapshots for company-level trends
CREATE TABLE historical_dsi_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,
    company_domain VARCHAR(255) NOT NULL,
    
    -- DSI metrics snapshot
    dsi_score DECIMAL(5,2) NOT NULL,
    dsi_rank INTEGER NOT NULL,
    keyword_coverage DECIMAL(5,2) NOT NULL,
    traffic_share DECIMAL(5,2) NOT NULL,
    persona_score DECIMAL(4,3) NOT NULL,
    
    -- Supporting metrics
    unique_keywords INTEGER NOT NULL,
    unique_pages INTEGER NOT NULL,
    estimated_traffic INTEGER NOT NULL,
    
    -- Company info at time of snapshot
    company_name VARCHAR(255),
    source_type VARCHAR(50),
    industry VARCHAR(100),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(snapshot_date, company_domain)
);

-- Historical page-level DSI tracking
CREATE TABLE historical_page_dsi_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,
    
    -- Page identification
    url VARCHAR(2048) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    page_title VARCHAR(500),
    content_hash VARCHAR(64), -- To detect content changes
    
    -- DSI metrics
    page_dsi_score DECIMAL(5,2) NOT NULL DEFAULT 0,
    page_dsi_rank INTEGER,
    keyword_count INTEGER DEFAULT 0,
    estimated_traffic INTEGER DEFAULT 0,
    
    -- SERP performance
    avg_position DECIMAL(4,1) DEFAULT 0,
    top_10_keywords INTEGER DEFAULT 0,
    total_keyword_appearances INTEGER DEFAULT 0,
    
    -- Content analysis scores
    content_classification VARCHAR(50),
    persona_alignment_scores JSONB,
    jtbd_phase VARCHAR(100),
    jtbd_alignment_score DECIMAL(4,3) DEFAULT 0,
    sentiment VARCHAR(20),
    
    -- Content metrics
    word_count INTEGER,
    content_quality_score DECIMAL(4,3) DEFAULT 0,
    freshness_score DECIMAL(4,3) DEFAULT 0,
    
    -- Engagement proxies
    serp_click_potential DECIMAL(4,3) DEFAULT 0,
    brand_mention_count INTEGER DEFAULT 0,
    competitor_mention_count INTEGER DEFAULT 0,
    
    -- Source information
    source_type VARCHAR(50),
    industry VARCHAR(100),
    
    -- Page lifecycle tracking
    first_seen_date DATE,
    last_seen_date DATE,
    is_active BOOLEAN DEFAULT true,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(snapshot_date, url)
);

-- Page content change tracking
CREATE TABLE historical_page_content_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url VARCHAR(2048) NOT NULL,
    
    -- Change tracking
    snapshot_date DATE NOT NULL,
    change_type VARCHAR(50) NOT NULL, -- 'content_updated', 'title_changed', 'new_page', 'page_removed'
    
    -- Before/after comparison
    previous_content_hash VARCHAR(64),
    current_content_hash VARCHAR(64),
    previous_title VARCHAR(500),
    current_title VARCHAR(500),
    
    -- Impact analysis
    dsi_score_before DECIMAL(5,2),
    dsi_score_after DECIMAL(5,2),
    ranking_impact JSONB,
    
    -- Content analysis changes
    classification_before VARCHAR(50),
    classification_after VARCHAR(50),
    persona_scores_before JSONB,
    persona_scores_after JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Page lifecycle management
CREATE TABLE historical_page_lifecycle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Page identification
    url VARCHAR(2048) NOT NULL UNIQUE,
    domain VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    
    -- Lifecycle events
    first_discovered DATE NOT NULL,
    last_seen_in_serps DATE,
    disappeared_date DATE,
    
    -- Performance summary
    peak_dsi_score DECIMAL(5,2) DEFAULT 0,
    peak_dsi_date DATE,
    avg_dsi_score DECIMAL(5,2) DEFAULT 0,
    total_days_active INTEGER DEFAULT 0,
    
    -- Traffic summary
    total_estimated_traffic INTEGER DEFAULT 0,
    peak_traffic_month DATE,
    peak_monthly_traffic INTEGER DEFAULT 0,
    
    -- Content summary
    primary_content_classification VARCHAR(50),
    primary_persona_target VARCHAR(100),
    keyword_appearances_count INTEGER DEFAULT 0,
    
    -- Current status
    lifecycle_status VARCHAR(20) DEFAULT 'active', -- 'active', 'declining', 'disappeared', 'archived'
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content metrics snapshots
CREATE TABLE historical_content_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL UNIQUE,
    
    -- Volume metrics
    total_serp_results INTEGER DEFAULT 0,
    total_content_analyzed INTEGER DEFAULT 0,
    total_companies_tracked INTEGER DEFAULT 0,
    
    -- Content type breakdown
    organic_results INTEGER DEFAULT 0,
    news_results INTEGER DEFAULT 0,
    video_results INTEGER DEFAULT 0,
    
    -- Regional breakdown
    us_results INTEGER DEFAULT 0,
    uk_results INTEGER DEFAULT 0,
    
    -- Quality metrics
    avg_analysis_confidence DECIMAL(4,3) DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Keyword performance snapshots
CREATE TABLE historical_keyword_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,
    keyword_id UUID NOT NULL REFERENCES keywords(id),
    keyword_text VARCHAR(255) NOT NULL,
    
    -- Performance metrics
    total_results INTEGER DEFAULT 0,
    avg_position DECIMAL(4,1) DEFAULT 0,
    top_10_results INTEGER DEFAULT 0,
    
    -- Content type breakdown
    organic_results INTEGER DEFAULT 0,
    news_results INTEGER DEFAULT 0,
    video_results INTEGER DEFAULT 0,
    
    -- Traffic estimation
    estimated_monthly_traffic INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(snapshot_date, keyword_id)
);

-- Pipeline schedules table
CREATE TABLE pipeline_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Schedule status
    is_active BOOLEAN DEFAULT true,
    
    -- Configuration
    keywords_set VARCHAR(50) DEFAULT 'all', -- 'all', 'custom'
    custom_keywords JSONB,
    regions VARCHAR[] DEFAULT ARRAY['US', 'UK'],
    
    -- Content type schedules (JSON array of ContentTypeSchedule objects)
    content_schedules JSONB NOT NULL DEFAULT '[]',
    
    -- Execution settings
    max_concurrent_executions INTEGER DEFAULT 1,
    
    -- Notification settings
    notification_emails VARCHAR[],
    notify_on_completion BOOLEAN DEFAULT true,
    notify_on_error BOOLEAN DEFAULT true,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_executed_at TIMESTAMPTZ,
    next_execution_at TIMESTAMPTZ
);

-- Schedule execution tracking
CREATE TABLE schedule_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID NOT NULL REFERENCES pipeline_schedules(id) ON DELETE CASCADE,
    
    -- Execution details
    pipeline_id UUID,
    content_types VARCHAR[] NOT NULL,
    
    -- Timing
    scheduled_for TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Results
    results_summary JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline execution tracking
CREATE TABLE pipeline_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Execution details
    status VARCHAR(20) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    
    -- Phase results
    phase_results JSONB DEFAULT '{}',
    
    -- Summary statistics
    keywords_processed INTEGER DEFAULT 0,
    serp_results_collected INTEGER DEFAULT 0,
    companies_enriched INTEGER DEFAULT 0,
    videos_enriched INTEGER DEFAULT 0,
    content_analyzed INTEGER DEFAULT 0,
    
    -- Errors and warnings
    errors JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    
    -- Resource usage
    api_calls_made JSONB DEFAULT '{}',
    estimated_cost DECIMAL(10,2) DEFAULT 0.00,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_historical_dsi_date_domain 
  ON historical_dsi_snapshots(snapshot_date DESC, company_domain);

CREATE INDEX idx_historical_page_dsi_date_url 
  ON historical_page_dsi_snapshots(snapshot_date DESC, url);

CREATE INDEX idx_historical_page_dsi_domain_date 
  ON historical_page_dsi_snapshots(domain, snapshot_date DESC);

CREATE INDEX idx_historical_page_dsi_score 
  ON historical_page_dsi_snapshots(page_dsi_score DESC);

CREATE INDEX idx_pipeline_schedules_active_next 
  ON pipeline_schedules(is_active, next_execution_at) 
  WHERE is_active = true;

CREATE INDEX idx_schedule_executions_status_scheduled 
  ON schedule_executions(status, scheduled_for) 
  WHERE status IN ('pending', 'running');

CREATE INDEX idx_pipeline_executions_started 
  ON pipeline_executions(started_at DESC);

CREATE INDEX idx_historical_keyword_metrics_date_keyword 
  ON historical_keyword_metrics(snapshot_date DESC, keyword_id);

-- Create month-over-month views
CREATE VIEW dsi_month_over_month AS
WITH monthly_dsi AS (
  SELECT 
    company_domain,
    company_name,
    snapshot_date,
    dsi_score,
    dsi_rank,
    LAG(dsi_score) OVER (
      PARTITION BY company_domain 
      ORDER BY snapshot_date
    ) as prev_dsi_score,
    LAG(dsi_rank) OVER (
      PARTITION BY company_domain 
      ORDER BY snapshot_date  
    ) as prev_dsi_rank
  FROM historical_dsi_snapshots
)
SELECT 
  *,
  ROUND((dsi_score - COALESCE(prev_dsi_score, 0))::numeric, 2) as dsi_change_points,
  ROUND(
    CASE 
      WHEN prev_dsi_score > 0 THEN 
        ((dsi_score - prev_dsi_score) / prev_dsi_score * 100)::numeric
      ELSE 0 
    END, 1
  ) as dsi_change_percent,
  (prev_dsi_rank - dsi_rank) as rank_change
FROM monthly_dsi
WHERE prev_dsi_score IS NOT NULL;

CREATE VIEW page_dsi_month_over_month AS
WITH monthly_page_dsi AS (
  SELECT 
    url,
    domain,
    company_name,
    page_title,
    snapshot_date,
    page_dsi_score,
    page_dsi_rank,
    estimated_traffic,
    content_classification,
    LAG(page_dsi_score) OVER (
      PARTITION BY url 
      ORDER BY snapshot_date
    ) as prev_page_dsi_score,
    LAG(page_dsi_rank) OVER (
      PARTITION BY url 
      ORDER BY snapshot_date
    ) as prev_page_dsi_rank,
    LAG(estimated_traffic) OVER (
      PARTITION BY url 
      ORDER BY snapshot_date
    ) as prev_estimated_traffic
  FROM historical_page_dsi_snapshots
)
SELECT 
  *,
  ROUND((page_dsi_score - COALESCE(prev_page_dsi_score, 0))::numeric, 2) as dsi_change_points,
  ROUND(
    CASE 
      WHEN prev_page_dsi_score > 0 THEN 
        ((page_dsi_score - prev_page_dsi_score) / prev_page_dsi_score * 100)::numeric
      ELSE 0 
    END, 1
  ) as dsi_change_percent,
  (prev_page_dsi_rank - page_dsi_rank) as rank_change,
  (estimated_traffic - COALESCE(prev_estimated_traffic, 0)) as traffic_change
FROM monthly_page_dsi
WHERE prev_page_dsi_score IS NOT NULL;

-- Trending content view (last 30 days)
CREATE VIEW trending_content AS
WITH recent_snapshots AS (
  SELECT * FROM historical_page_dsi_snapshots
  WHERE snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
),
page_trends AS (
  SELECT 
    url,
    domain,
    company_name,
    page_title,
    MAX(page_dsi_score) as max_dsi,
    MIN(page_dsi_score) as min_dsi,
    AVG(page_dsi_score) as avg_dsi,
    MAX(page_dsi_score) - MIN(page_dsi_score) as dsi_improvement,
    COUNT(*) as snapshot_count,
    MAX(snapshot_date) as latest_snapshot
  FROM recent_snapshots
  GROUP BY url, domain, company_name, page_title
  HAVING COUNT(*) >= 2
)
SELECT 
  *,
  CASE 
    WHEN min_dsi > 0 THEN ROUND((dsi_improvement / min_dsi * 100)::numeric, 1)
    ELSE 0
  END as improvement_percent
FROM page_trends
WHERE dsi_improvement > 0;

-- Add triggers for updated_at
CREATE TRIGGER update_historical_page_lifecycle_updated_at 
  BEFORE UPDATE ON historical_page_lifecycle
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pipeline_schedules_updated_at 
  BEFORE UPDATE ON pipeline_schedules
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

