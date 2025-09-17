# Digital Landscape Dashboard Schema Documentation

## Overview

This documentation provides comprehensive schema information for developing a **multi-tenant, client-agnostic** digital landscape dashboard platform. The dashboard service is a containerized microservice that serves multiple clients, each with their own configurations, custom metrics, personas, and branding (logo only).

## Table of Contents

1. [Multi-Tenant Architecture](#multi-tenant-architecture)
2. [Client Configuration Tables](#client-configuration-tables)
3. [Core DSI Tables](#core-dsi-tables)
4. [Supporting Data Tables](#supporting-data-tables)
5. [Authentication Framework](#authentication-framework)
6. [Data Relationships](#data-relationships)
7. [Sample Queries](#sample-queries)
8. [Dashboard API Patterns](#dashboard-api-patterns)
9. [Performance Considerations](#performance-considerations)

---

## Multi-Tenant Architecture

### Client Isolation Strategy

**Data Isolation**: All tables include `client_id` for tenant separation
**Configuration Isolation**: Each client has custom metrics, personas, and landscapes
**Branding Isolation**: Client-specific logos and color schemes
**Permission Isolation**: Role-based access per client

### Client Hierarchy

```
Platform Level
├── Client A (e.g., "finastra")
│   ├── Custom Landscapes (e.g., "Payments", "Banking")
│   ├── Custom Personas (e.g., "CTO", "Product Manager")  
│   ├── Custom Metrics (e.g., weighted DSI formula)
│   └── Brand Assets (logo, colors)
├── Client B (e.g., "temenos")
│   ├── Different Landscapes (e.g., "Retail Banking", "Corporate")
│   └── Different Personas/Metrics
└── Client C...
```

---

## Client Configuration Tables

### 1. `clients` - Client Master Data

**Purpose**: Defines each client/tenant with their configuration

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `varchar` | NO | Client identifier (Primary Key) | `"finastra"`, `"temenos"`, `"fiserv"` |
| `name` | `varchar` | NO | Client display name | `"Finastra"`, `"Temenos"`, `"Fiserv"` |
| `industry_focus` | `varchar` | YES | Primary industry | `"Financial Services"`, `"Banking Technology"` |
| `logo_url` | `varchar` | YES | Client logo URL | `"https://cdn.example.com/finastra-logo.png"` |
| `brand_color_primary` | `varchar` | YES | Primary brand color | `"#663399"`, `"#0066CC"` |
| `brand_color_secondary` | `varchar` | YES | Secondary brand color | `"#F0F0F0"` |
| `timezone` | `varchar` | YES | Client timezone | `"UTC"`, `"America/New_York"` |
| `date_format` | `varchar` | YES | Preferred date format | `"YYYY-MM-DD"`, `"MM/DD/YYYY"` |
| `currency` | `varchar` | YES | Default currency | `"USD"`, `"EUR"`, `"GBP"` |
| `is_active` | `boolean` | NO | Client active status | `true`, `false` |
| `subscription_tier` | `varchar` | YES | Service tier | `"basic"`, `"premium"`, `"enterprise"` |
| `max_landscapes` | `integer` | YES | Landscape limit | `10`, `24`, `50` |
| `max_keywords` | `integer` | YES | Keyword limit | `100`, `500`, `1000` |
| `created_at` | `timestamp` | NO | Client onboarding date | |
| `updated_at` | `timestamp` | YES | Last configuration update | |

### 2. `client_personas` - Custom Persona Definitions

**Purpose**: Client-specific persona configurations for DSI calculations

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `client_id` | `varchar` | NO | Client reference | `"finastra"`, `"temenos"` |
| `persona_name` | `varchar` | NO | Persona identifier | `"cto"`, `"product_manager"`, `"business_analyst"` |
| `display_name` | `varchar` | NO | Human-readable name | `"Chief Technology Officer"`, `"Product Manager"` |
| `description` | `text` | YES | Persona description | `"Technical decision maker focused on architecture"` |
| `weight_technical` | `numeric` | YES | Technical content weight (0-1) | `0.8`, `0.3`, `0.6` |
| `weight_business` | `numeric` | YES | Business content weight (0-1) | `0.2`, `0.7`, `0.4` |
| `weight_strategic` | `numeric` | YES | Strategic content weight (0-1) | `0.6`, `0.8`, `0.5` |
| `jtbd_preferences` | `jsonb` | YES | JTBD stage preferences | `{"awareness": 0.3, "consideration": 0.5, "purchase": 0.2}` |
| `content_type_preferences` | `jsonb` | YES | Content type weights | `{"technical": 0.8, "case_study": 0.6, "news": 0.3}` |
| `is_default` | `boolean` | YES | Default persona for client | `true`, `false` |
| `created_at` | `timestamp` | NO | Creation time | |

### 3. `client_dimensions` - Custom Dimension Definitions

**Purpose**: Client-specific custom dimensions for content analysis

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `client_id` | `varchar` | NO | Client reference | `"finastra"` |
| `dimension_name` | `varchar` | NO | Dimension identifier | `"product_relevance"`, `"market_segment"`, `"use_case_type"` |
| `display_name` | `varchar` | NO | Human-readable name | `"Product Relevance"`, `"Market Segment"` |
| `dimension_type` | `varchar` | NO | Analysis type | `"categorical"`, `"score"`, `"boolean"` |
| `possible_values` | `jsonb` | YES | Allowed values for categorical | `["core_banking", "payments", "lending"]` |
| `score_range_min` | `numeric` | YES | Min score (for score type) | `1.0`, `0.0` |
| `score_range_max` | `numeric` | YES | Max score (for score type) | `10.0`, `100.0` |
| `description` | `text` | YES | Dimension description | `"Relevance to core banking products"` |
| `analysis_prompt` | `text` | YES | AI analysis prompt | `"Rate content relevance to core banking on 1-10 scale"` |
| `is_active` | `boolean` | NO | Currently used | `true`, `false` |
| `created_at` | `timestamp` | NO | Creation time | |

### 3. `client_serp_config` - SERP Collection Configuration

**Purpose**: Client-specific SERP collection settings

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `client_id` | `varchar` | NO | Client reference | `"finastra"` |
| `serp_types` | `jsonb` | NO | Enabled SERP types | `["organic", "news", "video"]` |
| `max_position` | `integer` | NO | Maximum SERP position | `20`, `50`, `100` |
| `countries` | `jsonb` | NO | Target countries | `["US", "UK", "DE", "SA", "VN"]` |
| `scheduling_organic` | `varchar` | YES | Organic collection frequency | `"daily"`, `"weekly"` |
| `scheduling_news` | `varchar` | YES | News collection frequency | `"hourly"`, `"daily"` |
| `scheduling_video` | `varchar` | YES | Video collection frequency | `"weekly"`, `"monthly"` |
| `exclude_domains` | `jsonb` | YES | Domains to exclude | `["spam.com", "lowquality.net"]` |
| `include_brand_terms` | `boolean` | YES | Include brand keywords | `true`, `false` |
| `created_at` | `timestamp` | NO | Creation time | |

### 4. `client_landscapes` - Client-Specific Landscape Definitions

**Purpose**: Each client can have completely different landscape definitions

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `client_id` | `varchar` | NO | Client reference | `"finastra"`, `"temenos"` |
| `landscape_name` | `varchar` | NO | Landscape name | `"Core Banking"`, `"Retail Banking"`, `"Wealth Management"` |
| `business_unit` | `varchar` | YES | BU mapping | `"Banking"`, `"Payments"`, `"Lending"` |
| `region` | `varchar` | YES | Geographic focus | `"North America"`, `"EMEA"`, `"APAC"`, `"Global"` |
| `description` | `text` | YES | Landscape description | `"Core banking platform solutions for retail banks"` |
| `keyword_selection_criteria` | `jsonb` | YES | Keyword filtering rules | `{"categories": ["banking", "platform"], "exclude_brand": true}` |
| `content_filters` | `jsonb` | YES | Content inclusion rules | `{"min_word_count": 200, "exclude_domains": ["spam.com"]}` |
| `custom_weightings` | `jsonb` | YES | Client-specific weightings | `{"persona_weight": 0.3, "traffic_weight": 0.5}` |
| `is_active` | `boolean` | NO | Currently active | `true`, `false` |
| `display_order` | `integer` | YES | Dashboard sort order | `1, 2, 3...` |
| `created_at` | `timestamp` | NO | Creation time | |
| `updated_at` | `timestamp` | YES | Last modification | |

### 5. `client_landscape_keywords` - Client-Specific Keyword Assignments

**Purpose**: Maps keywords to client-specific landscapes (replaces landscape_keywords)

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `client_id` | `varchar` | NO | Client reference | `"finastra"` |
| `landscape_id` | `uuid` | NO | Client landscape reference | |
| `keyword_id` | `uuid` | NO | Keyword reference | |
| `custom_category` | `varchar` | YES | Client-specific category | `"core_product"`, `"adjacent"`, `"competitive"` |
| `created_at` | `timestamp` | NO | Assignment date | |

---

## Core DSI Tables

### 6. `landscape_dsi_metrics` - Primary DSI Data Table

**Purpose**: Stores company, page, and keyword DSI metrics for each client's digital landscapes

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | `550e8400-e29b-41d4-a716-446655440000` |
| `client_id` | `varchar` | NO | **Client tenant identifier** | `"finastra"`, `"temenos"`, `"fiserv"` |
| `landscape_id` | `uuid` | NO | Reference to client_landscapes.id | `4e773f12-12b7-4118-b859-faadc0abc60b` |
| `calculation_date` | `date` | NO | Date of DSI calculation | `2025-09-17` |
| `entity_type` | `varchar` | NO | Type of entity | `company`, `page`, `keyword` |
| `entity_id` | `uuid` | NO | Unique identifier for entity | Various UUID formats |
| `entity_name` | `varchar` | YES | Display name | `"Finastra"`, `"Core Banking Solutions Guide"`, `"digital payments"` |
| `entity_domain` | `varchar` | YES | Associated domain | `"finastra.com"`, `"techcrunch.com"` |
| `entity_url` | `varchar` | YES | Specific URL (for pages) | `"https://techcrunch.com/article"` |
| `unique_keywords` | `integer` | YES | Number of unique keywords | `1-500` |
| `unique_pages` | `integer` | YES | Number of unique pages | `1-1000` |
| `keyword_coverage` | `numeric` | YES | Keyword coverage ratio (0-1) | `0.0234` (2.34%) |
| `estimated_traffic` | `bigint` | YES | Estimated monthly traffic | `50000` |
| `traffic_share` | `numeric` | YES | Share of total traffic (0-1) | `0.0567` (5.67%) |
| `persona_alignment` | `numeric` | YES | Persona relevance score (0-1) | `0.7834` (78.34%) |
| `funnel_value` | `numeric` | YES | Funnel stage value (0-1) | `0.6500` (65%) |
| `dsi_score` | `numeric` | YES | Final DSI score | `0.000001` to `100.0` |
| `rank_in_landscape` | `integer` | YES | Rank within landscape | `1, 2, 3...` |
| `total_entities_in_landscape` | `integer` | YES | Total entities in landscape | `500, 1000, 2000` |
| `market_position` | `varchar` | YES | Market position category | `leader`, `challenger`, `competitor`, `niche` |
| `calculation_period_days` | `integer` | YES | Calculation period | `30` (days) |
| `created_at` | `timestamp` | NO | Record creation time | `2025-09-17 18:45:00+00` |

**Indexes:**
- Primary: `id`
- Unique: `(client_id, landscape_id, calculation_date, entity_type, entity_id)`
- Performance: `(client_id, landscape_id, entity_type, dsi_score DESC)`
- Performance: `(client_id, calculation_date, entity_type)`
- Tenant Isolation: `(client_id, calculation_date)`

### 7. `historical_page_dsi_snapshots` - Global Page DSI Rankings

**Purpose**: Global page-level DSI rankings across all landscapes (not landscape-specific)

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `snapshot_date` | `date` | NO | Snapshot date | `2025-09-17` |
| `url` | `varchar` | NO | Page URL | `"https://techcrunch.com/fintech-guide"` |
| `domain` | `varchar` | NO | Domain | `"techcrunch.com"` |
| `company_name` | `varchar` | YES | Company name | `"TechCrunch"` |
| `page_title` | `varchar` | YES | Page title | `"Complete FinTech Guide 2025"` |
| `content_hash` | `varchar` | YES | Content hash for change detection | MD5 hash |
| `page_dsi_score` | `numeric` | YES | Global DSI score | `0.000` to `100.000` |
| `page_dsi_rank` | `integer` | YES | Global ranking | `1, 2, 3...` |
| `keyword_count` | `integer` | YES | Keywords ranking for | `1-50` |
| `estimated_traffic` | `integer` | YES | Estimated monthly traffic | `10000` |
| `avg_position` | `numeric` | YES | Average SERP position | `1.5` to `20.0` |
| `top_10_keywords` | `integer` | YES | Keywords in top 10 | `5` |
| `total_keyword_appearances` | `integer` | YES | Total SERP appearances | `25` |
| `content_classification` | `varchar` | YES | Content type | `"guide"`, `"news"`, `"product"` |
| `persona_alignment_scores` | `jsonb` | YES | Persona scores by type | `{"jtbd": 4.8, "persona": 6.33}` |
| `jtbd_phase` | `varchar` | YES | JTBD phase classification | `"awareness"`, `"consideration"`, `"purchase"` |
| `jtbd_alignment_score` | `numeric` | YES | JTBD alignment (0-10) | `7.5` |
| `sentiment` | `varchar` | YES | Content sentiment | `"positive"`, `"neutral"`, `"negative"` |
| `word_count` | `integer` | YES | Content word count | `500, 1200, 3000` |
| `content_quality_score` | `numeric` | YES | Quality score (0-1) | `0.85` |
| `freshness_score` | `numeric` | YES | Content freshness (0-1) | `0.95` |
| `serp_click_potential` | `numeric` | YES | Click potential (0-1) | `0.23` |
| `brand_mention_count` | `integer` | YES | Brand mentions | `3` |
| `competitor_mention_count` | `integer` | YES | Competitor mentions | `1` |
| `source_type` | `varchar` | YES | Content source | `"organic"`, `"news"`, `"video"` |
| `industry` | `varchar` | YES | Industry classification | `"Financial Services"`, `"Technology"` |
| `first_seen_date` | `date` | YES | First discovery date | `2025-09-15` |
| `last_seen_date` | `date` | YES | Last seen in SERPs | `2025-09-17` |
| `is_active` | `boolean` | YES | Currently active in SERPs | `true`, `false` |
| `created_at` | `timestamp` | NO | Record creation | |

### 8. `dsi_calculations` - Historical Company DSI Calculations

**Purpose**: Historical company-level DSI calculations (legacy format, less detailed than landscape_dsi_metrics)

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `calculation_date` | `date` | NO | Calculation date | `2025-09-17` |
| `company_rankings` | `jsonb` | YES | Company rankings data | JSON array |
| `page_rankings` | `jsonb` | YES | Page rankings data | JSON array |
| `total_companies` | `integer` | YES | Total companies ranked | `1500` |
| `total_pages` | `integer` | YES | Total pages ranked | `25000` |
| `keywords_analyzed` | `integer` | YES | Keywords in analysis | `287` |
| `created_at` | `timestamp` | NO | Record creation | |

---

## Supporting Data Tables

### 9. `digital_landscapes` - Landscape Definitions (Legacy)

**Purpose**: Defines the 24 digital landscapes and their configurations

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `name` | `varchar` | NO | Landscape name | `"Payments"`, `"Universal Banking + Germany"` |
| `description` | `text` | YES | Detailed description | `"Digital payment solutions and infrastructure"` |
| `business_unit` | `varchar` | YES | Associated BU | `"Payments"`, `"Banking"`, `"Lending"` |
| `region` | `varchar` | YES | Geographic focus | `"US"`, `"UK"`, `"Germany"`, `"Global"` |
| `is_active` | `boolean` | NO | Currently active | `true`, `false` |
| `created_at` | `timestamp` | NO | Creation time | |
| `updated_at` | `timestamp` | YES | Last update | |

### 10. `landscape_keywords` - Keyword Assignments (Legacy)

**Purpose**: Maps keywords to specific landscapes (replaced by client_landscape_keywords)

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `landscape_id` | `uuid` | NO | Landscape reference | |
| `keyword_id` | `uuid` | NO | Keyword reference | |
| `created_at` | `timestamp` | NO | Assignment date | |

### 11. `keywords` - Keyword Master Data

**Purpose**: Master keyword data with all dimensions and metrics

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `keyword` | `varchar` | NO | Keyword text | `"digital payments"`, `"core banking"` |
| `category` | `varchar` | YES | Keyword category | `"product"`, `"solution"`, `"technology"` |
| `jtbd_stage` | `varchar` | YES | Jobs-to-be-done stage | `"awareness"`, `"consideration"`, `"purchase"` |
| `is_brand` | `boolean` | YES | Brand keyword flag | `true`, `false` |
| `client_score` | `numeric` | YES | Client relevance (0-10) | `8.5` |
| `persona_score` | `numeric` | YES | Persona alignment (0-10) | `7.2` |
| `seo_score` | `numeric` | YES | SEO difficulty (0-10) | `6.8` |
| `composite_score` | `numeric` | YES | Overall score (0-10) | `7.5` |
| `avg_monthly_searches` | `integer` | YES | Google search volume | `12000` |
| `competition_level` | `varchar` | YES | Competition level | `"HIGH"`, `"MEDIUM"`, `"LOW"` |
| `low_bid_micros` | `bigint` | YES | CPC low bid (micros) | `2500000` ($2.50) |
| `high_bid_micros` | `bigint` | YES | CPC high bid (micros) | `15000000` ($15.00) |
| `competition_index` | `numeric` | YES | Competition index (0-1) | `0.67` |
| `metrics_updated_at` | `timestamp` | YES | Last metrics update | |
| `is_active` | `boolean` | YES | Currently active | `true` |
| `created_at` | `timestamp` | NO | Creation time | |

### 12. `company_profiles` - Company Master Data

**Purpose**: Enriched company information for companies appearing in DSI calculations

| Field | Type | Null | Description | Sample Values |
|-------|------|------|-------------|---------------|
| `id` | `uuid` | NO | Primary key | |
| `domain` | `varchar` | NO | Company domain | `"finastra.com"` |
| `company_name` | `varchar` | NO | Company name | `"Finastra"` |
| `industry` | `varchar` | YES | Industry classification | `"Financial Services"`, `"Technology"` |
| `employee_count` | `varchar` | YES | Employee count range | `"1001-5000"`, `"10001+"` |
| `description` | `text` | YES | Company description | Full company description |
| `source` | `varchar` | YES | Data source | `"cognism"`, `"clearbit"`, `"fallback"` |
| `source_type` | `varchar` | YES | Source type | `"api"`, `"manual"` |
| `confidence_score` | `numeric` | YES | Data confidence (0-1) | `0.95` |
| `created_at` | `timestamp` | NO | Record creation | |
| `updated_at` | `timestamp` | YES | Last update | |

---

## Data Relationships

### Primary Relationships for Dashboard Queries

```sql
-- Get landscape DSI data with company information (CLIENT-FILTERED)
SELECT 
    ldm.*,
    cl.landscape_name,
    cl.business_unit,
    cl.region,
    cp.company_name,
    cp.industry,
    cp.employee_count
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain
WHERE ldm.client_id = $1                    -- CRITICAL: Client isolation
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.dsi_score DESC;
```

### Entity Type Breakdown

**Company Entities** (`entity_type = 'company'`):
- `entity_id`: Company UUID from domain_company_mapping
- `entity_name`: Company name from enrichment
- `entity_domain`: Root domain (e.g., "finastra.com")
- `entity_url`: NULL
- `unique_keywords`: Keywords company ranks for
- `unique_pages`: Pages company has in SERPs

**Page Entities** (`entity_type = 'page'`):
- `entity_id`: Generated UUID from URL hash
- `entity_name`: Page title
- `entity_domain`: Page domain
- `entity_url`: Full page URL
- `unique_keywords`: Keywords page ranks for
- `unique_pages`: Always 1

**Keyword Entities** (`entity_type = 'keyword'`):
- `entity_id`: Keyword UUID from keywords table
- `entity_name`: Keyword text
- `entity_domain`: Empty string
- `entity_url`: NULL
- `unique_keywords`: Always 1
- `unique_pages`: Number of pages ranking for keyword

---

## DSI Score Calculations

### Company DSI Formula
```
DSI = (Keyword Coverage %) × (Traffic Share %) × (Persona Relevance 0-1)
```

Where:
- **Keyword Coverage**: `(company_keywords / total_landscape_keywords) * 100`
- **Traffic Share**: `(company_traffic / total_landscape_traffic) * 100`
- **Persona Relevance**: `(persona_score / 10.0)` - normalized to 0-1

### Page DSI Formula
```
DSI = (Traffic Share %) × (Persona Relevance 0-1)
```

### Keyword DSI Formula
```
DSI = (Market Presence) × (Traffic Potential) × (Relevance Score)
```

Where:
- **Market Presence**: `(serp_results / 100.0)`
- **Traffic Potential**: `(estimated_traffic / search_volume)`
- **Relevance Score**: `(persona_score / 10.0)`

---

## Sample Dashboard Queries

### 1. Top Companies by Landscape (Multi-Tenant)

```sql
-- Get top 20 companies in a specific client's landscape
SELECT 
    ldm.entity_name as company_name,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.market_position,
    ldm.unique_keywords,
    ldm.unique_pages,
    ldm.estimated_traffic,
    ldm.keyword_coverage * 100 as keyword_coverage_pct,
    ldm.traffic_share * 100 as traffic_share_pct,
    ldm.persona_alignment * 100 as persona_alignment_pct,
    cp.industry,
    cp.employee_count
FROM landscape_dsi_metrics ldm
JOIN client_landscapes cl ON ldm.landscape_id = cl.id AND ldm.client_id = cl.client_id
LEFT JOIN company_profiles cp ON ldm.entity_domain = cp.domain
WHERE ldm.client_id = $1                    -- CRITICAL: Client isolation
AND cl.landscape_name = $2                   -- Client's landscape name
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.rank_in_landscape
LIMIT 20;
```

### 2. Client Landscape Overview Dashboard

```sql
-- Get overview metrics for all client's landscapes
SELECT 
    cl.landscape_name,
    cl.business_unit,
    cl.region,
    cl.display_order,
    COUNT(CASE WHEN ldm.entity_type = 'company' THEN 1 END) as total_companies,
    COUNT(CASE WHEN ldm.entity_type = 'page' THEN 1 END) as total_pages,
    COUNT(CASE WHEN ldm.entity_type = 'keyword' THEN 1 END) as total_keywords,
    AVG(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as avg_company_dsi,
    MAX(CASE WHEN ldm.entity_type = 'company' THEN ldm.dsi_score END) as top_company_dsi,
    SUM(CASE WHEN ldm.entity_type = 'company' THEN ldm.estimated_traffic END) as total_landscape_traffic
FROM client_landscapes cl
LEFT JOIN landscape_dsi_metrics ldm ON cl.id = ldm.landscape_id 
    AND ldm.client_id = cl.client_id
    AND ldm.calculation_date = CURRENT_DATE
WHERE cl.client_id = $1                     -- CRITICAL: Client isolation
AND cl.is_active = true
GROUP BY cl.id, cl.landscape_name, cl.business_unit, cl.region, cl.display_order
ORDER BY cl.display_order, total_landscape_traffic DESC;
```

### 3. Company Deep Dive

```sql
-- Get detailed company performance across all landscapes
SELECT 
    dl.name as landscape_name,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.total_entities_in_landscape,
    ldm.market_position,
    ldm.unique_keywords,
    ldm.estimated_traffic,
    ldm.keyword_coverage * 100 as keyword_coverage_pct,
    ldm.traffic_share * 100 as traffic_share_pct
FROM landscape_dsi_metrics ldm
JOIN digital_landscapes dl ON ldm.landscape_id = dl.id
WHERE ldm.entity_domain = 'finastra.com'  -- Dynamic company filter
AND ldm.entity_type = 'company'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.dsi_score DESC;
```

### 4. Top Performing Content by Landscape

```sql
-- Get top content pieces for a landscape
SELECT 
    ldm.entity_name as page_title,
    ldm.entity_url as url,
    ldm.entity_domain as domain,
    ldm.dsi_score,
    ldm.rank_in_landscape,
    ldm.unique_keywords,
    ldm.estimated_traffic,
    hpds.sentiment,
    hpds.content_classification,
    hpds.brand_mention_count,
    hpds.word_count
FROM landscape_dsi_metrics ldm
LEFT JOIN historical_page_dsi_snapshots hpds ON ldm.entity_url = hpds.url
WHERE ldm.landscape_id = $1  -- Landscape UUID
AND ldm.entity_type = 'page'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.rank_in_landscape
LIMIT 50;
```

### 5. Keyword Performance Analysis

```sql
-- Get keyword performance within a landscape
SELECT 
    ldm.entity_name as keyword_text,
    ldm.dsi_score as keyword_dsi,
    ldm.rank_in_landscape,
    ldm.estimated_traffic,
    k.avg_monthly_searches,
    k.competition_level,
    k.persona_score,
    k.category,
    k.jtbd_stage,
    ROUND((k.low_bid_micros::float / 1000000)::numeric, 2) as low_cpc,
    ROUND((k.high_bid_micros::float / 1000000)::numeric, 2) as high_cpc
FROM landscape_dsi_metrics ldm
JOIN keywords k ON ldm.entity_id::text = k.id::text
WHERE ldm.landscape_id = $1  -- Landscape UUID
AND ldm.entity_type = 'keyword'
AND ldm.calculation_date = CURRENT_DATE
ORDER BY ldm.rank_in_landscape;
```

### 6. Competitive Intelligence

```sql
-- Compare companies across multiple landscapes
WITH company_performance AS (
    SELECT 
        ldm.entity_domain,
        ldm.entity_name,
        dl.name as landscape_name,
        dl.business_unit,
        ldm.dsi_score,
        ldm.rank_in_landscape,
        ldm.market_position,
        ROW_NUMBER() OVER (PARTITION BY ldm.entity_domain ORDER BY ldm.dsi_score DESC) as best_landscape_rank
    FROM landscape_dsi_metrics ldm
    JOIN digital_landscapes dl ON ldm.landscape_id = dl.id
    WHERE ldm.entity_type = 'company'
    AND ldm.calculation_date = CURRENT_DATE
    AND ldm.entity_domain IN ('finastra.com', 'temenos.com', 'fiserv.com')  -- Dynamic competitor list
)
SELECT 
    entity_domain,
    entity_name,
    COUNT(*) as landscapes_present,
    AVG(dsi_score) as avg_dsi_score,
    MAX(dsi_score) as best_dsi_score,
    STRING_AGG(landscape_name, ', ' ORDER BY dsi_score DESC) as top_landscapes
FROM company_performance
GROUP BY entity_domain, entity_name
ORDER BY avg_dsi_score DESC;
```

---

## Authentication Framework Integration

The dashboard service should integrate with the existing authentication system:

### Current Auth Setup
- **Framework**: FastAPI with JWT tokens
- **Database**: User sessions and permissions stored in main database
- **Pattern**: Middleware-based authentication

### Required Tables for Dashboard Auth

```sql
-- User sessions (if not already existing)
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    session_token VARCHAR NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dashboard permissions (landscape access control)
CREATE TABLE IF NOT EXISTS dashboard_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    landscape_id UUID REFERENCES digital_landscapes(id),
    permission_level VARCHAR NOT NULL, -- 'read', 'full'
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    granted_by UUID
);
```

### Auth Integration Pattern

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    # Validate JWT token against main database
    # Return user object with landscape permissions
    pass

async def verify_landscape_access(landscape_id: str, user = Depends(get_current_user)):
    # Check user has access to specific landscape
    # Return 403 if unauthorized
    pass
```

---

## Performance Considerations

### 1. Indexing Strategy

```sql
-- Critical indexes for dashboard performance
CREATE INDEX CONCURRENTLY idx_landscape_dsi_current 
ON landscape_dsi_metrics (landscape_id, calculation_date, entity_type, dsi_score DESC);

CREATE INDEX CONCURRENTLY idx_landscape_dsi_entity_lookup
ON landscape_dsi_metrics (entity_type, entity_domain, calculation_date);

CREATE INDEX CONCURRENTLY idx_landscape_dsi_rankings
ON landscape_dsi_metrics (landscape_id, entity_type, rank_in_landscape)
WHERE calculation_date = CURRENT_DATE;
```

### 2. Caching Strategy

**Redis Caching Pattern**:
- Cache landscape overviews for 1 hour
- Cache top companies/pages for 30 minutes  
- Cache company profiles for 24 hours
- Cache keyword metrics for 6 hours

**Cache Keys**:
```
landscape:overview:{landscape_id}:{date}
landscape:top_companies:{landscape_id}:{date}:{limit}
landscape:top_pages:{landscape_id}:{date}:{limit}
company:profile:{domain}
company:landscapes:{domain}:{date}
```

### 3. Data Freshness

- **DSI Calculations**: Updated with each pipeline run (typically daily)
- **Real-time Data**: Use main database for drill-downs
- **Historical Trends**: Query multiple calculation_date values

---

## Dashboard Service Architecture

### Recommended Structure

```
dashboards/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── landscapes.py      # Landscape overview endpoints
│   │   │   ├── companies.py       # Company analysis endpoints
│   │   │   ├── content.py         # Page/content endpoints
│   │   │   ├── keywords.py        # Keyword analysis endpoints
│   │   │   └── competitive.py     # Competitive intelligence
│   │   └── dependencies.py        # Auth dependencies
│   ├── core/
│   │   ├── config.py              # Dashboard service config
│   │   ├── database.py            # Database connection
│   │   ├── cache.py               # Redis caching
│   │   └── auth.py                # Authentication
│   ├── models/
│   │   ├── landscape.py           # Landscape response models
│   │   ├── company.py             # Company response models
│   │   └── dsi.py                 # DSI response models
│   └── services/
│       ├── landscape_service.py   # Business logic
│       ├── company_service.py     # Company analytics
│       └── cache_service.py       # Caching layer
├── docker/
│   └── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

### Environment Configuration

```bash
# Database connection (read-only recommended)
DATABASE_URL=postgresql://readonly_user:password@postgres:5432/cylvy_analyze

# Redis for caching
REDIS_URL=redis://redis:6379

# Authentication
JWT_SECRET_KEY=your_jwt_secret
JWT_ALGORITHM=HS256

# API Configuration  
API_V1_STR=/api/v1
PROJECT_NAME=Digital Landscape Dashboards
VERSION=1.0.0

# Performance
CACHE_TTL_LANDSCAPE_OVERVIEW=3600  # 1 hour
CACHE_TTL_COMPANY_DATA=86400       # 24 hours
CACHE_TTL_DSI_RANKINGS=1800        # 30 minutes
```

---

## Sample API Response Structures

### Landscape Overview Response

```json
{
  "landscape_id": "4e773f12-12b7-4118-b859-faadc0abc60b",
  "name": "Payments",
  "business_unit": "Payments",
  "region": "Global",
  "calculation_date": "2025-09-17",
  "summary": {
    "total_companies": 238,
    "total_pages": 6605,
    "total_keywords": 103,
    "avg_company_dsi": 2.45,
    "top_company_dsi": 15.67,
    "total_landscape_traffic": 2500000
  },
  "top_companies": [
    {
      "rank": 1,
      "company_name": "Finastra",
      "domain": "finastra.com",
      "dsi_score": 15.67,
      "market_position": "leader",
      "keyword_count": 45,
      "estimated_traffic": 125000,
      "industry": "Financial Services"
    }
  ],
  "top_content": [
    {
      "rank": 1,
      "title": "How EU Instant Payments is Reshaping Finance Infrastructure",
      "url": "https://fintechmagazine.com/news/how-eu-instant-payments",
      "domain": "fintechmagazine.com",
      "dsi_score": 1.449,
      "keyword_count": 12,
      "sentiment": "positive"
    }
  ]
}
```

### Company Analysis Response

```json
{
  "company_name": "Finastra",
  "domain": "finastra.com",
  "industry": "Financial Services",
  "employee_count": "10001+",
  "landscape_performance": [
    {
      "landscape_name": "Payments",
      "dsi_score": 15.67,
      "rank": 1,
      "total_competitors": 238,
      "market_position": "leader",
      "keyword_coverage_pct": 43.7,
      "traffic_share_pct": 5.2
    },
    {
      "landscape_name": "Universal Banking",
      "dsi_score": 8.23,
      "rank": 5,
      "total_competitors": 133,
      "market_position": "challenger"
    }
  ],
  "top_content": [
    {
      "title": "Finastra Payment Solutions",
      "url": "https://finastra.com/payments",
      "dsi_score": 2.45,
      "keyword_count": 8,
      "estimated_traffic": 25000
    }
  ],
  "keyword_performance": [
    {
      "keyword": "payment orchestration",
      "dsi_score": 0.8934,
      "rank": 3,
      "search_volume": 12000,
      "competition": "HIGH"
    }
  ]
}
```

---

## Dashboard Development Guidelines

### 1. API Endpoint Patterns

```python
# Landscape endpoints
GET /api/v1/landscapes                    # List all landscapes
GET /api/v1/landscapes/{id}/overview      # Landscape overview
GET /api/v1/landscapes/{id}/companies     # Top companies in landscape
GET /api/v1/landscapes/{id}/content       # Top content in landscape
GET /api/v1/landscapes/{id}/keywords      # Keyword performance

# Company endpoints  
GET /api/v1/companies                     # Search companies
GET /api/v1/companies/{domain}/overview   # Company overview
GET /api/v1/companies/{domain}/landscapes # Company across landscapes
GET /api/v1/companies/{domain}/content    # Company content
GET /api/v1/companies/{domain}/competitors # Competitive analysis

# Competitive intelligence
GET /api/v1/competitive/comparison        # Compare multiple companies
GET /api/v1/competitive/market-leaders    # Market leaders across landscapes
GET /api/v1/competitive/emerging          # Emerging competitors
```

### 2. Real-time Data Integration

**For Live Updates**, query main database tables:
- `serp_results` - Recent SERP position changes
- `scraped_content` - New content discoveries
- `optimized_content_analysis` - Fresh content analysis
- `pipeline_executions` - Pipeline status and updates

### 3. Data Aggregation Patterns

**Time Series Analysis**:
```sql
-- Company DSI trends over time
SELECT 
    calculation_date,
    dsi_score,
    rank_in_landscape,
    estimated_traffic
FROM landscape_dsi_metrics
WHERE entity_domain = 'finastra.com'
AND entity_type = 'company'
AND landscape_id = $1
AND calculation_date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY calculation_date;
```

**Market Share Analysis**:
```sql
-- Market share distribution
SELECT 
    market_position,
    COUNT(*) as company_count,
    AVG(dsi_score) as avg_dsi,
    SUM(estimated_traffic) as total_traffic
FROM landscape_dsi_metrics
WHERE landscape_id = $1
AND entity_type = 'company'
AND calculation_date = CURRENT_DATE
GROUP BY market_position
ORDER BY 
    CASE market_position 
        WHEN 'leader' THEN 1 
        WHEN 'challenger' THEN 2 
        WHEN 'competitor' THEN 3 
        ELSE 4 
    END;
```

---

## Error Handling and Data Quality

### Data Quality Indicators

**DSI Score Ranges by Entity Type**:
- **Companies**: 0.001 to 50.0 (typical range)
- **Pages**: 0.001 to 10.0 (typical range)  
- **Keywords**: 0.001 to 5.0 (typical range)

**Market Position Thresholds**:
- **Leader**: Rank 1-10 OR top 5% of entities
- **Challenger**: Rank 11-50 OR top 20% of entities
- **Competitor**: Rank 51-200 OR top 50% of entities
- **Niche**: Below 50% threshold

### Null Value Handling

**Common Null Fields**:
- `entity_url` - Always null for companies and keywords
- `persona_alignment` - May be null for unanalyzed content
- `estimated_traffic` - May be 0 for low-volume keywords
- `company_industry` - May be "Unknown" for unidentified companies

**Default Values for UI**:
```javascript
const defaults = {
  dsi_score: 0.0,
  market_position: 'niche',
  industry: 'Unknown',
  sentiment: 'neutral',
  competition_level: 'UNKNOWN'
};
```

---

## Security Considerations

### 1. Read-Only Database Access
- Dashboard service should use read-only database user
- No write operations to main database
- Use connection pooling with appropriate limits

### 2. Data Sanitization
- Sanitize all user inputs for SQL injection prevention
- Validate UUID formats before database queries
- Implement rate limiting on API endpoints

### 3. Sensitive Data
- No PII or sensitive business data in DSI tables
- All data is aggregated market intelligence
- Company data limited to public domain information

---

This documentation provides everything needed to develop robust, high-performance customer-facing digital landscape dashboards that leverage the comprehensive DSI snapshot system we've built.
