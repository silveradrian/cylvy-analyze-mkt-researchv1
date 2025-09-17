"""
Simple DSI Calculator for Pipelines
"""
import json
from typing import Dict, List, Any
from loguru import logger
from app.core.database import DatabasePool
from app.core.config import Settings


class SimpleDSICalculator:
    """Simple DSI calculator based on available data"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
    
    async def calculate_dsi_for_pipeline(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """Calculate DSI scores based on SERP and content analysis data"""
        async with self.db.acquire() as conn:
            # Get company metrics from scraped content
            companies = await conn.fetch("""
                WITH company_data AS (
                    -- Get unique domains from scraped content
                    SELECT 
                        sc.domain as company_domain,
                        COUNT(DISTINCT sc.url) as page_count,
                        COUNT(DISTINCT oca.id) as analyzed_count,
                        AVG(
                            CASE 
                                WHEN oda.score IS NOT NULL THEN CAST(oda.score AS FLOAT)
                                ELSE 5.0  -- Default middle score
                            END
                        ) as avg_relevance
                    FROM scraped_content sc
                    LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url
                    LEFT JOIN optimized_dimension_analysis oda ON oda.analysis_id = oca.id
                    WHERE sc.pipeline_execution_id = $1
                        AND sc.domain IS NOT NULL
                        AND sc.domain != ''
                        AND sc.status = 'completed'
                    GROUP BY sc.domain
                ),
                serp_data AS (
                    -- Get SERP visibility data
                    SELECT 
                        sr.domain as company_domain,
                        COUNT(*) as serp_appearances,
                        AVG(sr.position) as avg_position,
                        COUNT(DISTINCT sr.keyword_id) as keyword_count
                    FROM serp_results sr
                    WHERE sr.pipeline_execution_id = $1
                        AND sr.domain IS NOT NULL
                        AND sr.domain != ''
                    GROUP BY sr.domain
                ),
                total_stats AS (
                    SELECT 
                        COUNT(DISTINCT keyword_id) as total_keywords,
                        COUNT(DISTINCT domain) as total_companies
                    FROM serp_results
                    WHERE pipeline_execution_id = $1
                )
                SELECT 
                    COALESCE(cd.company_domain, sd.company_domain) as company_domain,
                    COALESCE(cd.page_count, 0) as page_count,
                    COALESCE(cd.analyzed_count, 0) as analyzed_count,
                    COALESCE(cd.avg_relevance, 5.0) as avg_relevance,
                    COALESCE(sd.serp_appearances, 0) as serp_appearances,
                    COALESCE(sd.avg_position, 100.0) as avg_position,
                    COALESCE(sd.keyword_count, 0) as keyword_count,
                    ts.total_keywords,
                    ts.total_companies
                FROM company_data cd
                FULL OUTER JOIN serp_data sd ON cd.company_domain = sd.company_domain
                CROSS JOIN total_stats ts
                WHERE COALESCE(cd.company_domain, sd.company_domain) IS NOT NULL
                ORDER BY 
                    COALESCE(sd.keyword_count, 0) DESC,
                    COALESCE(cd.analyzed_count, 0) DESC
            """, pipeline_id)
            
            if not companies:
                logger.warning(f"No companies found for pipeline {pipeline_id}")
                return []
            
            # Calculate DSI scores
            scores = []
            for company in companies:
                # Keyword coverage (how many keywords they appear for)
                keyword_coverage = min(float(company['keyword_count']) / max(float(company['total_keywords']), 1), 1.0)
                
                # SERP position score (lower is better)
                position_score = max(0, 1 - (float(company['avg_position']) - 1) / 20)
                
                # Content relevance (normalized from 0-10 scale)
                content_relevance = float(company['avg_relevance']) / 10
                
                # Market presence (based on page count and SERP appearances)
                presence_score = min(
                    (float(company['page_count']) + float(company['serp_appearances'])) / 20,
                    1.0
                )
                
                # Calculate weighted DSI score
                dsi_score = (
                    keyword_coverage * 0.40 +      # 40% weight on keyword coverage
                    content_relevance * 0.30 +     # 30% weight on content relevance
                    presence_score * 0.20 +        # 20% weight on market presence
                    position_score * 0.10          # 10% weight on SERP position
                )
                
                score_data = {
                    'pipeline_execution_id': pipeline_id,
                    'company_domain': company['company_domain'],
                    'dsi_score': round(dsi_score, 4),
                    'keyword_overlap_score': round(keyword_coverage, 4),
                    'content_relevance_score': round(content_relevance, 4),
                    'market_presence_score': round(presence_score, 4),
                    'metadata': {
                        'keyword_count': company['keyword_count'],
                        'total_keywords': company['total_keywords'],
                        'avg_position': float(company['avg_position']),
                        'serp_appearances': company['serp_appearances'],
                        'page_count': company['page_count'],
                        'analyzed_count': company['analyzed_count'],
                        'serp_visibility_score': round(position_score, 4)
                    }
                }
                
                scores.append(score_data)
            
            # Store scores
            if scores:
                await self._store_scores(conn, scores)
            
            return scores
    
    async def _store_scores(self, conn, scores: List[Dict[str, Any]]):
        """Store DSI scores in database"""
        await conn.executemany("""
            INSERT INTO dsi_scores (
                pipeline_execution_id, company_domain, dsi_score,
                keyword_overlap_score, content_relevance_score,
                market_presence_score, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (pipeline_execution_id, company_domain) 
            DO UPDATE SET
                dsi_score = EXCLUDED.dsi_score,
                keyword_overlap_score = EXCLUDED.keyword_overlap_score,
                content_relevance_score = EXCLUDED.content_relevance_score,
                market_presence_score = EXCLUDED.market_presence_score,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """, [
            (
                s['pipeline_execution_id'],
                s['company_domain'],
                s['dsi_score'],
                s['keyword_overlap_score'],
                s['content_relevance_score'],
                s['market_presence_score'],
                json.dumps(s['metadata'])
            )
            for s in scores
        ])
        
        logger.info(f"Stored {len(scores)} DSI scores")
