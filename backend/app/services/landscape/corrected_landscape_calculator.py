"""
CORRECTED Production Landscape Calculator
Implements proper DSI formula: Keyword Coverage × Share of Traffic × Personal Relevance
Fixes domain matching and company aggregation issues
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
import hashlib

from app.core.database import db_pool
from app.models.dsi import CompanyDSIMetrics
from app.models.landscape import LandscapeCalculationResult, EntityType

logger = logging.getLogger(__name__)

class CorrectedLandscapeCalculator:
    """Client-agnostic landscape calculator with proper DSI formula"""
    
    def __init__(self, db=None):
        self.db = db or db_pool
    
    async def calculate_landscape_dsi(
        self, 
        landscape_id: str, 
        search_type: str = 'organic',
        pipeline_id: Optional[str] = None
    ) -> List[CompanyDSIMetrics]:
        """Calculate DSI with CORRECTED formula and aggregation"""
        
        calculation_date = datetime.utcnow()
        
        async with self.db.acquire() as conn:
            
            # Get landscape keywords
            keywords = await conn.fetch("""
                SELECT keyword_id FROM landscape_keywords WHERE landscape_id = $1
            """, landscape_id)
            
            if not keywords:
                logger.warning(f"No keywords found for landscape {landscape_id}")
                return []
            
            keyword_ids = [str(k['keyword_id']) for k in keywords]
            total_keywords = len(keyword_ids)
            
            logger.info(f"Calculating DSI for landscape {landscape_id} with {total_keywords} keywords")
            
            # CORRECTED DSI CALCULATION with proper formula
            company_query = """
                WITH landscape_serp AS (
                    SELECT 
                        sr.domain as original_domain,
                        sr.keyword_id,
                        sr.url,
                        sr.position,
                        sr.estimated_traffic,
                        k.keyword,
                        k.avg_monthly_searches as search_volume,
                        -- NORMALIZE domains for proper matching
                        LOWER(CASE 
                            WHEN sr.domain LIKE 'www.%' THEN SUBSTRING(sr.domain FROM 5)
                            ELSE sr.domain 
                        END) as normalized_domain
                    FROM serp_results sr
                    JOIN keywords k ON sr.keyword_id = k.id
                    WHERE sr.keyword_id = ANY($1::uuid[])
                    AND sr.serp_type = $2
                    AND sr.position <= 20  -- Top 20 only
                    {pipeline_filter}
                ),
                company_aggregation AS (
                    SELECT 
                        ls.normalized_domain,
                        ls.original_domain,
                        -- CORRECTED: Use parent company names when available
                        COALESCE(
                            cr.parent_company_name,  -- Parent company (best)
                            cp.company_name,         -- Enriched company name
                            INITCAP(REPLACE(REPLACE(ls.normalized_domain, '.com', ''), '.', ' '))  -- Clean domain fallback
                        ) as company_name,
                        COALESCE(cp.id, 
                            (md5(ls.normalized_domain || 'fallback'))::uuid  -- Deterministic UUID from domain
                        ) as company_id,
                        cp.source_type,
                        -- AGGREGATED METRICS (no duplicates)
                        COUNT(DISTINCT ls.keyword_id) as unique_keywords,
                        COUNT(DISTINCT ls.url) as unique_pages,
                        COUNT(*) as total_rankings,
                        SUM(COALESCE(ls.estimated_traffic, 0)) as total_traffic,
                        AVG(ls.position) as avg_position,
                        -- PERSONAL RELEVANCE: Sum of persona scores for company's content
                        COALESCE(
                            (SELECT AVG(CAST(oda.score AS FLOAT))
                             FROM optimized_content_analysis oca
                             JOIN optimized_dimension_analysis oda ON oca.id = oda.analysis_id
                             WHERE oca.url = ANY(array_agg(DISTINCT ls.url))
                             AND oda.dimension_type = 'persona'
                            ), 0.5  -- Default persona relevance if no analysis
                        ) as personal_relevance
                    FROM landscape_serp ls
                    -- FIXED: Join on normalized domains
                    LEFT JOIN company_profiles cp ON ls.normalized_domain = cp.domain
                    -- Join parent company relationships
                    LEFT JOIN company_relationships cr ON ls.original_domain = cr.subsidiary_domain
                    GROUP BY 
                        ls.normalized_domain, 
                        ls.original_domain,
                        cr.parent_company_name,
                        cp.company_name,
                        cp.id,
                        cp.source_type
                ),
                market_totals AS (
                    SELECT 
                        $3 as total_keywords,  -- Use parameter for total keywords
                        SUM(ca.total_traffic) as total_market_traffic,
                        COUNT(*) as total_companies
                    FROM company_aggregation ca
                ),
                final_dsi AS (
                    SELECT 
                        ca.*,
                        mt.total_keywords as market_keywords,
                        mt.total_market_traffic,
                        -- DSI COMPONENTS as specified by user
                        (ca.unique_keywords::float / mt.total_keywords::float) * 100 as keyword_coverage_pct,
                        CASE 
                            WHEN mt.total_market_traffic > 0 
                            THEN (ca.total_traffic / mt.total_market_traffic) * 100
                            ELSE (ca.unique_keywords::float / mt.total_keywords::float) * 
                                 (GREATEST(0, (21.0 - ca.avg_position)) / 20.0) * 100  -- Position-based traffic proxy
                        END as traffic_share_pct,
                        ca.personal_relevance as personal_relevance_score,
                        -- CORRECTED DSI FORMULA: Keyword Coverage × Share of Traffic × Personal Relevance
                        (
                            (ca.unique_keywords::float / mt.total_keywords::float) * 100 *
                            CASE 
                                WHEN mt.total_market_traffic > 0 
                                THEN (ca.total_traffic / mt.total_market_traffic) * 100
                                ELSE (ca.unique_keywords::float / mt.total_keywords::float) * 
                                     (GREATEST(0, (21.0 - ca.avg_position)) / 20.0) * 100
                            END *
                            ca.personal_relevance
                        )::numeric(10,2) as dsi_score
                    FROM company_aggregation ca
                    CROSS JOIN market_totals mt
                    WHERE ca.unique_keywords >= 3  -- Minimum keywords for inclusion
                )
                SELECT *
                FROM final_dsi
                ORDER BY dsi_score DESC
            """
            
            # Add pipeline filter if provided
            if pipeline_id:
                company_query = company_query.replace(
                    "{pipeline_filter}", 
                    f"AND sr.pipeline_execution_id = '{pipeline_id}'"
                )
            else:
                company_query = company_query.replace("{pipeline_filter}", "")
            
            results = await conn.fetch(
                company_query,
                keyword_ids,
                search_type, 
                total_keywords
            )
            
            # Convert to CompanyDSIMetrics objects
            company_metrics = []
            for idx, row in enumerate(results):
                
                # Market position based on DSI score
                dsi_score = float(row['dsi_score'] or 0)
                if dsi_score >= 50:
                    market_position = "leader"
                elif dsi_score >= 25:
                    market_position = "challenger" 
                elif dsi_score >= 10:
                    market_position = "competitor"
                else:
                    market_position = "niche"
                
                company_metric = CompanyDSIMetrics(
                    company_id=row['company_id'],
                    domain=row['original_domain'],  # Use original domain
                    company_name=row['company_name'],
                    total_keywords=row['unique_keywords'],
                    total_pages=row['unique_pages'],
                    keyword_coverage=float(row['keyword_coverage_pct'] or 0),
                    total_traffic=float(row['total_traffic'] or 0),
                    traffic_share=float(row['traffic_share_pct'] or 0),
                    avg_relevance=float(row['personal_relevance_score'] or 0),
                    avg_funnel_value=0.5,  # Default funnel value
                    dsi_score=dsi_score,
                    market_position=market_position,
                    rank_in_market=idx + 1,
                    total_companies_in_market=len(results)
                )
                
                company_metrics.append(company_metric)
            
            logger.info(f"Calculated DSI for {len(company_metrics)} companies")
            return company_metrics

    async def test_calculation(self, landscape_id: str, pipeline_id: str):
        """Test the corrected DSI calculation"""
        
        print(f'🧪 Testing corrected DSI calculation...')
        
        try:
            results = await self.calculate_landscape_dsi(
                landscape_id=landscape_id,
                search_type='organic',
                pipeline_id=pipeline_id
            )
            
            print(f'✅ Calculated DSI for {len(results)} companies')
            
            # Show top 20 results
            print(f'\n📊 TOP 20 CORRECTED DSI RESULTS:')
            print(f'Rank Company Name                   Domain                    DSI    Kwd%  Traffic%  Persona')
            print('-' * 100)
            
            major_companies_found = 0
            
            for i, company in enumerate(results[:20], 1):
                name = company.company_name[:30]
                domain = company.domain[:25]
                dsi = company.dsi_score
                kw_cov = company.keyword_coverage
                traffic = company.traffic_share
                persona = company.avg_relevance
                
                # Check if major company
                if any(major in name.lower() for major in ['finastra', 'gartner', 'oracle', 'ibm', 'fiserv', 'jpmorgan']):
                    major_companies_found += 1
                    icon = '🎯'
                else:
                    icon = '  '
                
                print(f'{i:4} {icon} {name:30} {domain:25} {dsi:6.2f} {kw_cov:5.1f} {traffic:8.2f} {persona:7.2f}')
            
            print(f'\n📈 CORRECTED CALCULATION RESULTS:')
            print(f'   🎯 Major companies in top 20: {major_companies_found}/20')
            print(f'   📊 Total companies calculated: {len(results)}')
            print(f'   🔝 Highest DSI score: {results[0].dsi_score:.2f}')
            
            if major_companies_found > 0:
                print(f'   ✅ SUCCESS! Major companies now appearing with corrected formula')
            else:
                print(f'   ❌ STILL BROKEN: Need to investigate SQL query further')
                
            return results
            
        except Exception as e:
            print(f'❌ Calculation failed: {e}')
            return []
