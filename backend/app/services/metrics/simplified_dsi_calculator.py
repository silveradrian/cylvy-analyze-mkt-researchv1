"""
Simplified DSI Calculator that works with current database schema
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool


class SimplifiedDSICalculator:
    """Simplified DSI Calculator that doesn't require client_id"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        
    async def calculate_dsi_rankings(self, pipeline_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculate DSI rankings for all data or specific pipeline"""
        try:
            # Store pipeline_id for use in queries
            self.current_pipeline_id = pipeline_id
            
            # Calculate organic search DSI
            organic_dsi = await self._calculate_organic_dsi()
            
            # Calculate page-level DSI for all SERP types if pipeline_id provided
            page_dsi = []
            organic_pages = []
            news_pages = []
            video_pages = []
            if pipeline_id:
                organic_pages = await self._calculate_page_dsi(pipeline_id, 'organic')
                news_pages = await self._calculate_page_dsi(pipeline_id, 'news')
                video_pages = await self._calculate_page_dsi(pipeline_id, 'video')
                page_dsi = organic_pages + news_pages + video_pages
            
            # Calculate news DSI
            news_dsi = await self._calculate_news_dsi()
            
            # Calculate YouTube DSI  
            youtube_dsi = await self._calculate_youtube_dsi()
            
            # Store DSI scores in database if pipeline_id provided
            if pipeline_id:
                await self._store_dsi_scores(pipeline_id, organic_dsi, news_dsi, youtube_dsi)
                # Also store page-level data
                if organic_pages:
                    await self._store_page_dsi_scores(pipeline_id, organic_pages, source_type='organic')
                if news_pages:
                    await self._store_page_dsi_scores(pipeline_id, news_pages, source_type='news')
                if video_pages:
                    await self._store_page_dsi_scores(pipeline_id, video_pages, source_type='video')
            
            # Count totals
            companies_ranked = len(set(
                [item['domain'] for item in organic_dsi] +
                [item['domain'] for item in news_dsi] +
                [item['domain'] for item in youtube_dsi]
            ))
            
            pages_ranked = len(page_dsi) if page_dsi else len(organic_dsi)
            
            return {
                'companies_ranked': companies_ranked,
                'pages_ranked': pages_ranked,
                'organic_dsi': organic_dsi,
                'page_dsi': page_dsi,
                'news_dsi': news_dsi,
                'youtube_dsi': youtube_dsi
            }
            
        except Exception as e:
            logger.error(f"DSI calculation failed: {e}")
            raise
    
    async def _calculate_organic_dsi(self) -> List[Dict[str, Any]]:
        """Calculate organic search DSI with proper CTR curves"""
        pipeline_filter = ""
        if hasattr(self, 'current_pipeline_id') and self.current_pipeline_id:
            pipeline_filter = f"AND s.pipeline_execution_id = '{self.current_pipeline_id}'"
        else:
            pipeline_filter = "AND s.search_date >= CURRENT_DATE - INTERVAL '30 days'"
            
        query = f"""
            WITH serp_data AS (
                SELECT 
                    s.domain,
                    s.keyword_id,
                    s.url,
                    s.position,
                    k.keyword,
                    k.avg_monthly_searches,
                    -- Industry-standard CTR curve based on 2024 data
                    CASE 
                        WHEN s.position = 1 THEN 0.2823  -- 28.23%
                        WHEN s.position = 2 THEN 0.1572  -- 15.72%
                        WHEN s.position = 3 THEN 0.1073  -- 10.73%
                        WHEN s.position = 4 THEN 0.0775  -- 7.75%
                        WHEN s.position = 5 THEN 0.0588  -- 5.88%
                        WHEN s.position = 6 THEN 0.0459  -- 4.59%
                        WHEN s.position = 7 THEN 0.0369  -- 3.69%
                        WHEN s.position = 8 THEN 0.0302  -- 3.02%
                        WHEN s.position = 9 THEN 0.0252  -- 2.52%
                        WHEN s.position = 10 THEN 0.0214 -- 2.14%
                        WHEN s.position <= 20 THEN 0.0150 -- 1.5% for positions 11-20
                        WHEN s.position <= 30 THEN 0.0080 -- 0.8% for positions 21-30
                        ELSE 0.0050 -- 0.5% for positions 31+
                    END as estimated_ctr,
                    -- ESTIMATED TRAFFIC = Search Volume × CTR
                    COALESCE(k.avg_monthly_searches, 1000) * CASE 
                        WHEN s.position = 1 THEN 0.2823
                        WHEN s.position = 2 THEN 0.1572
                        WHEN s.position = 3 THEN 0.1073
                        WHEN s.position = 4 THEN 0.0775
                        WHEN s.position = 5 THEN 0.0588
                        WHEN s.position = 6 THEN 0.0459
                        WHEN s.position = 7 THEN 0.0369
                        WHEN s.position = 8 THEN 0.0302
                        WHEN s.position = 9 THEN 0.0252
                        WHEN s.position = 10 THEN 0.0214
                        WHEN s.position <= 20 THEN 0.0150
                        WHEN s.position <= 30 THEN 0.0080
                        ELSE 0.0050
                    END as estimated_traffic
                FROM serp_results s
                JOIN keywords k ON s.keyword_id = k.id
                WHERE s.serp_type = 'organic'
                    {pipeline_filter}
            ),
            company_metrics AS (
                SELECT 
                    -- Use domain_company_mapping if available; otherwise fall back to profiles or cleaned domain
                    COALESCE(
                        dcm.display_name,
                        MIN(cp.company_name),
                        INITCAP(REPLACE(SPLIT_PART(regexp_replace(MIN(s.domain), '^www\\.', ''), '.', 1), '-', ' '))
                    ) as company_name,
                    COALESCE(dcm.original_domain, MIN(cp.domain), MIN(s.domain)) as primary_domain,
                    dcm.enrichment_source,
                    dcm.company_id,
                    -- SERP Performance Metrics
                    COUNT(DISTINCT s.keyword_id) as keyword_count,
                    COUNT(DISTINCT s.url) as page_count,
                    COUNT(DISTINCT s.domain) as domain_count,
                    AVG(s.position) as avg_position,
                    MIN(s.position) as best_position,
                    COUNT(CASE WHEN s.position <= 3 THEN 1 END) as top_3_count,
                    COUNT(CASE WHEN s.position <= 10 THEN 1 END) as top_10_count,
                    -- CORRECTED: Use estimated traffic (Search Volume × CTR)
                    SUM(s.estimated_traffic) as total_estimated_traffic,
                    -- ENHANCED: Aggregate page-level analysis data
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_content_analysis oca
                         JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
                         JOIN scraped_content sc ON oca.url = sc.url
                         WHERE sc.domain = COALESCE(dcm.original_domain, MIN(s.domain))
                         AND oda.dimension_type = 'persona'
                        ), 5.0  -- Default persona score (1-10 scale)
                    ) as persona_score,
                    -- Strategic Imperatives aggregate scores
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_content_analysis oca
                         JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
                         JOIN scraped_content sc ON oca.url = sc.url
                         WHERE sc.domain = COALESCE(dcm.original_domain, MIN(s.domain))
                         AND oda.dimension_type = 'strategic_imperative'
                        ), 5.0
                    ) as strategic_imperative_score,
                    -- JTBD aggregate scores
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_content_analysis oca
                         JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
                         JOIN scraped_content sc ON oca.url = sc.url
                         WHERE sc.domain = COALESCE(dcm.original_domain, MIN(s.domain))
                         AND oda.dimension_type = 'jtbd_phase'
                        ), 5.0
                    ) as jtbd_score,
                    -- Sentiment analysis aggregates
                    COUNT(CASE WHEN oca.overall_sentiment = 'positive' THEN 1 END) as positive_content_count,
                    COUNT(CASE WHEN oca.overall_sentiment = 'neutral' THEN 1 END) as neutral_content_count,
                    COUNT(CASE WHEN oca.overall_sentiment = 'negative' THEN 1 END) as negative_content_count,
                    -- Mention analysis aggregates
                    COALESCE(
                        (SELECT COUNT(*)
                         FROM optimized_content_analysis oca
                         JOIN scraped_content sc ON oca.url = sc.url
                         WHERE sc.domain = COALESCE(dcm.original_domain, MIN(s.domain))
                         AND oca.mentions IS NOT NULL 
                         AND jsonb_array_length(oca.mentions) > 0
                        ), 0
                    ) as pages_with_mentions,
                    -- Company enrichment details
                    cp.industry,
                    cp.employee_count,
                    cp.description as company_description,
                    cp.source_type as company_source_type,
                    dcm.confidence_score as enrichment_confidence
                FROM serp_data s
                LEFT JOIN domain_company_mapping dcm ON s.domain = dcm.original_domain
                LEFT JOIN company_profiles cp ON (cp.id = dcm.company_id OR cp.domain = s.domain)
                LEFT JOIN optimized_content_analysis oca ON oca.url = s.url AND oca.project_id IS NULL
                GROUP BY 
                    dcm.company_id,
                    dcm.display_name,
                    dcm.original_domain,
                    dcm.enrichment_source,
                    cp.industry,
                    cp.employee_count,
                    cp.description,
                    cp.source_type,
                    dcm.confidence_score
            ),
            market_totals AS (
                SELECT 
                    COUNT(DISTINCT s.keyword_id) as total_keywords,
                    COUNT(DISTINCT s.domain) as total_domains,
                    SUM(s.estimated_traffic) as total_market_traffic
                FROM serp_data s
            )
            SELECT 
                cm.company_name,
                cm.primary_domain as domain,
                cm.company_id,
                -- SERP Performance Metrics
                cm.keyword_count,
                cm.page_count,
                cm.domain_count,
                cm.avg_position,
                cm.best_position,
                cm.top_3_count,
                cm.top_10_count,
                cm.total_estimated_traffic,
                cm.enrichment_source,
                -- Company Details
                cm.industry,
                cm.employee_count,
                '' as company_description,  -- Description not available in this CTE
                cm.company_source_type,
                cm.enrichment_confidence,
                -- ENHANCED: Aggregate Page-Level Analysis Data
                ROUND(cm.persona_score::numeric, 2) as avg_persona_score,
                ROUND(cm.strategic_imperative_score::numeric, 2) as avg_strategic_imperative_score,
                ROUND(cm.jtbd_score::numeric, 2) as avg_jtbd_score,
                cm.positive_content_count,
                cm.neutral_content_count,
                cm.negative_content_count,
                cm.pages_with_mentions,
                -- Calculated sentiment distribution
                ROUND(
                    (cm.positive_content_count::float / NULLIF(cm.page_count, 0) * 100)::numeric, 1
                ) as positive_sentiment_pct,
                ROUND(
                    (cm.neutral_content_count::float / NULLIF(cm.page_count, 0) * 100)::numeric, 1
                ) as neutral_sentiment_pct,
                ROUND(
                    (cm.negative_content_count::float / NULLIF(cm.page_count, 0) * 100)::numeric, 1
                ) as negative_sentiment_pct,
                -- CORRECTED DSI COMPONENTS per user specification
                ROUND(
                    (cm.keyword_count::float / mt.total_keywords * 100)::numeric, 
                    2
                ) as keyword_coverage_pct,
                ROUND(
                    (cm.total_estimated_traffic / NULLIF(mt.total_market_traffic, 0) * 100)::numeric,
                    2
                ) as traffic_share_pct,
                ROUND(cm.persona_score::numeric, 2) as persona_relevance,
                -- ORGANIC DSI FORMULA: Keyword Coverage × Share of Traffic × Personal Relevance (full formula)
                ROUND(
                    (
                        (cm.keyword_count::float / mt.total_keywords * 100) *
                        (cm.total_estimated_traffic / NULLIF(mt.total_market_traffic, 0) * 100) *
                        (cm.persona_score / 10.0)  -- Normalize 1-10 scale to 0-1
                    )::numeric,
                    2
                ) as dsi_score
            FROM company_metrics cm
            CROSS JOIN market_totals mt
            WHERE cm.keyword_count >= 1  -- Include any company with at least 1 keyword
            ORDER BY dsi_score DESC, cm.keyword_count DESC
        """
        
        results = await self.db.fetch(query)
        return [dict(row) for row in results]
    
    async def _calculate_page_dsi(self, pipeline_id: str, serp_type: str) -> List[Dict[str, Any]]:
        """Calculate page-level DSI per SERP type.
        - organic/news: traffic_share × persona (already aligned with company formula)
        - video: Number of SERPs × views × engagement_rate (normalized to 0–100)
        """
        if serp_type == 'video':
            query = """
            WITH video_data AS (
                SELECT 
                    sr.url,
                    COALESCE(sr.title, vs.video_title) as title,
                    sr.domain,
                    sr.keyword_id,
                    sr.position,
                    COALESCE(vs.view_count, 0) as view_count,
                    COALESCE(vs.engagement_rate, 0.01) as engagement_rate
                FROM serp_results sr
                INNER JOIN video_snapshots vs ON vs.video_url = sr.url
                WHERE sr.serp_type = 'video'
                  AND sr.pipeline_execution_id = $1
            ), page_metrics AS (
                SELECT 
                    url,
                    MAX(title) as title,
                    MAX(domain) as domain,
                    COUNT(DISTINCT keyword_id) as keyword_count,
                    AVG(position) as avg_position,
                    MIN(position) as best_position,
                    COUNT(CASE WHEN position = 1 THEN 1 END) as position_1_count,
                    COUNT(CASE WHEN position <= 3 THEN 1 END) as top_3_count,
                    COUNT(CASE WHEN position <= 10 THEN 1 END) as top_10_count,
                    -- For uniformity with organic/news, keep a traffic-like metric
                    SUM(view_count) as total_estimated_traffic,
                    SUM(1) as serp_appearances,
                    MAX(view_count) as max_views,
                    MAX(engagement_rate) as engagement_rate
                FROM video_data
                GROUP BY url
            ), scored AS (
                SELECT 
                    pm.*, 
                    (pm.serp_appearances::double precision * pm.max_views::double precision * pm.engagement_rate::double precision) as dsi_raw,
                    MAX(pm.serp_appearances::double precision * pm.max_views::double precision * pm.engagement_rate::double precision) OVER () as dsi_raw_max
                FROM page_metrics pm
            )
            SELECT 
                url,
                title,
                domain,
                keyword_count,
                avg_position,
                best_position,
                position_1_count,
                top_3_count,
                top_10_count,
                total_estimated_traffic,
                ARRAY[]::text[] as top_keywords,
                '' as overall_insights,
                'neutral' as overall_sentiment,
                '' as key_topics_str,
                5.0 as persona_score,
                5.0 as strategic_imperative_score,
                5.0 as jtbd_score,
                0 as mention_count,
                0 as brand_mention_count,
                0 as competitor_mention_count,
                -- computed ranking index normalized to 0-100
                ROUND((CASE WHEN dsi_raw_max > 0 THEN (dsi_raw / dsi_raw_max) * 100.0 ELSE 0 END)::numeric, 6) as dsi_score
            FROM scored
            ORDER BY dsi_score DESC, keyword_count DESC
            """
            results = await self.db.fetch(query, pipeline_id)
            return [dict(row) for row in results]

        query = """
            WITH page_serp_data AS (
                SELECT 
                    sr.url,
                    sr.title,
                    sr.domain,
                    sr.keyword_id,
                    sr.position,
                    k.keyword as keyword_text,
                    k.avg_monthly_searches,
                    -- Industry-standard CTR curve for traffic estimation
                    COALESCE(k.avg_monthly_searches, 1000) * CASE 
                        WHEN sr.position = 1 THEN 0.2823
                        WHEN sr.position = 2 THEN 0.1572
                        WHEN sr.position = 3 THEN 0.1073
                        WHEN sr.position = 4 THEN 0.0775
                        WHEN sr.position = 5 THEN 0.0588
                        WHEN sr.position = 6 THEN 0.0459
                        WHEN sr.position = 7 THEN 0.0369
                        WHEN sr.position = 8 THEN 0.0302
                        WHEN sr.position = 9 THEN 0.0252
                        WHEN sr.position = 10 THEN 0.0214
                        WHEN sr.position <= 20 THEN 0.0150
                        ELSE 0.0050
                    END as estimated_traffic
                FROM serp_results sr
                LEFT JOIN keywords k ON k.id = sr.keyword_id
                WHERE sr.serp_type = $2
                    AND sr.pipeline_execution_id = $1
            ),
            page_metrics AS (
                SELECT 
                    url,
                    MAX(title) as title,
                    MAX(domain) as domain,
                    COUNT(DISTINCT keyword_id) as keyword_count,
                    AVG(position) as avg_position,
                    MIN(position) as best_position,
                    -- Traffic estimation (same as company-level)
                    SUM(estimated_traffic) as total_estimated_traffic,
                    -- Position distribution
                    COUNT(CASE WHEN position = 1 THEN 1 END) as position_1_count,
                    COUNT(CASE WHEN position <= 3 THEN 1 END) as top_3_count,
                    COUNT(CASE WHEN position <= 10 THEN 1 END) as top_10_count,
                    -- Keyword list for metadata
                    ARRAY_AGG(keyword_text ORDER BY position) as ranking_keywords
                FROM page_serp_data
                GROUP BY url
            ),
            content_analysis AS (
                -- Get comprehensive analysis results for each page
                SELECT 
                    oca.url,
                    oca.overall_insights,
                    oca.overall_sentiment,
                    oca.key_topics,
                    oca.mentions,
                    -- Dimension scores aggregated by type
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_dimension_analysis oda 
                         WHERE oda.analysis_id = oca.id 
                         AND oda.dimension_type = 'persona'
                        ), 5.0  -- Default persona score (1-10 scale)
                    ) as persona_score,
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_dimension_analysis oda 
                         WHERE oda.analysis_id = oca.id 
                         AND oda.dimension_type = 'strategic_imperative'
                        ), 5.0
                    ) as strategic_imperative_score,
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_dimension_analysis oda 
                         WHERE oda.analysis_id = oca.id 
                         AND oda.dimension_type = 'jtbd_phase'
                        ), 5.0
                    ) as jtbd_score,
                    -- Mention analysis details
                    CASE 
                        WHEN oca.mentions IS NOT NULL AND jsonb_array_length(oca.mentions) > 0
                        THEN jsonb_array_length(oca.mentions)
                        ELSE 0
                    END as mention_count,
                    -- Brand mentions specifically
                    COALESCE(
                        (SELECT COUNT(*)
                         FROM jsonb_array_elements(oca.mentions) as mention
                         WHERE mention->>'type' = 'brand'
                        ), 0
                    ) as brand_mention_count,
                    -- Competitor mentions specifically
                    COALESCE(
                        (SELECT COUNT(*)
                         FROM jsonb_array_elements(oca.mentions) as mention
                         WHERE mention->>'type' = 'competitor'
                        ), 0
                    ) as competitor_mention_count,
                    -- Key topics as string
                    CASE 
                        WHEN oca.key_topics IS NOT NULL AND jsonb_typeof(oca.key_topics) = 'array'
                        THEN array_to_string(ARRAY(SELECT jsonb_array_elements_text(oca.key_topics)), ', ')
                        ELSE ''
                    END as key_topics_str
                FROM optimized_content_analysis oca
                WHERE oca.project_id IS NULL  -- Pipeline analyses
            ),
            market_totals AS (
                -- Market totals for percentage calculations
                SELECT 
                    COUNT(DISTINCT keyword_id) as total_keywords,
                    SUM(estimated_traffic) as total_market_traffic
                FROM page_serp_data
            )
            SELECT 
                pm.url,
                pm.title,
                pm.domain,
                -- SERP Performance Metrics
                pm.keyword_count,
                pm.avg_position,
                pm.best_position,
                pm.position_1_count,
                pm.top_3_count,
                pm.top_10_count,
                pm.total_estimated_traffic,
                pm.ranking_keywords[1:5] as top_keywords,
                -- COMPREHENSIVE Analysis Results
                ca.overall_insights,
                ca.overall_sentiment,
                ca.key_topics_str,
                -- Dimension Scores
                ROUND(ca.persona_score::numeric, 2) as persona_score,
                ROUND(ca.strategic_imperative_score::numeric, 2) as strategic_imperative_score,
                ROUND(ca.jtbd_score::numeric, 2) as jtbd_score,
                -- Mention Analysis Results
                ca.mention_count,
                ca.brand_mention_count,
                ca.competitor_mention_count,
                ca.mentions,
                -- CONSISTENT DSI COMPONENTS (ratios and percents)
                ROUND(
                    (pm.keyword_count::float / mt.total_keywords * 100)::numeric, 
                    2
                ) as keyword_coverage_pct,
                ROUND(
                    (pm.total_estimated_traffic / NULLIF(mt.total_market_traffic, 0) * 100)::numeric,
                    4
                ) as traffic_share_pct,
                ROUND(ca.persona_score::numeric, 2) as persona_relevance,
                -- PAGE DSI: traffic_share_pct × persona_ratio (0–100 scale)
                ROUND(
                    (
                        (pm.total_estimated_traffic / NULLIF(mt.total_market_traffic, 0) * 100.0) *
                        (ca.persona_score / 10.0)
                    )::numeric,
                    6
                ) as dsi_score
            FROM page_metrics pm
            LEFT JOIN content_analysis ca ON ca.url = pm.url
            CROSS JOIN market_totals mt
            WHERE pm.keyword_count > 0
            ORDER BY dsi_score DESC, pm.keyword_count DESC
        """
        
        results = await self.db.fetch(query, pipeline_id, serp_type)
        return [dict(row) for row in results]
    
    async def _calculate_news_dsi(self) -> List[Dict[str, Any]]:
        """Calculate news DSI using SERP appearances × keyword coverage × persona alignment"""
        pipeline_filter = ""
        if hasattr(self, 'current_pipeline_id') and self.current_pipeline_id:
            pipeline_filter = f"AND s.pipeline_execution_id = '{self.current_pipeline_id}'"
        else:
            pipeline_filter = "AND s.search_date >= CURRENT_DATE - INTERVAL '30 days'"
            
        query = f"""
            WITH publisher_metrics AS (
                SELECT 
                    -- Company identification (mapping → profile → cleaned domain)
                    COALESCE(
                        dcm.display_name,
                        cp.company_name,
                        INITCAP(REPLACE(SPLIT_PART(regexp_replace(s.domain, '^www\.', ''), '.', 1), '-', ' '))
                    ) as company_name,
                    MIN(COALESCE(dcm.original_domain, cp.domain, regexp_replace(s.domain, '^www\.', ''))) as primary_domain,
                    COUNT(DISTINCT s.domain) as domain_count,
                    COUNT(DISTINCT s.keyword_id) as keyword_count,
                    COUNT(DISTINCT s.url) as article_count,
                    COUNT(*) as total_serp_appearances,  -- SERP appearances count
                    AVG(s.position) as avg_position,
                    -- Persona alignment from content analysis
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_content_analysis oca
                         JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
                         JOIN scraped_content sc ON oca.url = sc.url
                         WHERE sc.domain = COALESCE(MIN(dcm.original_domain), regexp_replace(MIN(s.domain), '^www\.', ''))
                         AND oda.dimension_type = 'persona'
                        ), 5.0  -- Default persona alignment (1-10 scale)
                    ) as persona_alignment
                FROM serp_results s
                LEFT JOIN company_profiles cp ON s.domain = cp.domain
                LEFT JOIN domain_company_mapping dcm ON s.domain = dcm.original_domain
                WHERE s.serp_type = 'news'
                    AND s.position <= 100  -- Top 100 to broaden inclusion
                    {pipeline_filter}
                GROUP BY COALESCE(
                    dcm.display_name,
                    cp.company_name,
                    INITCAP(REPLACE(SPLIT_PART(regexp_replace(s.domain, '^www\.', ''), '.', 1), '-', ' '))
                )
            ),
            market_totals AS (
                SELECT 
                    -- Total distinct keywords present in NEWS results for the same time/pipeline window
                    (SELECT COUNT(DISTINCT s.keyword_id)
                     FROM serp_results s
                     WHERE s.serp_type = 'news'
                     {pipeline_filter}
                    ) as total_keywords,
                    -- Total SERP appearances across all publishers (from aggregated metrics)
                    (SELECT SUM(total_serp_appearances) FROM publisher_metrics) as total_appearances
            )
            SELECT 
                company_name,
                primary_domain as domain,
                domain_count,
                keyword_count,
                article_count,
                total_serp_appearances,
                avg_position,
                ROUND(persona_alignment::numeric, 2) as persona_alignment,
                -- Keyword coverage percentage
                ROUND(
                    (keyword_count::float / NULLIF(mt.total_keywords, 0) * 100)::numeric,
                    2
                ) as keyword_coverage_pct,
                -- NEWS DSI FORMULA: SERP Appearances × Keyword Coverage × Persona Alignment  
                ROUND(
                    (
                        (total_serp_appearances::float / NULLIF(mt.total_appearances, 0)) * 100 *  -- SERP appearance share %
                        (keyword_count::float / mt.total_keywords * 100) *                         -- Keyword coverage %
                        (persona_alignment / 10.0)                                                -- Persona alignment (0-1 scale)
                    )::numeric,
                    2
                ) as news_dsi_score
            FROM publisher_metrics pm
            CROSS JOIN market_totals mt
            WHERE keyword_count >= 1  -- Include any company with at least 1 keyword
            ORDER BY news_dsi_score DESC NULLS LAST
            
        """
        
        results = await self.db.fetch(query)
        return [dict(row) for row in results]
    
    async def _calculate_youtube_dsi(self) -> List[Dict[str, Any]]:
        """Calculate YouTube DSI - aggregated by company"""
        pipeline_id = getattr(self, 'current_pipeline_id', None)
        if not pipeline_id:
            return []
            
        query = """
            WITH video_company_mapping AS (
                -- Map videos to company domains via channel enrichment
                SELECT 
                    sr.url,
                    sr.keyword_id,
                    sr.position,
                    sr.pipeline_execution_id,
                    vs.channel_id,
                    vs.view_count,
                    -- Resolve company domain: prioritize enriched data, fallback to inferred
                    COALESCE(
                        ycc.company_domain,
                        cp.domain,
                        -- Fallback: extract from channel title if it looks like a domain
                        CASE 
                            WHEN vs.channel_title ~ '^[a-zA-Z0-9-]+\.(com|net|org|io|co)$' 
                            THEN LOWER(vs.channel_title)
                            ELSE NULL
                        END
                    ) as company_domain,
                    -- Resolve company name: prioritize profile data, then enriched, then infer
                    COALESCE(
                        cp.company_name,
                        ycc.company_name,
                        -- Fallback: clean channel title or infer from domain
                        CASE
                            WHEN ycc.company_domain IS NOT NULL THEN
                                INITCAP(REPLACE(SPLIT_PART(ycc.company_domain, '.', 1), '-', ' '))
                            WHEN vs.channel_title IS NOT NULL THEN
                                vs.channel_title
                            ELSE
                                'Unknown'
                        END
                    ) as company_name
                FROM serp_results sr
                INNER JOIN video_snapshots vs ON vs.video_url = sr.url
                LEFT JOIN youtube_channel_companies ycc ON ycc.channel_id = vs.channel_id
                LEFT JOIN company_domains cd ON cd.domain = ycc.company_domain
                LEFT JOIN company_profiles cp ON cp.id = cd.company_id
                WHERE sr.serp_type = 'video'
                    AND sr.pipeline_execution_id = $1
            ),
            company_metrics AS (
                SELECT 
                    company_name,
                    MIN(company_domain) as primary_domain,
                    COUNT(DISTINCT company_domain) as domain_count,
                    COUNT(DISTINCT keyword_id) as keyword_count,
                    COUNT(DISTINCT url) as video_count,
                    COUNT(*) as total_serp_appearances,  -- SERP appearances count
                    AVG(position) as avg_position,
                    SUM(COALESCE(view_count, 0)) as total_views,
                    -- Persona alignment from content analysis
                    COALESCE(
                        (SELECT AVG(CAST(oda.score AS FLOAT))
                         FROM optimized_content_analysis oca
                         JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
                         WHERE oca.url = ANY(array_agg(DISTINCT vcm.url))
                         AND oda.dimension_type = 'persona'
                        ), 5.0  -- Default persona alignment (1-10 scale)
                    ) as persona_alignment
                FROM video_company_mapping vcm
                WHERE company_domain IS NOT NULL AND company_name IS NOT NULL
                GROUP BY company_name
            ),
            market_totals AS (
                SELECT 
                    -- Total distinct keywords present in VIDEO results for this pipeline
                    (SELECT COUNT(DISTINCT sr.keyword_id)
                     FROM serp_results sr
                     WHERE sr.serp_type = 'video'
                       AND sr.pipeline_execution_id = $1
                    ) as total_keywords,
                    -- Total SERP appearances across all companies (from aggregated metrics)
                    (SELECT SUM(total_serp_appearances) FROM company_metrics) as total_appearances
            )
            SELECT 
                primary_domain as domain,
                company_name,
                domain_count,
                keyword_count,
                video_count,
                total_serp_appearances,
                avg_position,
                total_views,
                ROUND(persona_alignment::numeric, 2) as persona_alignment,
                -- Keyword coverage percentage
                ROUND(
                    (keyword_count::float / NULLIF(mt.total_keywords, 0) * 100)::numeric,
                    2
                ) as keyword_coverage_pct,
                -- VIDEO DSI FORMULA: SERP Appearances × Keyword Coverage × Persona Alignment
                ROUND(
                    (
                        (total_serp_appearances::float / NULLIF(mt.total_appearances, 0)) * 100 *  -- SERP appearance share %
                        (keyword_count::float / mt.total_keywords * 100) *                         -- Keyword coverage %
                        (persona_alignment / 10.0)                                                -- Persona alignment (0-1 scale)
                    )::numeric,
                    2
                ) as video_dsi_score
            FROM company_metrics cm
            CROSS JOIN market_totals mt
            WHERE keyword_count >= 1  -- Include any company with at least 1 keyword
            ORDER BY video_dsi_score DESC NULLS LAST
            
        """
        
        results = await self.db.fetch(query, pipeline_id)
        return [dict(row) for row in results]
    
    async def calculate(self, request: Any) -> Any:
        """Compatibility method for DSICalculationRequest"""
        # Just call the simplified calculation
        result = await self.calculate_dsi_rankings()
        
        # Wrap in expected format
        from app.models.dsi import DSICalculationResult, CompanyDSIMetrics
        
        # Convert organic DSI to CompanyDSIMetrics
        organic_metrics = []
        for item in result.get('organic_dsi', []):
            organic_metrics.append(CompanyDSIMetrics(
                domain=item['domain'],
                company_name=item['domain'],  # Use domain as company name
                company_id='',
                total_keywords=item['keyword_count'],
                total_pages=item['page_count'],
                avg_position=item['avg_position'],
                top_3_count=item['top_3_count'],
                top_10_count=item['top_10_count'],
                dsi_score=item['visibility_score'],
                market_share=item['keyword_coverage'],
                page_metrics=[]
            ))
        
        return DSICalculationResult(
            calculation_id=request.calculation_id,
            client_id=request.client_id,
            period_start=request.period_start,
            period_end=request.period_end,
            organic_dsi=organic_metrics,
            news_dsi=[],
            youtube_dsi=[],
            total_dsi_score=len(organic_metrics),
            market_totals=None,
            insights=[]
        )
    
    async def _store_dsi_scores(self, pipeline_id: str, organic_dsi: List[Dict], news_dsi: List[Dict], youtube_dsi: List[Dict]):
        """Store DSI scores in the database"""
        async with self.db.acquire() as conn:
            # Clear existing scores for this pipeline
            await conn.execute("DELETE FROM dsi_scores WHERE pipeline_execution_id = $1", pipeline_id)
            
            # Store organic DSI scores with comprehensive company and analysis data
            for item in organic_dsi:
                # Normalize DSI score (percentage → 0..1)
                raw_dsi = float(item.get('dsi_score') or 0)
                dsi_score = max(0.0, min(1.0, raw_dsi / 100.0))
                keyword_coverage = float(item.get('keyword_coverage_pct') or 0) / 100
                traffic_share = float(item.get('traffic_share_pct') or 0) / 100
                persona_relevance = float(item.get('persona_relevance') or 5.0) / 10
                
                serp_visibility = max(0.0, min(1.0, 1.0 - (float(item.get('avg_position') or 20) / 20)))
                await conn.execute("""
                    INSERT INTO dsi_scores (
                        pipeline_execution_id, company_domain,
                        dsi_score, keyword_overlap_score, content_relevance_score,
                        market_presence_score, traffic_share_score, serp_visibility_score,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (pipeline_execution_id, company_domain)
                    DO UPDATE SET
                        dsi_score = GREATEST(dsi_scores.dsi_score, EXCLUDED.dsi_score),
                        keyword_overlap_score = GREATEST(dsi_scores.keyword_overlap_score, EXCLUDED.keyword_overlap_score),
                        content_relevance_score = GREATEST(dsi_scores.content_relevance_score, EXCLUDED.content_relevance_score),
                        market_presence_score = GREATEST(dsi_scores.market_presence_score, EXCLUDED.market_presence_score),
                        traffic_share_score = GREATEST(dsi_scores.traffic_share_score, EXCLUDED.traffic_share_score),
                        serp_visibility_score = GREATEST(dsi_scores.serp_visibility_score, EXCLUDED.serp_visibility_score),
                        metadata = dsi_scores.metadata || EXCLUDED.metadata,
                        updated_at = NOW()
                """, pipeline_id, item['domain'], 
                    dsi_score,  # Your DSI formula result (0-1)
                    keyword_coverage,  # Keyword coverage (0-1)
                    persona_relevance,  # Content relevance from persona analysis
                    min(1.0, float(item.get('top_10_count') or 0) / max(float(item.get('keyword_count') or 1), 1)),  # Market presence (0-1)
                    traffic_share,  # Traffic share (0-1)
                    serp_visibility,  # SERP visibility (0-1)
                    json.dumps({
                        'source': 'organic',
                        'company_name': item.get('company_name', ''),
                        'company_id': str(item.get('company_id', '')),
                        # SERP Performance
                        'avg_position': float(item.get('avg_position') or 0),
                        'best_position': int(item.get('best_position') or 20),
                        'keyword_count': int(item.get('keyword_count') or 0),
                        'page_count': int(item.get('page_count') or 0),
                        'domain_count': int(item.get('domain_count') or 1),
                        'top_3_count': int(item.get('top_3_count') or 0),
                        'top_10_count': int(item.get('top_10_count') or 0),
                        'total_estimated_traffic': int(item.get('total_estimated_traffic') or 0),
                        # Company Details
                        'industry': item.get('industry', ''),
                        'employee_count': item.get('employee_count', ''),
                        'company_description': item.get('company_description', '') or '',
                        'company_source_type': item.get('company_source_type', ''),
                        'enrichment_confidence': float(item.get('enrichment_confidence') or 0),
                        # Aggregate Page Analysis Data
                        'avg_persona_score': float(item.get('avg_persona_score') or 5.0),
                        'avg_strategic_imperative_score': float(item.get('avg_strategic_imperative_score') or 5.0),
                        'avg_jtbd_score': float(item.get('avg_jtbd_score') or 5.0),
                        'positive_content_count': int(item.get('positive_content_count') or 0),
                        'neutral_content_count': int(item.get('neutral_content_count') or 0),
                        'negative_content_count': int(item.get('negative_content_count') or 0),
                        'pages_with_mentions': int(item.get('pages_with_mentions') or 0),
                        'positive_sentiment_pct': float(item.get('positive_sentiment_pct') or 0),
                        'neutral_sentiment_pct': float(item.get('neutral_sentiment_pct') or 0),
                        'negative_sentiment_pct': float(item.get('negative_sentiment_pct') or 0),
                        # DSI Components
                        'keyword_coverage_pct': float(item.get('keyword_coverage_pct') or 0),
                        'traffic_share_pct': float(item.get('traffic_share_pct') or 0)
                    }))
            
            # Store news DSI scores with SERP appearances × keyword coverage × persona alignment formula
            for item in news_dsi:
                # Normalize DSI score (percentage → 0..1)
                raw_news = float(item.get('news_dsi_score') or 0)
                news_dsi_score = max(0.0, min(1.0, raw_news / 100.0))
                # Use normalized keyword coverage from SQL (percentage)
                keyword_coverage = float(item.get('keyword_coverage_pct') or 0)
                serp_appearances = float(item.get('total_serp_appearances') or 0)
                persona_alignment = float(item.get('persona_alignment') or 5.0) / 10
                
                serp_visibility = max(0.0, min(1.0, 1.0 - (float(item.get('avg_position') or 20) / 20)))
                await conn.execute("""
                    INSERT INTO dsi_scores (
                        pipeline_execution_id, company_domain,
                        dsi_score, keyword_overlap_score, content_relevance_score,
                        market_presence_score, traffic_share_score, serp_visibility_score,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (pipeline_execution_id, company_domain)
                    DO UPDATE SET
                        dsi_score = GREATEST(dsi_scores.dsi_score, EXCLUDED.dsi_score),
                        keyword_overlap_score = GREATEST(dsi_scores.keyword_overlap_score, EXCLUDED.keyword_overlap_score),
                        content_relevance_score = GREATEST(dsi_scores.content_relevance_score, EXCLUDED.content_relevance_score),
                        market_presence_score = GREATEST(dsi_scores.market_presence_score, EXCLUDED.market_presence_score),
                        traffic_share_score = GREATEST(dsi_scores.traffic_share_score, EXCLUDED.traffic_share_score),
                        serp_visibility_score = GREATEST(dsi_scores.serp_visibility_score, EXCLUDED.serp_visibility_score),
                        metadata = dsi_scores.metadata || EXCLUDED.metadata,
                        updated_at = NOW()
                """, pipeline_id, item['domain'],
                    news_dsi_score,  # News DSI (0-1)
                    keyword_coverage / 100,  # Keyword coverage (0-1)
                    persona_alignment,  # Persona alignment (0-1)
                    min(1.0, serp_appearances / 100),  # Market presence (0-1)
                    0.0,  # No traffic share for news (not applicable)
                    serp_visibility,  # SERP visibility (0-1)
                    json.dumps({
                        'source': 'news',
                        'formula': 'SERP Appearances × Keyword Coverage × Persona Alignment',
                        'avg_position': float(item.get('avg_position') or 0),
                        'article_count': int(item.get('article_count') or 0),
                        'total_serp_appearances': int(item.get('total_serp_appearances') or 0),
                        'keyword_count': int(item.get('keyword_count') or 0),
                        'persona_alignment': float(item.get('persona_alignment') or 5.0)
                    }))
            
            # Store YouTube DSI scores with SERP appearances × keyword coverage × persona alignment formula
            for item in youtube_dsi:
                # Normalize DSI score (percentage → 0..1)
                raw_video = float(item.get('video_dsi_score') or 0)
                video_dsi_score = max(0.0, min(1.0, raw_video / 100.0))
                # Use normalized keyword coverage from SQL (percentage)
                keyword_coverage = float(item.get('keyword_coverage_pct') or 0)
                serp_appearances = float(item.get('total_serp_appearances') or 0)
                persona_alignment = float(item.get('persona_alignment') or 5.0) / 10
                
                serp_visibility = max(0.0, min(1.0, 1.0 - (float(item.get('avg_position') or 20) / 20)))
                await conn.execute("""
                    INSERT INTO dsi_scores (
                        pipeline_execution_id, company_domain,
                        dsi_score, keyword_overlap_score, content_relevance_score,
                        market_presence_score, traffic_share_score, serp_visibility_score,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (pipeline_execution_id, company_domain)
                    DO UPDATE SET
                        dsi_score = GREATEST(dsi_scores.dsi_score, EXCLUDED.dsi_score),
                        keyword_overlap_score = GREATEST(dsi_scores.keyword_overlap_score, EXCLUDED.keyword_overlap_score),
                        content_relevance_score = GREATEST(dsi_scores.content_relevance_score, EXCLUDED.content_relevance_score),
                        market_presence_score = GREATEST(dsi_scores.market_presence_score, EXCLUDED.market_presence_score),
                        traffic_share_score = GREATEST(dsi_scores.traffic_share_score, EXCLUDED.traffic_share_score),
                        serp_visibility_score = GREATEST(dsi_scores.serp_visibility_score, EXCLUDED.serp_visibility_score),
                        metadata = dsi_scores.metadata || EXCLUDED.metadata,
                        updated_at = NOW()
                """, pipeline_id, item['domain'],
                    video_dsi_score,  # Video DSI (0-1)
                    keyword_coverage / 100,  # Keyword coverage (0-1)
                    persona_alignment,  # Persona alignment (0-1)
                    min(1.0, serp_appearances / 50),  # Market presence (0-1)
                    0.0,  # No traffic share for video (not applicable)
                    serp_visibility,  # SERP visibility (0-1)
                    json.dumps({
                        'source': 'video',
                        'formula': 'SERP Appearances × Keyword Coverage × Persona Alignment',
                        'avg_position': float(item.get('avg_position') or 0),
                        'video_count': int(item.get('video_count') or 0),
                        'total_views': int(item.get('total_views') or 0),
                        'total_serp_appearances': int(item.get('total_serp_appearances') or 0),
                        'keyword_count': int(item.get('keyword_count') or 0),
                        'persona_alignment': float(item.get('persona_alignment') or 5.0)
                    }))
    
    async def _store_page_dsi_scores(self, pipeline_id: str, page_dsi: List[Dict], source_type: str = 'organic'):
        """Store page-level DSI scores using SAME formula as company-level"""
        async with self.db.acquire() as conn:
            # Store comprehensive page analysis in historical snapshots only (avoid dsi_scores unique constraint)
            await self._store_page_dsi_snapshots(pipeline_id, page_dsi, source_type)
            
            logger.info(f"Stored page-level DSI scores: {len(page_dsi)}")

    async def _store_page_dsi_snapshots(self, pipeline_id: str, page_dsi: List[Dict], source_type: str):
        """Store comprehensive page-level DSI data in historical snapshots"""
        async with self.db.acquire() as conn:
            snapshot_date = datetime.now().date()
            
            for rank, page in enumerate(page_dsi, 1):
                # Get company information for this domain
                company_info = await conn.fetchrow("""
                    SELECT dcm.display_name as company_name, cp.industry
                    FROM domain_company_mapping dcm
                    LEFT JOIN company_profiles cp ON cp.id = dcm.company_id
                    WHERE dcm.original_domain = $1
                    LIMIT 1
                """, page['domain'])
                
                await conn.execute("""
                    INSERT INTO historical_page_dsi_snapshots (
                        snapshot_date, url, domain, company_name, page_title,
                        page_dsi_score, page_dsi_rank, keyword_count, estimated_traffic,
                        avg_position, top_10_keywords, total_keyword_appearances,
                        content_classification, persona_alignment_scores, jtbd_phase,
                        jtbd_alignment_score, sentiment, word_count, content_quality_score,
                        brand_mention_count, competitor_mention_count, source_type, 
                        industry, is_active
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24
                    )
                    ON CONFLICT (url, snapshot_date) DO UPDATE SET
                        page_dsi_score = EXCLUDED.page_dsi_score,
                        page_dsi_rank = EXCLUDED.page_dsi_rank,
                        keyword_count = EXCLUDED.keyword_count,
                        estimated_traffic = EXCLUDED.estimated_traffic,
                        avg_position = EXCLUDED.avg_position,
                        persona_alignment_scores = EXCLUDED.persona_alignment_scores,
                        jtbd_alignment_score = EXCLUDED.jtbd_alignment_score,
                        content_classification = EXCLUDED.content_classification,
                        brand_mention_count = EXCLUDED.brand_mention_count,
                        competitor_mention_count = EXCLUDED.competitor_mention_count
                """,
                    snapshot_date,                                              # $1
                    page['url'],                                               # $2  
                    page['domain'],                                            # $3
                    company_info['company_name'] if company_info else page['domain'],  # $4
                    page.get('title', '')[:255],                              # $5
                    float(page.get('dsi_score') or 0),                         # $6
                    rank,                                                      # $7
                    int(page.get('keyword_count', 0)),                        # $8
                    int(page.get('total_estimated_traffic') or 0),            # $9
                    float(page.get('avg_position') or 20),                    # $10
                    int(page.get('top_10_count', 0)),                         # $11
                    int(page.get('keyword_count', 0)),                        # $12 (total appearances = keyword count)
                    page.get('overall_sentiment', 'neutral'),                 # $13
                    json.dumps({                                               # $14 (persona alignment scores)
                        'persona': float(page.get('persona_score') or 5.0),
                        'strategic_imperative': float(page.get('strategic_imperative_score') or 5.0),
                        'jtbd': float(page.get('jtbd_score') or 5.0)
                    }),
                    page.get('overall_sentiment', 'neutral'),                 # $15 (jtbd_phase - using sentiment as proxy)
                    float(page.get('jtbd_score') or 5.0),                     # $16
                    page.get('overall_sentiment', 'neutral'),                 # $17
                    len(page.get('overall_insights', '').split()) if page.get('overall_insights') else 0,  # $18 (word count estimate)
                    float(page.get('persona_score') or 5.0) / 10.0,           # $19 (content quality from persona score)
                    int(page.get('brand_mention_count') or 0),                # $20
                    int(page.get('competitor_mention_count') or 0),           # $21
                    source_type,                                               # $22 (source type)
                    company_info['industry'] if company_info else 'Unknown',  # $23
                    True                                                       # $24 (is_active)
                )
            
            logger.info(f"Stored {len(page_dsi)} page DSI snapshots")

