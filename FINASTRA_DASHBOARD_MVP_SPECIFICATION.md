# Finastra Dashboard MVP Specification

## Overview

This document specifies the **MVP dashboard views for Finastra** as the first client. The dashboard provides DSI (Digital Share Index) analytics across Finastra's digital landscapes with geographic and business unit breakdowns.

**Timeline**: 2-day development sprint
**Client**: Finastra (client_id: "finastra")

---

## MVP Dashboard Views

### 1. 📊 **Summary Dashboard**

**Purpose**: Executive overview of Finastra's DSI performance

#### Vital Stats Cards
```sql
-- Finastra overall performance metrics
SELECT 
    COUNT(DISTINCT ldm.landscape_id) as total_landscapes,
    AVG(CASE WHEN ldm.entity_type = 'company' AND ldm.entity_domain LIKE '%finastra%' THEN ldm.dsi_score END) as avg_finastra_dsi,
    MAX(CASE WHEN ldm.entity_type = 'company' AND ldm.entity_domain LIKE '%finastra%' THEN ldm.dsi_score END) as best_finastra_dsi,
    AVG(CASE WHEN ldm.entity_type = 'company' AND ldm.entity_domain LIKE '%finastra%' THEN ldm.rank_in_landscape END) as avg_rank,
    SUM(CASE WHEN ldm.entity_type = 'company' AND ldm.entity_domain LIKE '%finastra%' THEN ldm.estimated_traffic END) as total_traffic
FROM landscape_dsi_metrics ldm
WHERE ldm.client_id = 'finastra'
AND ldm.calculation_date = CURRENT_DATE;
```

#### DSI Score + Rank (Finastra)
```sql
-- Current Finastra DSI performance across all landscapes
SELECT 
    cl.landscape_name,
    cl.business_unit,
    cl.region,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.total_entities_in_landscape,
    ldm.market_position
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
WHERE ldm.client_id = 'finastra'
AND ldm.entity_domain LIKE '%finastra%'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.dsi_score DESC;
```

#### DSI Score by Business Unit (Finastra)
```sql
-- Finastra performance grouped by BU
SELECT 
    cl.business_unit,
    COUNT(*) as landscape_count,
    AVG(ldm.dsi_score) as avg_dsi_score,
    MAX(ldm.dsi_score) as best_dsi_score,
    AVG(ldm.rank_in_landscape) as avg_rank,
    SUM(ldm.estimated_traffic) as total_bu_traffic
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
WHERE ldm.client_id = 'finastra'
AND ldm.entity_domain LIKE '%finastra%'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
GROUP BY cl.business_unit
ORDER BY avg_dsi_score DESC;
```

#### DSI Score by Geography (Finastra)
```sql
-- Finastra performance grouped by region
SELECT 
    cl.region,
    COUNT(*) as landscape_count,
    AVG(ldm.dsi_score) as avg_dsi_score,
    MAX(ldm.dsi_score) as best_dsi_score,
    AVG(ldm.rank_in_landscape) as avg_rank
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
WHERE ldm.client_id = 'finastra'
AND ldm.entity_domain LIKE '%finastra%'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
GROUP BY cl.region
ORDER BY avg_dsi_score DESC;
```

#### Month-over-Month Comparisons
```sql
-- Finastra MoM DSI changes
WITH current_month AS (
    SELECT 
        cl.business_unit,
        cl.region,
        AVG(ldm.dsi_score) as current_dsi,
        AVG(ldm.rank_in_landscape) as current_rank
    FROM landscape_dsi_metrics ldm
    JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
    WHERE ldm.client_id = 'finastra'
    AND ldm.entity_domain LIKE '%finastra%'
    AND ldm.entity_type = 'company'
    AND ldm.calculation_date = CURRENT_DATE
    GROUP BY cl.business_unit, cl.region
),
previous_month AS (
    SELECT 
        cl.business_unit,
        cl.region,
        AVG(ldm.dsi_score) as previous_dsi,
        AVG(ldm.rank_in_landscape) as previous_rank
    FROM landscape_dsi_metrics ldm
    JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
    WHERE ldm.client_id = 'finastra'
    AND ldm.entity_domain LIKE '%finastra%'
    AND ldm.entity_type = 'company'
    AND ldm.calculation_date = CURRENT_DATE - INTERVAL '30 days'
    GROUP BY cl.business_unit, cl.region
)
SELECT 
    cm.business_unit,
    cm.region,
    cm.current_dsi,
    pm.previous_dsi,
    (cm.current_dsi - pm.previous_dsi) as dsi_change,
    cm.current_rank,
    pm.previous_rank,
    (pm.previous_rank - cm.current_rank) as rank_change
FROM current_month cm
LEFT JOIN previous_month pm ON cm.business_unit = pm.business_unit AND cm.region = pm.region;
```

---

### 2. 🌍 **DSI Overview Dashboard**

**Purpose**: Market overview with all companies, filterable by geo/BU

#### Vital Stats
```sql
-- Market overview vital statistics
SELECT 
    COUNT(DISTINCT ldm.entity_domain) as total_companies,
    COUNT(DISTINCT ldm.landscape_id) as total_landscapes,
    AVG(ldm.dsi_score) as market_avg_dsi,
    MAX(ldm.dsi_score) as market_top_dsi,
    SUM(ldm.estimated_traffic) as total_market_traffic
FROM landscape_dsi_metrics ldm
WHERE ldm.client_id = 'finastra'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE;
```

#### DSI Score + Rank (All Companies)
```sql
-- All companies ranked with geo/BU selectors
SELECT 
    ldm.entity_name as company_name,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.market_position,
    cl.landscape_name,
    cl.business_unit,
    cl.region,
    cp.industry,
    CASE WHEN ldm.entity_domain LIKE '%finastra%' THEN true ELSE false END as is_finastra
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain
WHERE ldm.client_id = 'finastra'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
AND ($1 IS NULL OR cl.business_unit = $1)    -- BU filter
AND ($2 IS NULL OR cl.region = $2)           -- Geo filter
ORDER BY ldm.dsi_score DESC
LIMIT 100;
```

#### Competitor/Publisher Filters
```sql
-- Available filter values
SELECT DISTINCT 
    cp.industry as publisher_type,
    CASE WHEN ldm.entity_domain LIKE '%finastra%' THEN 'finastra'
         WHEN cp.industry LIKE '%Financial%' THEN 'competitor'
         ELSE 'publisher' 
    END as entity_category
FROM landscape_dsi_metrics ldm
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain
WHERE ldm.client_id = 'finastra'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE;
```

---

### 3. 🏢 **Company Details Drilldown**

**Purpose**: Deep dive into specific company performance

#### Company Vital Stats
```sql
-- Company-specific vital statistics
SELECT 
    cp.company_name,
    cp.domain,
    cp.industry,
    cp.employee_count,
    COUNT(DISTINCT ldm.landscape_id) as landscapes_present,
    AVG(ldm.dsi_score) as avg_dsi_across_landscapes,
    MAX(ldm.dsi_score) as best_dsi_score,
    MIN(ldm.rank_in_landscape) as best_rank,
    SUM(ldm.estimated_traffic) as total_traffic
FROM company_profiles cp
JOIN landscape_dsi_metrics ldm ON cp.domain = ldm.entity_domain
WHERE ldm.client_id = 'finastra'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
AND cp.domain = $1                           -- Company domain filter
GROUP BY cp.company_name, cp.domain, cp.industry, cp.employee_count;
```

#### Company Top Pages
```sql
-- Top performing pages for company
SELECT 
    ldm.entity_name as page_title,
    ldm.entity_url as url,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.unique_keywords,
    ldm.estimated_traffic,
    cl.landscape_name,
    hpds.sentiment,
    hpds.word_count
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
LEFT JOIN historical_page_dsi_snapshots hpds ON ldm.entity_url = hpds.url
WHERE ldm.client_id = 'finastra'
AND ldm.entity_domain = $1                   -- Company domain
AND ldm.entity_type = 'page'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.dsi_score DESC
LIMIT 20;
```

#### Company Top Videos
```sql
-- Top performing videos for company (from YouTube data)
SELECT 
    hpds.page_title as video_title,
    hpds.url,
    hpds.page_dsi_score,
    hpds.estimated_traffic,
    hpds.keyword_count,
    vs.view_count,
    vs.engagement_rate
FROM historical_page_dsi_snapshots hpds
LEFT JOIN video_snapshots vs ON hpds.url = vs.video_url
WHERE hpds.source_type = 'video'
AND hpds.domain = $1                         -- Company domain
AND hpds.snapshot_date = CURRENT_DATE
ORDER BY hpds.page_dsi_score DESC
LIMIT 10;
```

#### Persona Coverage Analysis
```sql
-- Content analysis by persona alignment
SELECT 
    cp.persona_name,
    cp.display_name,
    COUNT(DISTINCT oca.url) as total_content,
    AVG(CAST(oda.score AS FLOAT)) as avg_persona_score,
    COUNT(CASE WHEN CAST(oda.score AS FLOAT) >= 7.0 THEN 1 END) as high_alignment_content,
    COUNT(CASE WHEN oca.overall_sentiment = 'positive' THEN 1 END) as positive_content
FROM client_personas cp
CROSS JOIN optimized_content_analysis oca
JOIN scraped_content sc ON oca.url = sc.url
JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id AND oda.dimension_type = 'persona'
WHERE cp.client_id = 'finastra'
AND sc.domain = $1                           -- Company domain
GROUP BY cp.persona_name, cp.display_name
ORDER BY avg_persona_score DESC;
```

#### Strategic Imperative Alignment
```sql
-- Content alignment to strategic imperatives
SELECT 
    oda.dimension_value as strategic_imperative,
    COUNT(DISTINCT oca.url) as content_count,
    AVG(CAST(oda.score AS FLOAT)) as avg_alignment_score,
    SUM(hpds.estimated_traffic) as total_traffic_potential
FROM optimized_dimension_analysis oda
JOIN optimized_content_analysis oca ON oda.analysis_id = oca.id
JOIN scraped_content sc ON oca.url = sc.url
LEFT JOIN historical_page_dsi_snapshots hpds ON sc.url = hpds.url
WHERE oda.dimension_type = 'strategic_imperative'
AND sc.domain = $1                           -- Company domain
GROUP BY oda.dimension_value
ORDER BY avg_alignment_score DESC;
```

---

### 4. 📰 **News Dashboard**

**Purpose**: News publisher rankings and Finastra mention analysis

#### Publisher DSI Rankings
```sql
-- News publisher DSI rankings
SELECT 
    ldm.entity_name as publisher_name,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.unique_keywords,
    ldm.estimated_traffic,
    cp.industry
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain
WHERE ldm.client_id = 'finastra'
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
AND EXISTS (
    SELECT 1 FROM serp_results sr 
    WHERE sr.domain = ldm.entity_domain 
    AND sr.serp_type = 'news'
)
ORDER BY ldm.dsi_score DESC
LIMIT 50;
```

#### Finastra Mentions Count
```sql
-- Count of Finastra mentions in news content
SELECT 
    COUNT(DISTINCT oca.url) as total_mentions,
    COUNT(CASE WHEN oca.overall_sentiment = 'positive' THEN 1 END) as positive_mentions,
    COUNT(CASE WHEN oca.overall_sentiment = 'neutral' THEN 1 END) as neutral_mentions,
    COUNT(CASE WHEN oca.overall_sentiment = 'negative' THEN 1 END) as negative_mentions,
    AVG(hpds.estimated_traffic) as avg_reach_per_mention
FROM optimized_content_analysis oca
JOIN historical_page_dsi_snapshots hpds ON oca.url = hpds.url
WHERE hpds.source_type = 'news'
AND (
    oca.mentions::text ILIKE '%finastra%' OR
    oca.overall_insights ILIKE '%finastra%' OR
    oca.key_topics::text ILIKE '%finastra%'
)
AND hpds.snapshot_date = CURRENT_DATE;
```

#### Top News Stories
```sql
-- Top news stories mentioning Finastra
SELECT 
    hpds.page_title as headline,
    hpds.url,
    hpds.domain as publisher,
    hpds.page_dsi_score,
    hpds.estimated_traffic,
    oca.overall_sentiment,
    hpds.created_at as published_date
FROM historical_page_dsi_snapshots hpds
JOIN optimized_content_analysis oca ON hpds.url = oca.url
WHERE hpds.source_type = 'news'
AND (
    oca.mentions::text ILIKE '%finastra%' OR
    oca.overall_insights ILIKE '%finastra%'
)
AND hpds.snapshot_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY hpds.page_dsi_score DESC
LIMIT 20;
```

---

### 5. 📺 **Video Dashboard**

**Purpose**: YouTube/video content performance analysis

#### Finastra Video DSI Performance
```sql
-- Finastra video content DSI rankings
SELECT 
    hpds.page_title as video_title,
    hpds.url,
    hpds.page_dsi_score,
    hpds.page_dsi_rank,
    hpds.estimated_traffic,
    vs.view_count,
    vs.engagement_rate,
    vs.published_at
FROM historical_page_dsi_snapshots hpds
LEFT JOIN video_snapshots vs ON hpds.url = vs.video_url
WHERE hpds.source_type = 'video'
AND (
    hpds.domain LIKE '%finastra%' OR
    hpds.company_name ILIKE '%finastra%'
)
AND hpds.snapshot_date = CURRENT_DATE
ORDER BY hpds.page_dsi_score DESC
LIMIT 20;
```

#### All Video Rankings (with Geo/BU selectors)
```sql
-- All video content with selectable filters
SELECT 
    hpds.page_title as video_title,
    hpds.url,
    hpds.domain,
    hpds.company_name,
    hpds.page_dsi_score,
    hpds.page_dsi_rank,
    vs.view_count,
    vs.engagement_rate,
    -- Derive geography from SERP results
    STRING_AGG(DISTINCT sr.location, ', ') as regions_appearing
FROM historical_page_dsi_snapshots hpds
LEFT JOIN video_snapshots vs ON hpds.url = vs.video_url
LEFT JOIN serp_results sr ON hpds.url = sr.url AND sr.serp_type = 'video'
WHERE hpds.source_type = 'video'
AND hpds.snapshot_date = CURRENT_DATE
GROUP BY hpds.page_title, hpds.url, hpds.domain, hpds.company_name, 
         hpds.page_dsi_score, hpds.page_dsi_rank, vs.view_count, vs.engagement_rate
ORDER BY hpds.page_dsi_score DESC
LIMIT 50;
```

#### Most Viewed vs Most Engaged
```sql
-- Video performance analysis
SELECT 
    'most_viewed' as metric_type,
    hpds.page_title,
    hpds.url,
    hpds.company_name,
    vs.view_count as primary_metric,
    vs.engagement_rate as secondary_metric,
    hpds.page_dsi_score
FROM historical_page_dsi_snapshots hpds
JOIN video_snapshots vs ON hpds.url = vs.video_url
WHERE hpds.source_type = 'video'
AND vs.view_count IS NOT NULL
ORDER BY vs.view_count DESC
LIMIT 10

UNION ALL

SELECT 
    'most_engaged' as metric_type,
    hpds.page_title,
    hpds.url,
    hpds.company_name,
    vs.engagement_rate as primary_metric,
    vs.view_count as secondary_metric,
    hpds.page_dsi_score
FROM historical_page_dsi_snapshots hpds
JOIN video_snapshots vs ON hpds.url = vs.video_url
WHERE hpds.source_type = 'video'
AND vs.engagement_rate IS NOT NULL
ORDER BY vs.engagement_rate DESC
LIMIT 10;
```

---

### 6. 🎯 **Strategic Imperatives Dashboard**

**Purpose**: Content performance aligned to strategic imperatives

#### DSI Scores by Strategic Imperative (All 3)
```sql
-- Performance across all strategic imperatives
SELECT 
    oda.dimension_value as strategic_imperative,
    COUNT(DISTINCT oca.url) as total_content,
    AVG(CAST(oda.score AS FLOAT)) as avg_alignment_score,
    AVG(hpds.page_dsi_score) as avg_dsi_score,
    SUM(hpds.estimated_traffic) as total_traffic_potential,
    COUNT(CASE WHEN hpds.domain LIKE '%finastra%' THEN 1 END) as finastra_content_count
FROM optimized_dimension_analysis oda
JOIN optimized_content_analysis oca ON oda.analysis_id = oca.id
JOIN historical_page_dsi_snapshots hpds ON oca.url = hpds.url
WHERE oda.dimension_type = 'strategic_imperative'
AND hpds.snapshot_date = CURRENT_DATE
GROUP BY oda.dimension_value
ORDER BY avg_dsi_score DESC;
```

#### Individual Strategic Imperative Deep Dive
```sql
-- Detailed view for specific strategic imperative
SELECT 
    hpds.page_title,
    hpds.url,
    hpds.domain,
    hpds.company_name,
    hpds.page_dsi_score,
    hpds.page_dsi_rank,
    CAST(oda.score AS FLOAT) as si_alignment_score,
    hpds.estimated_traffic,
    cl.business_unit,
    cl.region
FROM optimized_dimension_analysis oda
JOIN optimized_content_analysis oca ON oda.analysis_id = oca.id
JOIN historical_page_dsi_snapshots hpds ON oca.url = hpds.url
LEFT JOIN serp_results sr ON hpds.url = sr.url
LEFT JOIN client_landscapes cl ON sr.keyword_id IN (
    SELECT clk.keyword_id FROM client_landscape_keywords clk WHERE clk.landscape_id = cl.id
)
WHERE oda.dimension_type = 'strategic_imperative'
AND oda.dimension_value = $1                 -- Specific SI filter
AND hpds.snapshot_date = CURRENT_DATE
AND ($2 IS NULL OR cl.region = $2)           -- Geo filter
AND ($3 IS NULL OR cl.business_unit = $3)    -- BU filter
ORDER BY hpds.page_dsi_score DESC
LIMIT 50;
```

---

## MVP API Endpoints

### Essential Endpoints for 2-Day Sprint

```python
# 1. Summary Dashboard
GET /api/v1/summary/vital-stats                    # Finastra vital statistics
GET /api/v1/summary/finastra-performance          # Finastra DSI across landscapes
GET /api/v1/summary/performance-by-bu             # Finastra by business unit
GET /api/v1/summary/performance-by-geo            # Finastra by geography
GET /api/v1/summary/month-over-month              # MoM comparisons

# 2. DSI Overview  
GET /api/v1/overview/vital-stats                  # Market vital stats
GET /api/v1/overview/company-rankings             # All company rankings
GET /api/v1/overview/filters                      # Available filter values

# 3. Company Details
GET /api/v1/companies/{domain}/overview           # Company vital stats
GET /api/v1/companies/{domain}/top-pages          # Company top pages
GET /api/v1/companies/{domain}/top-videos         # Company top videos
GET /api/v1/companies/{domain}/persona-coverage   # Persona analysis
GET /api/v1/companies/{domain}/strategic-alignment # SI alignment

# 4. News Dashboard
GET /api/v1/news/publisher-rankings               # Publisher DSI rankings
GET /api/v1/news/finastra-mentions               # Finastra mention analysis
GET /api/v1/news/top-stories                     # Top news stories

# 5. Video Dashboard  
GET /api/v1/video/finastra-performance            # Finastra video DSI
GET /api/v1/video/all-rankings                   # All video rankings
GET /api/v1/video/most-viewed                    # Most viewed videos
GET /api/v1/video/most-engaged                   # Most engaged videos

# 6. Strategic Imperatives
GET /api/v1/strategic-imperatives/overview        # All SI performance
GET /api/v1/strategic-imperatives/{si}/details    # Specific SI deep dive
```

---

## Client Configuration for Finastra

### Required Setup Data

```sql
-- 1. Create Finastra client
INSERT INTO clients (
    id, name, industry_focus, logo_url, brand_color_primary, 
    is_active, subscription_tier
) VALUES (
    'finastra', 'Finastra', 'Financial Services',
    'https://cdn.finastra.com/logo.png', '#663399',
    true, 'enterprise'
);

-- 2. Create Finastra personas (based on existing persona dimensions)
INSERT INTO client_personas (client_id, persona_name, display_name, weight_technical, weight_business, is_default)
VALUES 
    ('finastra', 'cto', 'Chief Technology Officer', 0.8, 0.2, true),
    ('finastra', 'product_manager', 'Product Manager', 0.4, 0.6, false),
    ('finastra', 'business_analyst', 'Business Analyst', 0.2, 0.8, false);

-- 3. Create Finastra SERP configuration
INSERT INTO client_serp_config (
    client_id, serp_types, max_position, countries,
    scheduling_organic, scheduling_news, scheduling_video
) VALUES (
    'finastra', 
    '["organic", "news", "video"]',
    100,  -- Max position 1-100
    '["US", "UK", "DE", "SA", "VN"]',
    'daily', 'hourly', 'weekly'
);

-- 4. Migrate existing landscapes to Finastra
INSERT INTO client_landscapes (
    id, client_id, landscape_name, business_unit, region, 
    description, is_active, display_order
)
SELECT 
    id, 'finastra', name, 
    CASE 
        WHEN name LIKE '%Payments%' THEN 'Payments'
        WHEN name LIKE '%Lending%' THEN 'Lending'
        WHEN name LIKE '%Banking%' THEN 'Banking'
        ELSE 'Technology'
    END as business_unit,
    CASE 
        WHEN name LIKE '%Germany%' THEN 'Germany'
        WHEN name LIKE '%UK%' THEN 'UK'
        WHEN name LIKE '%US%' THEN 'US'
        WHEN name LIKE '%Saudi%' THEN 'Saudi Arabia'
        WHEN name LIKE '%Vietnam%' THEN 'Vietnam'
        ELSE 'Global'
    END as region,
    name as description,
    true,
    ROW_NUMBER() OVER (ORDER BY name)
FROM digital_landscapes
WHERE is_active = true;
```

---

## Frontend Component Structure (MVP)

### React Component Hierarchy

```
FinastraDashboard/
├── SummaryDashboard/
│   ├── VitalStatsCards
│   ├── FinastraPerformanceChart  
│   ├── BusinessUnitBreakdown
│   ├── GeographyBreakdown
│   └── MonthOverMonthTrends
├── DSIOverview/
│   ├── MarketVitalStats
│   ├── CompanyRankingsTable
│   ├── FilterControls (Geo, BU, Competitors)
│   └── CompetitivePositioningChart
├── CompanyDetails/
│   ├── CompanyVitalStats
│   ├── LandscapePerformance
│   ├── TopPagesTable
│   ├── TopVideosTable
│   ├── PersonaCoverageChart
│   └── StrategicAlignmentAnalysis
├── NewsDashboard/
│   ├── PublisherRankings
│   ├── FinastraMentionsAnalysis
│   ├── TopStoriesTable
│   └── SentimentBreakdown
├── VideoDashboard/
│   ├── FinastraVideoPerformance
│   ├── AllVideoRankings
│   ├── MostViewedVideos
│   └── EngagementAnalysis
└── StrategicImperatives/
    ├── OverviewGrid (3 SIs)
    ├── IndividualSIAnalysis
    ├── ContentAlignmentChart
    └── OpportunityMatrix
```

### Essential UI Components

```typescript
// Key dashboard components for MVP
interface FinastraVitalStats {
  total_landscapes: number;
  avg_dsi_score: number;
  best_dsi_score: number;
  avg_rank: number;
  total_traffic: number;
  market_position_distribution: {
    leader: number;
    challenger: number;
    competitor: number;
    niche: number;
  };
}

interface LandscapePerformance {
  landscape_name: string;
  business_unit: string;
  region: string;
  dsi_score: number;
  rank: number;
  total_competitors: number;
  market_position: 'leader' | 'challenger' | 'competitor' | 'niche';
}

interface CompanyRanking {
  rank: number;
  company_name: string;
  domain: string;
  dsi_score: number;
  market_position: string;
  industry: string;
  is_finastra: boolean;
}
```

---

## Development Priority (2-Day Sprint)

### Day 1: Core Infrastructure + Summary Dashboard
- [ ] Create dashboard service container
- [ ] Database connection + authentication
- [ ] Summary dashboard APIs
- [ ] Basic React components
- [ ] Finastra branding integration

### Day 2: DSI Overview + Company Details
- [ ] DSI overview dashboard
- [ ] Company details drilldown
- [ ] Geographic/BU filtering
- [ ] Basic news/video views

### Out of Scope (Future Sprints)
- Complex multi-client support (focus on Finastra only)
- Advanced visualizations
- Real-time WebSocket updates
- Export functionality
- Strategic imperatives dashboard

---

## Simplified Data Access Pattern

Since this is MVP for Finastra only, simplify queries:

```python
# All queries can assume client_id = 'finastra' for MVP
FINASTRA_CLIENT_ID = 'finastra'

async def get_finastra_summary():
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(f"""
            SELECT 
                COUNT(DISTINCT ldm.landscape_id) as total_landscapes,
                AVG(CASE WHEN ldm.entity_domain LIKE '%finastra%' THEN ldm.dsi_score END) as avg_dsi,
                MAX(CASE WHEN ldm.entity_domain LIKE '%finastra%' THEN ldm.dsi_score END) as best_dsi
            FROM landscape_dsi_metrics ldm
            WHERE ldm.client_id = '{FINASTRA_CLIENT_ID}'
            AND ldm.entity_type = 'company'
            AND ldm.calculation_date = CURRENT_DATE
        """)
```

This MVP focuses on delivering immediate value for Finastra within the 2-day timeline while laying the foundation for future multi-client expansion.
