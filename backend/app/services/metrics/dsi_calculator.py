"""
DSI (Digital Share of Intelligence) Calculator Service
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4
import hashlib
import logging

logger = logging.getLogger(__name__)
from app.models.dsi import (
    DSIType, MarketPosition, DSICalculationRequest, DSICalculationResult,
    CompanyDSIMetrics, PageDSIMetrics, PublisherDSIMetrics, ArticleDSIMetrics,
    YouTubeChannelDSIMetrics, YouTubeVideoDSIMetrics, MarketTotals,
    OrganicDSIRequest, NewsDSIRequest, YouTubeDSIRequest
)
from app.core.database import AsyncConnection
from app.core.config import Settings




class DSICalculator:
    """Service for calculating Digital Share of Intelligence metrics"""
    
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db
        
    async def calculate(self, request: DSICalculationRequest) -> DSICalculationResult:
        """Calculate DSI based on request parameters"""
        job_id = uuid4()
        period_end = datetime.utcnow().date()
        period_start = period_end - timedelta(days=request.lookback_days)
        
        logger.info(f"Starting DSI calculation job {job_id} for client {request.client_id}")
        
        # Initialize with default market totals
        default_market_totals = MarketTotals(
            total_keywords=0,
            total_traffic=0.0,
            total_companies=0,
            total_pages=0,
            avg_relevance=0.0,
            calculation_date=datetime.utcnow()
        )
        
        result = DSICalculationResult(
            job_id=job_id,
            client_id=request.client_id,
            calculation_type=request.dsi_types[0],  # Primary type
            lookback_days=request.lookback_days,
            period_start=period_start,
            period_end=period_end,
            calculated_at=datetime.utcnow(),
            market_totals=default_market_totals,
            client_total_dsi=0.0,
            client_market_share=0.0,
            top_performers=[],
            insights=[]
        )
        
        # Calculate based on requested types
        for dsi_type in request.dsi_types:
            if dsi_type == DSIType.ORGANIC:
                organic_results = await self._calculate_organic_dsi(
                    request.client_id, 
                    period_start, 
                    period_end,
                    request.include_detailed_metrics
                )
                result.organic_results = organic_results
                
            elif dsi_type == DSIType.NEWS:
                news_results = await self._calculate_news_dsi(
                    request.client_id,
                    period_start,
                    period_end,
                    request.include_detailed_metrics
                )
                result.news_results = news_results
                
            elif dsi_type == DSIType.YOUTUBE:
                youtube_results = await self._calculate_youtube_dsi(
                    request.client_id,
                    period_start,
                    period_end,
                    request.include_detailed_metrics
                )
                result.youtube_results = youtube_results
        
        # Calculate market totals
        result.market_totals = await self._calculate_market_totals(
            request.client_id, period_start, period_end
        )
        
        # Generate insights
        result.insights = self._generate_insights(result)
        
        # Store results - commented out for now as table schema doesn't match
        # await self._store_results(result)
        
        logger.info(f"Completed DSI calculation job {job_id}")
        return result
    
    async def _calculate_organic_dsi(
        self, 
        client_id: str, 
        period_start: datetime, 
        period_end: datetime,
        include_page_metrics: bool = True
    ) -> List[CompanyDSIMetrics]:
        """Calculate organic search DSI at company and page levels"""
        
        # Get company-level aggregates
        company_query = """
            WITH company_aggregates AS (
                SELECT 
                    s.domain,
                    c.company_name as company_name,
                    c.id as company_id,
                    COUNT(DISTINCT s.keyword_id) as total_keywords,
                    SUM(s.estimated_traffic) as total_traffic,
                    COUNT(DISTINCT s.url) as total_pages,
                    AVG(ca.jtbd_alignment_score) as avg_relevance,
                    AVG(CASE 
                        WHEN ca.content_classification = 'BUY' THEN 1.0
                        WHEN ca.content_classification = 'CONVERT/TRY' THEN 0.8
                        WHEN ca.content_classification = 'LEARN' THEN 0.6
                        WHEN ca.content_classification = 'ATTRACT' THEN 0.4
                        ELSE 0.2
                    END) as avg_funnel_value
                FROM serp_results s
                JOIN company_profiles c ON s.domain = c.domain
                LEFT JOIN content_analysis ca ON s.url = ca.url AND ca.client_id = $1
                WHERE s.client_id = $1
                    AND s.search_date >= $2::date
                    AND s.search_date <= $3::date
                    AND s.result_type = 'organic'
                GROUP BY s.domain, c.company_name, c.id
            ),
            market_totals AS (
                SELECT 
                    SUM(total_keywords) as market_keywords,
                    SUM(total_traffic) as market_traffic,
                    COUNT(*) as total_companies
                FROM company_aggregates
            )
            SELECT 
                ca.*,
                ca.total_keywords::float / NULLIF(mt.market_keywords, 0) as keyword_coverage,
                ca.total_traffic / NULLIF(mt.market_traffic, 0) as traffic_share,
                -- Calculate DSI score
                ROUND(
                    ((ca.total_keywords::float / NULLIF(mt.market_keywords, 0)) * 
                    (ca.total_traffic / NULLIF(mt.market_traffic, 0)) * 
                    COALESCE(ca.avg_relevance, 0.5) *
                    ca.avg_funnel_value * 100)::numeric, 
                    2
                ) as dsi_score,
                mt.total_companies
            FROM company_aggregates ca
            CROSS JOIN market_totals mt
            ORDER BY dsi_score DESC
        """
        
        results = await self.db.fetch(company_query, client_id, period_start, period_end)
        
        company_metrics = []
        for idx, row in enumerate(results):
            # Determine market position
            dsi_score = row['dsi_score'] or 0
            if dsi_score >= 30:
                market_position = MarketPosition.LEADER
            elif dsi_score >= 15:
                market_position = MarketPosition.CHALLENGER
            elif dsi_score >= 5:
                market_position = MarketPosition.COMPETITOR
            else:
                market_position = MarketPosition.NICHE
            
            company_metric = CompanyDSIMetrics(
                company_id=row['company_id'],
                domain=row['domain'],
                company_name=row['company_name'],
                total_keywords=row['total_keywords'],
                total_traffic=row['total_traffic'],
                total_pages=row['total_pages'],
                keyword_coverage=row['keyword_coverage'] or 0,
                traffic_share=row['traffic_share'] or 0,
                avg_relevance=row['avg_relevance'] or 0,
                                    avg_funnel_value=row['avg_funnel_value'] or 0,
                dsi_score=dsi_score,
                market_position=market_position,
                rank_in_market=idx + 1,
                total_companies_in_market=row['total_companies']
            )
            
            # Get page-level metrics if requested
            if include_page_metrics:
                company_metric.page_metrics = await self._get_page_metrics(
                    client_id, row['domain'], period_start, period_end
                )
            
            company_metrics.append(company_metric)
        
        return company_metrics
    
    async def _get_page_metrics(
        self, 
        client_id: str, 
        domain: str, 
        period_start: datetime, 
        period_end: datetime
    ) -> List[PageDSIMetrics]:
        """Get page-level DSI metrics for a company"""
        
        query = """
            WITH page_aggregates AS (
                SELECT 
                    COALESCE(s.content_asset_id, s.id) as page_id,
                    s.url,
                    s.title,
                    ca.content_classification as content_type,
                    COUNT(DISTINCT s.keyword_id) as keyword_count,
                    SUM(s.estimated_traffic) as estimated_traffic,
                    AVG(ca.jtbd_alignment_score) as relevance_score,
                    CASE 
                        WHEN ca.content_classification = 'BUY' THEN 1.0
                        WHEN ca.content_classification = 'CONVERT/TRY' THEN 0.8
                        WHEN ca.content_classification = 'LEARN' THEN 0.6
                        WHEN ca.content_classification = 'ATTRACT' THEN 0.4
                        ELSE 0.2
                    END as funnel_value
                FROM serp_results s
                LEFT JOIN content_analysis ca ON s.url = ca.url AND ca.client_id = $1
                WHERE s.client_id = $1
                    AND s.domain = $2
                    AND s.search_date >= $3::date
                    AND s.search_date <= $4::date
                    AND s.result_type = 'organic'
                GROUP BY COALESCE(s.content_asset_id, s.id), s.url, s.title, ca.content_classification
            ),
            company_totals AS (
                SELECT 
                    SUM(keyword_count) as total_keywords,
                    SUM(estimated_traffic) as total_traffic
                FROM page_aggregates
            )
            SELECT 
                pa.*,
                pa.keyword_count::float / NULLIF(ct.total_keywords, 0) as keyword_coverage,
                pa.estimated_traffic / NULLIF(ct.total_traffic, 0) as traffic_share,
                -- Calculate page DSI
                ROUND(
                    ((pa.keyword_count::float / NULLIF(ct.total_keywords, 0)) * 
                    (pa.estimated_traffic / NULLIF(ct.total_traffic, 0)) * 
                    COALESCE(pa.relevance_score, 0.5) *
                    pa.funnel_value * 100)::numeric, 
                    2
                ) as dsi_score
            FROM page_aggregates pa
            CROSS JOIN company_totals ct
            ORDER BY dsi_score DESC
        """
        
        results = await self.db.fetch(query, client_id, domain, period_start, period_end)
        
        page_metrics = []
        for idx, row in enumerate(results):
            page_metrics.append(PageDSIMetrics(
                page_id=row['page_id'],
                url=row['url'],
                title=row['title'] or '',
                content_type=row['content_type'],
                keyword_count=row['keyword_count'],
                estimated_traffic=row['estimated_traffic'],
                keyword_coverage=row['keyword_coverage'] or 0,
                traffic_share=row['traffic_share'] or 0,
                relevance_score=row['relevance_score'] or 0,
                                    funnel_value=row['funnel_value'],
                dsi_score=row['dsi_score'] or 0,
                rank_in_company=idx + 1,
                rank_in_market=0  # Will be calculated separately
            ))
        
        return page_metrics
    
    async def _calculate_news_dsi(
        self, 
        client_id: str, 
        period_start: datetime, 
        period_end: datetime,
        include_article_metrics: bool = True
    ) -> List[PublisherDSIMetrics]:
        """Calculate news DSI based on SERP appearances and relevance"""
        
        query = """
            WITH publisher_aggregates AS (
                SELECT 
                    s.domain as publisher_domain,
                    c.company_name as publisher_name,
                    COUNT(DISTINCT s.url) as total_articles,
                    COUNT(*) as total_serp_appearances,
                    COUNT(DISTINCT s.keyword_id) as keywords_covered,
                    AVG(ca.persona_alignment_scores::json->>'IT Director') as avg_persona_relevance
                FROM serp_results s
                JOIN company_profiles c ON s.domain = c.domain
                LEFT JOIN content_analysis ca ON s.url = ca.url AND ca.client_id = $1
                WHERE s.client_id = $1
                    AND s.search_date >= $2::date
                    AND s.search_date <= $3::date
                    AND s.result_type = 'news'
                GROUP BY s.domain, c.company_name
            ),
            market_totals AS (
                SELECT 
                    COUNT(DISTINCT keyword_id) as total_keywords,
                    SUM(total_serp_appearances) as total_appearances
                FROM (
                    SELECT DISTINCT keyword_id 
                    FROM serp_results 
                    WHERE client_id = $1 
                                            AND search_date >= $2::date
                    AND search_date <= $3::date
                        AND result_type = 'news'
                ) k,
                publisher_aggregates
            )
            SELECT 
                pa.*,
                pa.keywords_covered::float / NULLIF(mt.total_keywords, 0) as keyword_coverage,
                -- Calculate news DSI based on appearances, coverage, and relevance
                ROUND(
                    ((pa.total_serp_appearances::float / NULLIF(mt.total_appearances, 0)) * 
                    (pa.keywords_covered::float / NULLIF(mt.total_keywords, 0)) * 
                    COALESCE(pa.avg_persona_relevance, 0.5) * 100)::numeric, 
                    2
                ) as dsi_score
            FROM publisher_aggregates pa
            CROSS JOIN market_totals mt
            ORDER BY dsi_score DESC
        """
        
        results = await self.db.fetch(query, client_id, period_start, period_end)
        
        publisher_metrics = []
        for idx, row in enumerate(results):
            publisher_metrics.append(PublisherDSIMetrics(
                publisher_domain=row['publisher_domain'],
                publisher_name=row['publisher_name'],
                total_articles=row['total_articles'],
                total_serp_appearances=row['total_serp_appearances'],
                keyword_coverage=row['keyword_coverage'] or 0,
                avg_persona_relevance=row['avg_persona_relevance'] or 0.5,
                dsi_score=row['dsi_score'] or 0,
                rank_in_market=idx + 1
            ))
        
        return publisher_metrics
    
    async def _calculate_youtube_dsi(
        self, 
        client_id: str, 
        period_start: datetime, 
        period_end: datetime,
        include_video_metrics: bool = True
    ) -> List[YouTubeChannelDSIMetrics]:
        """Calculate YouTube DSI based on SERP appearances and engagement"""
        
        query = """
            WITH channel_aggregates AS (
                SELECT 
                    y.channel_id,
                    y.channel_name,
                    COUNT(DISTINCT y.video_id) as total_videos,
                    SUM(y.view_count) as total_views,
                    SUM(y.like_count) as total_likes,
                    SUM(y.comment_count) as total_comments,
                    MAX(y.subscriber_count) as subscriber_count,
                    COUNT(DISTINCT s.keyword_id) as keywords_covered,
                    COUNT(*) as serp_appearances
                FROM youtube_videos y
                JOIN serp_results s ON y.url = s.url
                WHERE s.client_id = $1
                    AND s.search_date >= $2::date
                    AND s.search_date <= $3::date
                    AND s.result_type = 'video'
                GROUP BY y.channel_id, y.channel_name
            ),
            market_totals AS (
                SELECT 
                    COUNT(DISTINCT keyword_id) as total_keywords,
                    SUM(serp_appearances) as total_appearances,
                    SUM(total_views) as market_views
                FROM (
                    SELECT DISTINCT keyword_id 
                    FROM serp_results 
                    WHERE client_id = $1 
                                            AND search_date >= $2::date
                    AND search_date <= $3::date
                        AND result_type = 'video'
                ) k,
                channel_aggregates
            )
            SELECT 
                ca.*,
                ca.keywords_covered::float / NULLIF(mt.total_keywords, 0) as keyword_coverage,
                (ca.total_likes + ca.total_comments)::float / NULLIF(ca.total_views, 0) as engagement_rate,
                -- Calculate YouTube DSI based on appearances, coverage, and engagement
                ROUND(
                    ((ca.serp_appearances::float / NULLIF(mt.total_appearances, 0)) * 
                    (ca.keywords_covered::float / NULLIF(mt.total_keywords, 0)) * 
                    ((ca.total_likes + ca.total_comments)::float / NULLIF(ca.total_views, 0) * 10) * 100)::numeric, 
                    2
                ) as dsi_score
            FROM channel_aggregates ca
            CROSS JOIN market_totals mt
            ORDER BY dsi_score DESC
        """
        
        results = await self.db.fetch(query, client_id, period_start, period_end)
        
        channel_metrics = []
        for idx, row in enumerate(results):
            channel_metrics.append(YouTubeChannelDSIMetrics(
                channel_id=row['channel_id'],
                channel_name=row['channel_name'],
                total_videos=row['total_videos'],
                total_views=row['total_views'],
                total_likes=row['total_likes'],
                total_comments=row['total_comments'],
                subscriber_count=row['subscriber_count'],
                serp_appearances=row['serp_appearances'],
                keyword_coverage=row['keyword_coverage'] or 0,
                engagement_rate=row['engagement_rate'] or 0,
                dsi_score=row['dsi_score'] or 0,
                rank_in_market=idx + 1
            ))
        
        return channel_metrics
    
    async def _calculate_market_totals(
        self, 
        client_id: str, 
        period_start: datetime, 
        period_end: datetime
    ) -> MarketTotals:
        """Calculate market-wide totals"""
        
        query = """
            SELECT 
                COUNT(DISTINCT s.keyword_id) as total_keywords,
                SUM(s.estimated_traffic) as total_traffic,
                COUNT(DISTINCT s.domain) as total_companies,
                COUNT(DISTINCT s.url) as total_pages,
                AVG(ca.jtbd_alignment_score) as avg_relevance
            FROM serp_results s
            LEFT JOIN content_analysis ca ON s.url = ca.url AND ca.client_id = $1
            WHERE s.client_id = $1
                AND s.search_date >= $2
                AND s.search_date <= $3
        """
        
        result = await self.db.fetchrow(query, client_id, period_start, period_end)
        
        return MarketTotals(
            total_keywords=result['total_keywords'] or 0,
            total_traffic=result['total_traffic'] or 0,
            total_companies=result['total_companies'] or 0,
            total_pages=result['total_pages'] or 0,
            avg_relevance=result['avg_relevance'] or 0.5,
            calculation_date=datetime.utcnow()
        )
    
    def _generate_insights(self, result: DSICalculationResult) -> List[str]:
        """Generate insights based on DSI results"""
        insights = []
        
        # Organic insights
        if result.organic_results:
            leaders = [c for c in result.organic_results if c.market_position == MarketPosition.LEADER]
            if leaders:
                insights.append(f"Market leaders: {', '.join([l.company_name for l in leaders[:3]])}")
            
            # Traffic concentration
            top_3_traffic = sum(c.traffic_share for c in result.organic_results[:3])
            if top_3_traffic > 0.5:
                insights.append(f"Top 3 companies control {top_3_traffic:.1%} of market traffic")
        
        # News insights
        if result.news_results:
            top_publisher = result.news_results[0] if result.news_results else None
            if top_publisher:
                insights.append(f"Top news publisher: {top_publisher.publisher_name} ({top_publisher.dsi_score:.1f} DSI)")
        
        # YouTube insights  
        if result.youtube_results:
            high_engagement = [c for c in result.youtube_results if c.engagement_rate > 0.05]
            if high_engagement:
                insights.append(f"{len(high_engagement)} YouTube channels with >5% engagement rate")
        
        return insights
    
    async def _store_results(self, result: DSICalculationResult):
        """Store DSI calculation results"""
        
        # Store main result
        await self.db.execute("""
            INSERT INTO dsi_calculations (
                job_id, client_id, calculation_type, lookback_days,
                period_start, period_end, calculated_at,
                market_totals, results, insights
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, 
            result.job_id, result.client_id, result.calculation_type,
            result.lookback_days, result.period_start, result.period_end,
            result.calculated_at, result.market_totals.dict() if result.market_totals else None,
            result.dict(), result.insights
        )
        
        # Store historical trends
        if result.organic_results:
            for company in result.organic_results:
                await self._store_trend(
                    result.client_id, company.domain, DSIType.ORGANIC,
                    company.dsi_score, company.market_position, company.rank_in_market
                )
    
    async def _store_trend(
        self, 
        client_id: str, 
        entity_id: str, 
        entity_type: DSIType,
        dsi_score: float, 
        market_position: MarketPosition, 
        rank: int
    ):
        """Store historical trend data"""
        
        period = datetime.utcnow().strftime("%Y-%m")
        
        # Get previous month's score for change calculation
        prev_score = await self.db.fetchval("""
            SELECT dsi_score 
            FROM dsi_historical_trends 
            WHERE client_id = $1 AND entity_id = $2 AND entity_type = $3
            ORDER BY period DESC LIMIT 1
        """, client_id, entity_id, entity_type)
        
        change_from_previous = None
        if prev_score is not None:
            change_from_previous = dsi_score - prev_score
        
        await self.db.execute("""
            INSERT INTO dsi_historical_trends (
                client_id, entity_id, entity_type, period,
                dsi_score, market_position, rank, change_from_previous
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (client_id, entity_id, entity_type, period) 
            DO UPDATE SET 
                dsi_score = EXCLUDED.dsi_score,
                market_position = EXCLUDED.market_position,
                rank = EXCLUDED.rank,
                change_from_previous = EXCLUDED.change_from_previous
        """, 
            client_id, entity_id, entity_type, period,
            dsi_score, market_position, rank, change_from_previous
        ) 