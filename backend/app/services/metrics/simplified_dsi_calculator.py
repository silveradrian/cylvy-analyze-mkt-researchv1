"""
Simplified DSI Calculator that works with current database schema
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger

from app.core.config import Settings
from app.core.database import DatabasePool


class SimplifiedDSICalculator:
    """Simplified DSI Calculator that doesn't require client_id"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        
    async def calculate_dsi_rankings(self) -> Dict[str, Any]:
        """Calculate DSI rankings for all data"""
        try:
            # Calculate organic search DSI
            organic_dsi = await self._calculate_organic_dsi()
            
            # Calculate news DSI
            news_dsi = await self._calculate_news_dsi()
            
            # Calculate YouTube DSI  
            youtube_dsi = await self._calculate_youtube_dsi()
            
            # Count totals
            companies_ranked = len(set(
                [item['domain'] for item in organic_dsi] +
                [item['domain'] for item in news_dsi]
            ))
            
            pages_ranked = len(organic_dsi)
            
            return {
                'companies_ranked': companies_ranked,
                'pages_ranked': pages_ranked,
                'organic_dsi': organic_dsi,
                'news_dsi': news_dsi,
                'youtube_dsi': youtube_dsi
            }
            
        except Exception as e:
            logger.error(f"DSI calculation failed: {e}")
            raise
    
    async def _calculate_organic_dsi(self) -> List[Dict[str, Any]]:
        """Calculate organic search DSI"""
        query = """
            WITH domain_metrics AS (
                SELECT 
                    s.domain,
                    COUNT(DISTINCT s.keyword_id) as keyword_count,
                    COUNT(DISTINCT s.url) as page_count,
                    AVG(s.position) as avg_position,
                    MIN(s.position) as best_position,
                    COUNT(CASE WHEN s.position <= 3 THEN 1 END) as top_3_count,
                    COUNT(CASE WHEN s.position <= 10 THEN 1 END) as top_10_count
                FROM serp_results s
                WHERE s.serp_type = 'organic'
                    AND s.search_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY s.domain
            ),
            market_totals AS (
                SELECT 
                    COUNT(DISTINCT keyword_id) as total_keywords,
                    COUNT(DISTINCT domain) as total_domains
                FROM serp_results
                WHERE serp_type = 'organic'
                    AND search_date >= CURRENT_DATE - INTERVAL '30 days'
            )
            SELECT 
                dm.domain,
                dm.keyword_count,
                dm.page_count,
                dm.avg_position,
                dm.best_position,
                dm.top_3_count,
                dm.top_10_count,
                ROUND(
                    (dm.keyword_count::float / mt.total_keywords * 100)::numeric, 
                    2
                ) as keyword_coverage,
                ROUND(
                    ((dm.top_3_count * 3 + dm.top_10_count * 1)::float / dm.keyword_count * 100)::numeric,
                    2
                ) as visibility_score
            FROM domain_metrics dm
            CROSS JOIN market_totals mt
            ORDER BY dm.keyword_count DESC, dm.avg_position ASC
            LIMIT 100
        """
        
        results = await self.db.fetch(query)
        return [dict(row) for row in results]
    
    async def _calculate_news_dsi(self) -> List[Dict[str, Any]]:
        """Calculate news DSI"""
        query = """
            WITH publisher_metrics AS (
                SELECT 
                    s.domain,
                    COUNT(DISTINCT s.keyword_id) as keyword_count,
                    COUNT(DISTINCT s.url) as article_count,
                    AVG(s.position) as avg_position
                FROM serp_results s
                WHERE s.serp_type = 'news'
                    AND s.search_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY s.domain
            )
            SELECT 
                domain,
                keyword_count,
                article_count,
                avg_position,
                ROUND(
                    (keyword_count * 10 / NULLIF(avg_position, 0))::numeric,
                    2
                ) as news_influence_score
            FROM publisher_metrics
            ORDER BY news_influence_score DESC NULLS LAST
            LIMIT 50
        """
        
        results = await self.db.fetch(query)
        return [dict(row) for row in results]
    
    async def _calculate_youtube_dsi(self) -> List[Dict[str, Any]]:
        """Calculate YouTube DSI"""
        query = """
            WITH video_metrics AS (
                SELECT 
                    s.domain,
                    COUNT(DISTINCT s.keyword_id) as keyword_count,
                    COUNT(DISTINCT s.url) as video_count,
                    AVG(s.position) as avg_position
                FROM serp_results s
                WHERE s.serp_type = 'video'
                    AND s.search_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY s.domain
            )
            SELECT 
                domain,
                keyword_count,
                video_count,
                avg_position,
                ROUND(
                    (keyword_count * video_count / NULLIF(avg_position, 0))::numeric,
                    2
                ) as youtube_visibility_score
            FROM video_metrics
            ORDER BY youtube_visibility_score DESC NULLS LAST
            LIMIT 50
        """
        
        results = await self.db.fetch(query)
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

