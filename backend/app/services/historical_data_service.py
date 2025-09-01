"""
Historical Data Service - Create and manage monthly snapshots for trend analysis
Simplified for single-instance deployment (no tenant isolation)
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
from loguru import logger

from app.core.database import db_pool
from app.core.config import settings


class HistoricalDataService:
    """Service for creating and managing historical data snapshots"""
    
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings
    
    async def create_monthly_snapshot(self, snapshot_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Create comprehensive monthly snapshot for trend analysis
        
        Args:
            snapshot_date: Date for snapshot (defaults to first day of current month)
            
        Returns:
            Summary of snapshot creation results
        """
        if snapshot_date is None:
            now = datetime.now()
            snapshot_date = date(now.year, now.month, 1)
        
        logger.info(f"Creating monthly snapshot for {snapshot_date}")
        
        results = {
            "snapshot_date": snapshot_date.isoformat(),
            "created_at": datetime.now().isoformat(),
            "snapshots_created": {}
        }
        
        try:
            # Create company-level DSI snapshot
            company_count = await self.create_dsi_snapshot(snapshot_date)
            results["snapshots_created"]["company_dsi"] = company_count
            
            # Create page-level DSI snapshot
            page_count = await self.create_page_dsi_snapshot(snapshot_date)
            results["snapshots_created"]["page_dsi"] = page_count
            
            # Create content metrics snapshot
            content_metrics = await self.create_content_metrics_snapshot(snapshot_date)
            results["snapshots_created"]["content_metrics"] = content_metrics
            
            # Update page lifecycle tracking
            lifecycle_updates = await self.update_page_lifecycle_tracking(snapshot_date)
            results["snapshots_created"]["lifecycle_updates"] = lifecycle_updates
            
            # Create keyword metrics snapshot
            keyword_count = await self.create_keyword_metrics_snapshot(snapshot_date)
            results["snapshots_created"]["keyword_metrics"] = keyword_count
            
            # Detect and log content changes
            changes = await self.detect_content_changes(snapshot_date)
            results["snapshots_created"]["content_changes"] = len(changes)
            
            results["success"] = True
            logger.info(f"Monthly snapshot completed: {results}")
            
        except Exception as e:
            logger.error(f"Failed to create monthly snapshot: {e}")
            results["success"] = False
            results["error"] = str(e)
        
        return results
    
    async def create_dsi_snapshot(self, snapshot_date: date) -> int:
        """Create company-level DSI snapshot"""
        async with db_pool.acquire() as conn:
            # Get current DSI data from DSI calculations
            current_dsi = await conn.fetch("""
                WITH latest_calculation AS (
                    SELECT * FROM dsi_calculations 
                    ORDER BY calculation_date DESC LIMIT 1
                ),
                company_rankings AS (
                    SELECT 
                        jsonb_array_elements(company_rankings) as company_data
                    FROM latest_calculation
                )
                SELECT 
                    (company_data->>'domain')::text as company_domain,
                    (company_data->>'company_name')::text as company_name,
                    (company_data->>'dsi_score')::decimal as dsi_score,
                    (company_data->>'dsi_rank')::integer as dsi_rank,
                    (company_data->>'keyword_coverage')::decimal as keyword_coverage,
                    (company_data->>'traffic_share')::decimal as traffic_share,
                    (company_data->>'persona_score')::decimal as persona_score,
                    (company_data->>'unique_keywords')::integer as unique_keywords,
                    (company_data->>'unique_pages')::integer as unique_pages,
                    (company_data->>'estimated_traffic')::integer as estimated_traffic,
                    COALESCE(cp.source, 'unknown') as source_type
                FROM company_rankings cr
                LEFT JOIN company_profiles cp ON (company_data->>'domain') = cp.domain
                WHERE company_data->>'domain' IS NOT NULL
                ORDER BY (company_data->>'dsi_rank')::integer
            """)
            
            # Insert snapshots
            count = 0
            for company in current_dsi:
                await conn.execute("""
                    INSERT INTO historical_dsi_snapshots (
                        snapshot_date, company_domain, company_name,
                        dsi_score, dsi_rank, keyword_coverage, traffic_share,
                        persona_score, unique_keywords, unique_pages,
                        estimated_traffic, source_type
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (snapshot_date, company_domain) 
                    DO UPDATE SET
                        dsi_score = EXCLUDED.dsi_score,
                        dsi_rank = EXCLUDED.dsi_rank,
                        keyword_coverage = EXCLUDED.keyword_coverage,
                        traffic_share = EXCLUDED.traffic_share,
                        persona_score = EXCLUDED.persona_score,
                        unique_keywords = EXCLUDED.unique_keywords,
                        unique_pages = EXCLUDED.unique_pages,
                        estimated_traffic = EXCLUDED.estimated_traffic
                """, 
                snapshot_date, company['company_domain'], company['company_name'],
                company['dsi_score'], company['dsi_rank'], company['keyword_coverage'],
                company['traffic_share'], company['persona_score'], company['unique_keywords'],
                company['unique_pages'], company['estimated_traffic'], company['source_type'])
                count += 1
            
            logger.info(f"Created DSI snapshots for {count} companies")
            return count
    
    async def create_page_dsi_snapshot(self, snapshot_date: date) -> int:
        """Create page-level DSI snapshot"""
        async with db_pool.acquire() as conn:
            # Get current page DSI data with content analysis
            current_pages = await conn.fetch("""
                WITH latest_calculation AS (
                    SELECT * FROM dsi_calculations 
                    ORDER BY calculation_date DESC LIMIT 1
                ),
                page_rankings AS (
                    SELECT 
                        jsonb_array_elements(page_rankings) as page_data
                    FROM latest_calculation
                ),
                page_details AS (
                    SELECT 
                        (page_data->>'url')::text as url,
                        (page_data->>'domain')::text as domain,
                        (page_data->>'page_dsi_score')::decimal as page_dsi_score,
                        (page_data->>'page_dsi_rank')::integer as page_dsi_rank,
                        (page_data->>'keyword_count')::integer as keyword_count,
                        (page_data->>'estimated_traffic')::integer as estimated_traffic,
                        (page_data->>'avg_position')::decimal as avg_position
                    FROM page_rankings
                    WHERE page_data->>'url' IS NOT NULL
                )
                SELECT 
                    pd.url,
                    pd.domain,
                    cp.company_name,
                    sc.title as page_title,
                    pd.page_dsi_score,
                    pd.page_dsi_rank,
                    pd.keyword_count,
                    pd.estimated_traffic,
                    pd.avg_position,
                    ca.content_classification,
                    ca.persona_alignment_scores,
                    ca.jtbd_phase,
                    ca.jtbd_alignment_score,
                    ca.overall_sentiment as sentiment,
                    sc.word_count,
                    cp.source as source_type,
                    cp.industry,
                    md5(COALESCE(sc.content, '')) as content_hash
                FROM page_details pd
                LEFT JOIN scraped_content sc ON pd.url = sc.url
                LEFT JOIN content_analysis ca ON pd.url = ca.url
                LEFT JOIN company_profiles cp ON pd.domain = cp.domain
                ORDER BY pd.page_dsi_score DESC NULLS LAST
            """)
            
            count = 0
            for page in current_pages:
                # Check existing lifecycle data
                lifecycle_data = await conn.fetchrow("""
                    SELECT first_discovered FROM historical_page_lifecycle
                    WHERE url = $1
                """, page['url'])
                
                first_discovered = lifecycle_data['first_discovered'] if lifecycle_data else snapshot_date
                
                await conn.execute("""
                    INSERT INTO historical_page_dsi_snapshots (
                        snapshot_date, url, domain, company_name, page_title,
                        page_dsi_score, page_dsi_rank, keyword_count, estimated_traffic,
                        avg_position, content_classification, persona_alignment_scores,
                        jtbd_phase, jtbd_alignment_score, sentiment, word_count,
                        source_type, industry, content_hash, first_seen_date, 
                        last_seen_date, is_active
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
                    ON CONFLICT (snapshot_date, url) 
                    DO UPDATE SET
                        page_dsi_score = EXCLUDED.page_dsi_score,
                        page_dsi_rank = EXCLUDED.page_dsi_rank,
                        keyword_count = EXCLUDED.keyword_count,
                        estimated_traffic = EXCLUDED.estimated_traffic,
                        content_hash = EXCLUDED.content_hash,
                        last_seen_date = EXCLUDED.last_seen_date
                """,
                snapshot_date, page['url'], page['domain'], page['company_name'],
                page['page_title'], page['page_dsi_score'], page['page_dsi_rank'],
                page['keyword_count'], page['estimated_traffic'], page['avg_position'],
                page['content_classification'], page['persona_alignment_scores'],
                page['jtbd_phase'], page['jtbd_alignment_score'], page['sentiment'],
                page['word_count'], page['source_type'], page['industry'],
                page['content_hash'], first_discovered, snapshot_date, True)
                count += 1
            
            logger.info(f"Created page DSI snapshots for {count} pages")
            return count
    
    async def create_content_metrics_snapshot(self, snapshot_date: date) -> Dict[str, int]:
        """Create content volume metrics snapshot"""
        async with db_pool.acquire() as conn:
            # Get overall content metrics
            metrics = await conn.fetchrow("""
                WITH content_stats AS (
                    SELECT 
                        COUNT(DISTINCT sr.url) as total_serp_results,
                        COUNT(DISTINCT ca.url) as total_content_analyzed,
                        COUNT(DISTINCT cp.domain) as total_companies_tracked,
                        COUNT(DISTINCT CASE WHEN sr.serp_type = 'organic' THEN sr.url END) as organic_results,
                        COUNT(DISTINCT CASE WHEN sr.serp_type = 'news' THEN sr.url END) as news_results,
                        COUNT(DISTINCT CASE WHEN sr.serp_type = 'video' THEN sr.url END) as video_results,
                        COUNT(DISTINCT CASE WHEN sr.location = 'US' THEN sr.url END) as us_results,
                        COUNT(DISTINCT CASE WHEN sr.location = 'UK' THEN sr.url END) as uk_results,
                        AVG((ca.confidence_scores->>'overall')::decimal) as avg_analysis_confidence
                    FROM serp_results sr
                    LEFT JOIN content_analysis ca ON sr.url = ca.url
                    LEFT JOIN company_profiles cp ON sr.domain = cp.domain
                )
                SELECT * FROM content_stats
            """)
            
            # Insert content metrics snapshot
            await conn.execute("""
                INSERT INTO historical_content_metrics (
                    snapshot_date, total_serp_results, total_content_analyzed,
                    total_companies_tracked, organic_results, news_results, video_results,
                    us_results, uk_results, avg_analysis_confidence
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (snapshot_date) DO UPDATE SET
                    total_serp_results = EXCLUDED.total_serp_results,
                    total_content_analyzed = EXCLUDED.total_content_analyzed,
                    total_companies_tracked = EXCLUDED.total_companies_tracked,
                    organic_results = EXCLUDED.organic_results,
                    news_results = EXCLUDED.news_results,
                    video_results = EXCLUDED.video_results,
                    us_results = EXCLUDED.us_results,
                    uk_results = EXCLUDED.uk_results,
                    avg_analysis_confidence = EXCLUDED.avg_analysis_confidence
            """,
            snapshot_date, metrics['total_serp_results'],
            metrics['total_content_analyzed'], metrics['total_companies_tracked'],
            metrics['organic_results'], metrics['news_results'], metrics['video_results'],
            metrics['us_results'], metrics['uk_results'], metrics['avg_analysis_confidence'])
            
            return dict(metrics)
    
    async def update_page_lifecycle_tracking(self, snapshot_date: date) -> int:
        """Update page lifecycle tracking"""
        async with db_pool.acquire() as conn:
            # Update lifecycle data based on page snapshots
            await conn.execute("""
                INSERT INTO historical_page_lifecycle (
                    url, domain, company_name, first_discovered,
                    last_seen_in_serps, peak_dsi_score, peak_dsi_date,
                    avg_dsi_score, total_days_active, lifecycle_status
                )
                SELECT 
                    url,
                    domain,
                    company_name,
                    MIN(snapshot_date) as first_discovered,
                    MAX(snapshot_date) as last_seen_in_serps,
                    MAX(page_dsi_score) as peak_dsi_score,
                    (ARRAY_AGG(snapshot_date ORDER BY page_dsi_score DESC NULLS LAST))[1] as peak_dsi_date,
                    AVG(page_dsi_score) as avg_dsi_score,
                    COUNT(DISTINCT snapshot_date) as total_days_active,
                    CASE 
                        WHEN MAX(snapshot_date) >= $1 - INTERVAL '30 days' THEN 'active'
                        WHEN MAX(snapshot_date) >= $1 - INTERVAL '90 days' THEN 'declining'  
                        ELSE 'disappeared'
                    END as lifecycle_status
                FROM historical_page_dsi_snapshots
                GROUP BY url, domain, company_name
                ON CONFLICT (url) DO UPDATE SET
                    last_seen_in_serps = EXCLUDED.last_seen_in_serps,
                    peak_dsi_score = GREATEST(historical_page_lifecycle.peak_dsi_score, EXCLUDED.peak_dsi_score),
                    peak_dsi_date = CASE 
                        WHEN EXCLUDED.peak_dsi_score > historical_page_lifecycle.peak_dsi_score 
                        THEN EXCLUDED.peak_dsi_date 
                        ELSE historical_page_lifecycle.peak_dsi_date 
                    END,
                    avg_dsi_score = EXCLUDED.avg_dsi_score,
                    total_days_active = EXCLUDED.total_days_active,
                    lifecycle_status = EXCLUDED.lifecycle_status,
                    updated_at = NOW()
            """, snapshot_date)
            
            # Get count of updated lifecycles
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM historical_page_lifecycle
            """)
            
            return result
    
    async def create_keyword_metrics_snapshot(self, snapshot_date: date) -> int:
        """Create keyword performance snapshot"""
        async with db_pool.acquire() as conn:
            # Get keyword performance data
            keywords = await conn.fetch("""
                SELECT 
                    k.id as keyword_id,
                    k.keyword as keyword_text,
                    COUNT(DISTINCT sr.url) as total_results,
                    AVG(sr.position) as avg_position,
                    COUNT(CASE WHEN sr.position <= 10 THEN 1 END) as top_10_results,
                    COUNT(CASE WHEN sr.serp_type = 'organic' THEN 1 END) as organic_results,
                    COUNT(CASE WHEN sr.serp_type = 'news' THEN 1 END) as news_results,
                    COUNT(CASE WHEN sr.serp_type = 'video' THEN 1 END) as video_results,
                    COALESCE(k.avg_monthly_searches, 0) as estimated_monthly_traffic
                FROM keywords k
                LEFT JOIN serp_results sr ON k.id = sr.keyword_id
                GROUP BY k.id, k.keyword, k.avg_monthly_searches
            """)
            
            count = 0
            for keyword in keywords:
                await conn.execute("""
                    INSERT INTO historical_keyword_metrics (
                        snapshot_date, keyword_id, keyword_text,
                        total_results, avg_position, top_10_results,
                        organic_results, news_results, video_results,
                        estimated_monthly_traffic
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (snapshot_date, keyword_id) DO UPDATE SET
                        total_results = EXCLUDED.total_results,
                        avg_position = EXCLUDED.avg_position,
                        top_10_results = EXCLUDED.top_10_results,
                        organic_results = EXCLUDED.organic_results,
                        news_results = EXCLUDED.news_results,
                        video_results = EXCLUDED.video_results,
                        estimated_monthly_traffic = EXCLUDED.estimated_monthly_traffic
                """,
                snapshot_date, keyword['keyword_id'], keyword['keyword_text'],
                keyword['total_results'], keyword['avg_position'], keyword['top_10_results'],
                keyword['organic_results'], keyword['news_results'], keyword['video_results'],
                keyword['estimated_monthly_traffic'])
                count += 1
            
            return count
    
    async def detect_content_changes(self, snapshot_date: date) -> List[Dict]:
        """Detect and log content changes"""
        async with db_pool.acquire() as conn:
            # Find content changes by comparing content hashes
            changes = await conn.fetch("""
                WITH current_snapshot AS (
                    SELECT url, content_hash, page_title, page_dsi_score,
                           content_classification, persona_alignment_scores
                    FROM historical_page_dsi_snapshots
                    WHERE snapshot_date = $1
                ),
                previous_snapshot AS (
                    SELECT url, content_hash, page_title, page_dsi_score,
                           content_classification, persona_alignment_scores,
                           ROW_NUMBER() OVER (PARTITION BY url ORDER BY snapshot_date DESC) as rn
                    FROM historical_page_dsi_snapshots
                    WHERE snapshot_date < $1
                )
                SELECT 
                    c.url,
                    'content_updated' as change_type,
                    p.content_hash as previous_content_hash,
                    c.content_hash as current_content_hash,
                    p.page_title as previous_title,
                    c.page_title as current_title,
                    p.page_dsi_score as dsi_score_before,
                    c.page_dsi_score as dsi_score_after,
                    p.content_classification as classification_before,
                    c.content_classification as classification_after,
                    p.persona_alignment_scores as persona_scores_before,
                    c.persona_alignment_scores as persona_scores_after
                FROM current_snapshot c
                JOIN previous_snapshot p ON c.url = p.url
                WHERE p.rn = 1
                AND (c.content_hash != p.content_hash 
                     OR c.page_title != p.page_title
                     OR c.content_classification != p.content_classification)
            """, snapshot_date)
            
            # Log changes
            change_count = 0
            for change in changes:
                await conn.execute("""
                    INSERT INTO historical_page_content_changes (
                        url, snapshot_date, change_type,
                        previous_content_hash, current_content_hash,
                        previous_title, current_title,
                        dsi_score_before, dsi_score_after,
                        classification_before, classification_after,
                        persona_scores_before, persona_scores_after
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                change['url'], snapshot_date, change['change_type'],
                change['previous_content_hash'], change['current_content_hash'],
                change['previous_title'], change['current_title'],
                change['dsi_score_before'], change['dsi_score_after'],
                change['classification_before'], change['classification_after'],
                change['persona_scores_before'], change['persona_scores_after'])
                change_count += 1
            
            logger.info(f"Detected and logged {change_count} content changes")
            return list(changes)
    
    async def get_month_over_month_dsi(self, limit: int = 50) -> List[Dict]:
        """Get month-over-month DSI changes"""
        async with db_pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM dsi_month_over_month 
                WHERE snapshot_date = (
                    SELECT MAX(snapshot_date) 
                    FROM historical_dsi_snapshots
                )
                ORDER BY dsi_change_percent DESC NULLS LAST
                LIMIT $1
            """, limit)
    
    async def get_page_trends(
        self, 
        months: int = 12, 
        domain: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get page-level trends"""
        async with db_pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM page_dsi_month_over_month 
                WHERE snapshot_date >= CURRENT_DATE - INTERVAL '%s months'
                AND ($2::text IS NULL OR domain = $2)
                AND ($3::text IS NULL OR content_classification = $3)
                ORDER BY dsi_change_percent DESC NULLS LAST
                LIMIT $4
            """ % months, domain, content_type, limit)
    
    async def get_page_lifecycle_data(
        self, 
        status: Optional[str] = None,
        domain: Optional[str] = None
    ) -> List[Dict]:
        """Get page lifecycle analysis"""
        async with db_pool.acquire() as conn:
            return await conn.fetch("""
                SELECT 
                    url, domain, company_name, first_discovered, last_seen_in_serps,
                    peak_dsi_score, peak_dsi_date, avg_dsi_score, total_days_active,
                    lifecycle_status, (CURRENT_DATE - first_discovered) as page_age_days
                FROM historical_page_lifecycle 
                WHERE ($1::text IS NULL OR lifecycle_status = $1)
                AND ($2::text IS NULL OR domain = $2)
                ORDER BY peak_dsi_score DESC NULLS LAST
            """, status, domain)
    
    async def get_trending_content(self, days: int = 30) -> List[Dict]:
        """Get trending content based on DSI changes"""
        async with db_pool.acquire() as conn:
            return await conn.fetch("""
                WITH recent_snapshots AS (
                    SELECT * FROM historical_page_dsi_snapshots
                    WHERE snapshot_date >= CURRENT_DATE - INTERVAL '%s days'
                ),
                trending AS (
                    SELECT 
                        url,
                        domain,
                        page_title,
                        MAX(page_dsi_score) - MIN(page_dsi_score) as dsi_improvement,
                        AVG(page_dsi_score) as avg_dsi_score,
                        MAX(snapshot_date) as latest_snapshot,
                        COUNT(*) as snapshot_count
                    FROM recent_snapshots
                    GROUP BY url, domain, page_title
                    HAVING COUNT(*) >= 2 AND MAX(page_dsi_score) > MIN(page_dsi_score)
                )
                SELECT * FROM trending
                ORDER BY dsi_improvement DESC
                LIMIT 20
            """ % days)
    
    async def schedule_monthly_snapshots(self):
        """Schedule automatic monthly snapshot creation"""
        logger.info("Monthly snapshot automation would integrate with SchedulingService")
        # This would be called by the SchedulingService on a monthly basis
