"""
Simple Landscape Calculator Service
Integrates with existing DSI calculator to provide landscape-filtered metrics
"""
import logging
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.core.database import db_pool
from app.models.dsi import DSICalculationRequest, DSIType, CompanyDSIMetrics, PageDSIMetrics
from app.models.landscape import (
    LandscapeCalculationResult, LandscapeDSIMetrics, 
    EntityType, LandscapeSummary
)
from app.services.metrics.dsi_calculator import DSICalculator

logger = logging.getLogger(__name__)


class SimpleLandscapeCalculator:
    """Simple landscape calculator that stores all metrics"""
    
    def __init__(self, dsi_calculator: DSICalculator, db=None):
        self.dsi_calculator = dsi_calculator
        self.db = db or db_pool
    
    async def calculate_and_store_landscape_dsi(self, landscape_id: str) -> LandscapeCalculationResult:
        """Calculate DSI for landscape and store ALL metrics"""
        start_time = time.time()
        
        try:
            # Get landscape details
            landscape = await self._get_landscape_details(landscape_id)
            if not landscape:
                raise ValueError(f"Landscape {landscape_id} not found")
            
            # Get keywords for this landscape
            landscape_keywords = await self._get_landscape_keywords(landscape_id)
            
            if not landscape_keywords:
                logger.warning(f"No keywords assigned to landscape {landscape_id}")
                return LandscapeCalculationResult(
                    landscape_id=UUID(landscape_id),
                    calculation_date=datetime.now().date(),
                    total_companies=0,
                    total_keywords=0,
                    companies=[],
                    calculation_duration_seconds=time.time() - start_time
                )
            
            logger.info(f"Calculating DSI for landscape '{landscape['name']}' with {len(landscape_keywords)} keywords")
            
            # Create DSI calculation request
            # Note: For simplicity, we'll calculate based on available data
            # In a real implementation, you might want to filter SERP data by keywords
            request = DSICalculationRequest(
                client_id="system",  # Use system client for landscape calculations
                dsi_types=[DSIType.ORGANIC],
                lookback_days=30,
                include_detailed_metrics=True
            )
            
            # Use existing DSI calculator
            dsi_result = await self.dsi_calculator.calculate(request)
            
            # Filter and process results based on landscape keywords
            filtered_companies = await self._filter_companies_by_keywords(
                dsi_result.organic_results or [], 
                landscape_keywords, 
                landscape_id
            )
            
            # Store detailed metrics for companies
            if filtered_companies:
                await self._store_detailed_company_metrics(landscape_id, filtered_companies)
                
                # Store page-level metrics if available
                for company_metric in filtered_companies:
                    if company_metric.page_metrics:
                        await self._store_detailed_page_metrics(landscape_id, company_metric.page_metrics)
            
            calculation_duration = time.time() - start_time
            
            result = LandscapeCalculationResult(
                landscape_id=UUID(landscape_id),
                calculation_date=datetime.now().date(),
                total_companies=len(filtered_companies),
                total_keywords=len(landscape_keywords),
                companies=[self._format_company_summary(cm) for cm in filtered_companies],
                calculation_duration_seconds=calculation_duration
            )
            
            logger.info(f"Landscape DSI calculation completed in {calculation_duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating landscape DSI: {str(e)}")
            raise
    
    async def _get_landscape_details(self, landscape_id: str) -> Optional[Dict[str, Any]]:
        """Get landscape details"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, name, description, is_active
                FROM digital_landscapes
                WHERE id = $1 AND is_active = true
            """, landscape_id)
            return dict(row) if row else None
    
    async def _get_landscape_keywords(self, landscape_id: str) -> List[str]:
        """Get keyword strings for a landscape"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT k.keyword, k.id as keyword_id
                FROM landscape_keywords lk
                JOIN keywords k ON lk.keyword_id = k.id
                WHERE lk.landscape_id = $1
                ORDER BY k.keyword
            """, landscape_id)
            return [row['keyword'] for row in rows]
    
    async def _filter_companies_by_keywords(
        self, 
        company_metrics: List[CompanyDSIMetrics], 
        landscape_keywords: List[str],
        landscape_id: str
    ) -> List[CompanyDSIMetrics]:
        """
        Filter company metrics based on landscape keywords
        For simplicity, we'll use all companies but could filter by domain presence in keyword results
        """
        # In a real implementation, you'd filter SERP results by keywords first
        # For now, we'll use the existing company metrics
        
        # Re-rank companies within the landscape context
        for idx, company in enumerate(company_metrics):
            company.rank_in_market = idx + 1
            company.total_companies_in_market = len(company_metrics)
        
        return company_metrics
    
    async def _store_detailed_company_metrics(self, landscape_id: str, company_metrics: List[CompanyDSIMetrics]):
        """Store all company-level metrics"""
        calculation_date = datetime.now().date()
        
        async with self.db.acquire() as conn:
            for company in company_metrics:
                await conn.execute("""
                    INSERT INTO landscape_dsi_metrics (
                        landscape_id, calculation_date, entity_type, entity_id, entity_name, 
                        entity_domain, unique_keywords, unique_pages, keyword_coverage, 
                        estimated_traffic, traffic_share, persona_alignment, funnel_value, 
                        dsi_score, rank_in_landscape, total_entities_in_landscape, market_position
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (landscape_id, calculation_date, entity_type, entity_id)
                    DO UPDATE SET 
                        unique_keywords = EXCLUDED.unique_keywords,
                        unique_pages = EXCLUDED.unique_pages,
                        keyword_coverage = EXCLUDED.keyword_coverage,
                        estimated_traffic = EXCLUDED.estimated_traffic,
                        traffic_share = EXCLUDED.traffic_share,
                        persona_alignment = EXCLUDED.persona_alignment,
                        funnel_value = EXCLUDED.funnel_value,
                        dsi_score = EXCLUDED.dsi_score,
                        rank_in_landscape = EXCLUDED.rank_in_landscape,
                        market_position = EXCLUDED.market_position,
                        created_at = NOW()
                """,
                    landscape_id, calculation_date, EntityType.COMPANY.value, company.company_id,
                    company.company_name, company.domain, company.total_keywords,
                    company.total_pages, float(company.keyword_coverage), int(company.total_traffic),
                    float(company.traffic_share), float(company.avg_relevance or 0), 
                    float(company.avg_funnel_value or 0), float(company.dsi_score), 
                    company.rank_in_market, company.total_companies_in_market,
                    company.market_position.value
                )
        
        logger.info(f"Stored metrics for {len(company_metrics)} companies in landscape {landscape_id}")
    
    async def _store_detailed_page_metrics(self, landscape_id: str, page_metrics: List[PageDSIMetrics]):
        """Store all page-level metrics"""
        calculation_date = datetime.now().date()
        
        async with self.db.acquire() as conn:
            for page in page_metrics:
                await conn.execute("""
                    INSERT INTO landscape_dsi_metrics (
                        landscape_id, calculation_date, entity_type, entity_id, entity_name,
                        entity_domain, entity_url, unique_keywords, unique_pages,
                        keyword_coverage, estimated_traffic, traffic_share, persona_alignment,
                        funnel_value, dsi_score, rank_in_landscape, total_entities_in_landscape
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (landscape_id, calculation_date, entity_type, entity_id)
                    DO UPDATE SET 
                        unique_keywords = EXCLUDED.unique_keywords,
                        estimated_traffic = EXCLUDED.estimated_traffic,
                        dsi_score = EXCLUDED.dsi_score,
                        rank_in_landscape = EXCLUDED.rank_in_landscape,
                        created_at = NOW()
                """,
                    landscape_id, calculation_date, EntityType.PAGE.value, page.page_id,
                    page.title, page.domain, page.url, page.total_keywords,
                    1, float(page.keyword_coverage or 0), int(page.total_traffic),
                    float(page.traffic_share or 0), float(page.avg_relevance or 0), 
                    float(page.avg_funnel_value or 0), float(page.dsi_score),
                    page.rank_in_market, getattr(page, 'total_pages_in_market', 1)
                )
        
        logger.info(f"Stored metrics for {len(page_metrics)} pages in landscape {landscape_id}")
    
    async def get_landscape_summary(self, landscape_id: str, calculation_date: Optional[date] = None) -> Optional[LandscapeSummary]:
        """Get summary statistics for a landscape"""
        if not calculation_date:
            calculation_date = datetime.now().date()
        
        async with self.db.acquire() as conn:
            # Get latest calculation date if none provided
            if not calculation_date:
                latest_date = await conn.fetchval("""
                    SELECT MAX(calculation_date) FROM landscape_dsi_metrics 
                    WHERE landscape_id = $1
                """, landscape_id)
                
                if not latest_date:
                    return None
                calculation_date = latest_date
            
            # Get summary stats
            summary = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_companies,
                    COALESCE(SUM(unique_keywords), 0) as total_keywords,
                    COALESCE(SUM(unique_pages), 0) as total_pages,
                    COALESCE(SUM(estimated_traffic), 0) as total_traffic,
                    COALESCE(AVG(dsi_score), 0) as avg_dsi_score,
                    COALESCE(MAX(dsi_score), 0) as top_dsi_score
                FROM landscape_dsi_metrics
                WHERE landscape_id = $1 
                    AND calculation_date = $2 
                    AND entity_type = $3
            """, landscape_id, calculation_date, EntityType.COMPANY.value)
            
            if not summary or summary['total_companies'] == 0:
                return None
            
            return LandscapeSummary(
                landscape_id=UUID(landscape_id),
                calculation_date=calculation_date,
                total_companies=summary['total_companies'],
                total_keywords=summary['total_keywords'],
                total_pages=summary['total_pages'],
                total_traffic=summary['total_traffic'],
                avg_dsi_score=float(summary['avg_dsi_score']),
                top_dsi_score=float(summary['top_dsi_score'])
            )
    
    def _format_company_summary(self, company_metric: CompanyDSIMetrics) -> Dict[str, Any]:
        """Format company metric for API response"""
        return {
            "company_id": str(company_metric.company_id),
            "company_name": company_metric.company_name,
            "domain": company_metric.domain,
            "dsi_score": float(company_metric.dsi_score),
            "rank": company_metric.rank_in_market,
            "unique_keywords": company_metric.total_keywords,
            "unique_pages": company_metric.total_pages,
            "estimated_traffic": int(company_metric.total_traffic),
            "keyword_coverage": float(company_metric.keyword_coverage),
            "traffic_share": float(company_metric.traffic_share),
            "market_position": company_metric.market_position.value
        }

