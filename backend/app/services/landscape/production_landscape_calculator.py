"""
Production-Ready Landscape Calculator Service
Properly implements keyword filtering for landscape-specific DSI calculations
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

logger = logging.getLogger(__name__)


class ProductionLandscapeCalculator:
    """Production-ready landscape calculator with proper keyword filtering"""
    
    def __init__(self, db=None):
        self.db = db or db_pool
    
    async def calculate_and_store_landscape_dsi(self, landscape_id: str, client_id: str) -> LandscapeCalculationResult:
        """Calculate DSI for landscape with proper keyword filtering"""
        start_time = time.time()
        
        try:
            # Get landscape details
            landscape = await self._get_landscape_details(landscape_id)
            if not landscape:
                raise ValueError(f"Landscape {landscape_id} not found")
            
            # Get keywords for this landscape
            landscape_keywords = await self._get_landscape_keyword_ids(landscape_id)
            
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
            
            # Calculate DSI metrics using filtered SERP data (organic only for now)
            company_metrics = await self._calculate_landscape_specific_dsi(
                client_id, landscape_keywords, landscape_id, 'organic'
            )
            
            # Store detailed metrics
            if company_metrics:
                await self._store_detailed_company_metrics(landscape_id, company_metrics)
                
                # Store page-level metrics if available
                for company_metric in company_metrics:
                    if hasattr(company_metric, 'page_metrics') and company_metric.page_metrics:
                        await self._store_detailed_page_metrics(landscape_id, company_metric.page_metrics)
            
            calculation_duration = time.time() - start_time
            
            result = LandscapeCalculationResult(
                landscape_id=UUID(landscape_id),
                calculation_date=datetime.now().date(),
                total_companies=len(company_metrics),
                total_keywords=len(landscape_keywords),
                companies=[self._format_company_summary(cm) for cm in company_metrics],
                calculation_duration_seconds=calculation_duration
            )
            
            logger.info(f"Landscape DSI calculation completed in {calculation_duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating landscape DSI: {str(e)}")
            raise
    
    async def _calculate_landscape_specific_dsi(
        self, 
        client_id: str, 
        keyword_ids: List[str], 
        landscape_id: str,
        search_type: str = 'organic'
    ) -> List[CompanyDSIMetrics]:
        """Calculate DSI using only landscape-specific SERP results for specified search type"""
        
        calculation_date = datetime.now().date()
        period_start = calculation_date - timedelta(days=30)
        
        # CORRECTED: Get SERP results with proper traffic calculation and domain mapping
        async with self.db.acquire() as conn:
            company_query = """
                WITH landscape_serp AS (
                    SELECT 
                        s.domain,
                        s.keyword_id,
                        s.url,
                        s.position,
                        k.keyword,
                        k.avg_monthly_searches,
                        -- REALISTIC TRAFFIC ESTIMATION: Search Volume × Industry-Standard CTR
                        COALESCE(k.avg_monthly_searches, 1000) * CASE 
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
                            WHEN s.position <= 20 THEN 0.0150 -- 1.5%
                            ELSE 0.0050 -- 0.5%
                        END as estimated_traffic
                    FROM serp_results s
                    JOIN keywords k ON s.keyword_id = k.id
                    WHERE s.keyword_id = ANY($1::uuid[])
                        AND s.search_date >= $2
                        AND s.search_date <= $3
                        AND s.serp_type = $4
                        AND s.position <= 20  -- Top 20 only
                ),
                company_aggregates AS (
                    SELECT 
                        -- ROBUST: Use domain_company_mapping for consistent company identification
                        dcm.company_id,
                        dcm.display_name as company_name,
                        dcm.enrichment_source,
                        dcm.confidence_score,
                        MIN(ls.domain) as primary_domain,
                        COUNT(DISTINCT ls.domain) as domain_count,
                        COUNT(DISTINCT ls.keyword_id) as total_keywords,
                        COUNT(DISTINCT ls.url) as total_pages,
                        SUM(ls.estimated_traffic) as total_traffic,
                        AVG(ls.position) as avg_position,
                        -- CORRECTED: Personal Relevance from actual persona scores
                        COALESCE(
                            (SELECT AVG(CAST(oda.score AS FLOAT))
                             FROM optimized_content_analysis oca
                             JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
                             JOIN scraped_content sc ON oca.url = sc.url
                             WHERE sc.domain = ANY(
                                 SELECT original_domain FROM domain_company_mapping 
                                 WHERE company_id = dcm.company_id
                             )
                             AND oda.dimension_type = 'persona'
                            ), 5.0  -- Default persona score (1-10 scale)
                        ) as personal_relevance,
                        AVG(CASE 
                            WHEN ca.overall_sentiment = 'positive' THEN 1.0
                            WHEN ca.overall_sentiment = 'neutral' THEN 0.7
                            WHEN ca.overall_sentiment = 'negative' THEN 0.3
                            WHEN ca.id IS NOT NULL THEN 0.6
                            ELSE 0.4
                        END) as avg_funnel_value
                    FROM landscape_serp ls
                    -- ROBUST: Use domain_company_mapping for all domain variations
                    INNER JOIN domain_company_mapping dcm ON ls.domain = dcm.original_domain
                    LEFT JOIN optimized_content_analysis ca ON ls.url = ca.url
                    GROUP BY 
                        dcm.company_id,
                        dcm.display_name,
                        dcm.enrichment_source,
                        dcm.confidence_score
                ),
                market_totals AS (
                    SELECT 
                        (SELECT COUNT(*) FROM landscape_keywords WHERE landscape_id = $5) as market_keywords,
                        SUM(ca.total_traffic) as market_traffic,
                        COUNT(DISTINCT ca.company_id) as total_companies
                    FROM company_aggregates ca
                )
                SELECT 
                    ca.*,
                    -- USER'S DSI FORMULA COMPONENTS
                    (ca.total_keywords::float / NULLIF(mt.market_keywords, 0)) * 100 as keyword_coverage_pct,
                    (ca.total_traffic / NULLIF(mt.market_traffic, 0)) * 100 as traffic_share_pct,
                    (ca.personal_relevance / 10.0) as personal_relevance_score,
                    -- USER'S DSI FORMULA: Keyword Coverage × Share of Traffic × Personal Relevance
                    (
                        (ca.total_keywords::float / NULLIF(mt.market_keywords, 0)) * 100 *
                        (ca.total_traffic / NULLIF(mt.market_traffic, 0)) * 100 *
                        (ca.personal_relevance / 10.0)
                    )::numeric(10,2) as dsi_score,
                    mt.total_companies
                FROM company_aggregates ca
                CROSS JOIN market_totals mt
                WHERE ca.total_keywords >= 3  -- Minimum keywords for inclusion
                ORDER BY dsi_score DESC NULLS LAST
            """
            
            results = await conn.fetch(
                company_query, 
                keyword_ids, 
                period_start, 
                calculation_date,
                search_type,
                landscape_id  # Add landscape_id as $5
            )
            
            company_metrics = []
            for idx, row in enumerate(results):
                # Use company_id from domain_company_mapping (always present)
                company_id = row['company_id']
                
                # Don't skip companies with NULL DSI scores, assign them 0
                dsi_score = float(row['dsi_score'] or 0)
                if dsi_score >= 30:
                    market_position = "leader"
                elif dsi_score >= 15:
                    market_position = "challenger"
                elif dsi_score >= 5:
                    market_position = "competitor"
                else:
                    market_position = "niche"
                
                company_metric = CompanyDSIMetrics(
                    company_id=UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id,
                    domain=row['primary_domain'],
                    company_name=row['company_name'],
                    total_keywords=row['total_keywords'],
                    total_pages=row['total_pages'],
                    keyword_coverage=float(row['keyword_coverage_pct'] or 0),
                    total_traffic=float(row['total_traffic'] or 0),
                    traffic_share=float(row['traffic_share_pct'] or 0),
                    avg_relevance=float(row['personal_relevance_score'] or 0),
                    avg_funnel_value=float(row['avg_funnel_value'] or 0),
                    dsi_score=dsi_score,
                    market_position=market_position,
                    rank_in_market=idx + 1,
                    total_companies_in_market=row['total_companies'] or 0
                )
                
                company_metrics.append(company_metric)
            
            return company_metrics
    
    async def _get_landscape_details(self, landscape_id: str) -> Optional[Dict[str, Any]]:
        """Get landscape details"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, name, description, is_active
                FROM digital_landscapes
                WHERE id = $1 AND is_active = true
            """, landscape_id)
            return dict(row) if row else None
    
    async def _get_landscape_keyword_ids(self, landscape_id: str) -> List[str]:
        """Get keyword IDs for a landscape"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT k.id
                FROM landscape_keywords lk
                JOIN keywords k ON lk.keyword_id = k.id
                WHERE lk.landscape_id = $1
                ORDER BY k.keyword
            """, landscape_id)
            return [str(row['id']) for row in rows]
    
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
                    landscape_id, calculation_date, EntityType.COMPANY.value, str(company.company_id),
                    company.company_name, company.domain, company.total_keywords,
                    company.total_pages, company.keyword_coverage, int(company.total_traffic),
                    company.traffic_share, company.avg_relevance, company.avg_funnel_value,
                    company.dsi_score, company.rank_in_market, company.total_companies_in_market,
                    company.market_position
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
                    landscape_id, calculation_date, EntityType.PAGE.value, str(page.page_id),
                    getattr(page, 'title', ''), getattr(page, 'domain', ''), getattr(page, 'url', ''),
                    getattr(page, 'total_keywords', 0), 1, getattr(page, 'keyword_coverage', 0),
                    int(getattr(page, 'total_traffic', 0)), getattr(page, 'traffic_share', 0),
                    getattr(page, 'avg_relevance', 0), getattr(page, 'avg_funnel_value', 0),
                    getattr(page, 'dsi_score', 0), getattr(page, 'rank_in_market', 0),
                    getattr(page, 'total_pages_in_market', 1)
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
            "market_position": company_metric.market_position
        }
