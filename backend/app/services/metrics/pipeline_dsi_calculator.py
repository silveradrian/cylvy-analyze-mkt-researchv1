"""
Pipeline DSI Calculator
Calculates Digital Saturation Index scores for completed pipelines
"""
import asyncio
from typing import Dict, List, Optional, Any
from uuid import UUID
from loguru import logger
from app.core.database import DatabasePool
from app.core.config import Settings


class PipelineDSICalculator:
    """Calculate DSI scores for pipeline results"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
    
    async def calculate_pipeline_dsi(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """Calculate DSI scores for all companies in a pipeline"""
        async with self.db.acquire() as conn:
            # Get all companies found in the pipeline
            companies = await conn.fetch("""
                WITH company_data AS (
                    -- Get companies from SERP results
                    SELECT DISTINCT 
                        sr.domain as company_domain,
                        sr.url,
                        sr.position,
                        sr.title,
                        sr.snippet,
                        k.keyword
                    FROM serp_results sr
                    JOIN keywords k ON sr.keyword_id = k.id
                    WHERE sr.pipeline_execution_id = $1
                        AND sr.domain IS NOT NULL
                ),
                company_metrics AS (
                    SELECT 
                        company_domain,
                        COUNT(DISTINCT keyword) as keyword_count,
                        AVG(position) as avg_position,
                        COUNT(*) as total_appearances
                    FROM company_data
                    GROUP BY company_domain
                ),
                content_analysis AS (
                    SELECT 
                        sc.domain as company_domain,
                        COUNT(DISTINCT oca.id) as analyzed_pages,
                        AVG(CAST(oda.score AS FLOAT)) as avg_relevance_score
                    FROM scraped_content sc
                    JOIN optimized_content_analysis oca ON oca.url = sc.url
                    LEFT JOIN optimized_dimension_analysis oda ON oda.analysis_id = oca.id
                    WHERE sc.pipeline_execution_id = $1
                        AND sc.domain IS NOT NULL
                    GROUP BY sc.domain
                ),
                total_keywords AS (
                    SELECT COUNT(DISTINCT keyword) as total
                    FROM serp_results sr
                    WHERE sr.pipeline_execution_id = $1
                )
                SELECT 
                    cm.company_domain,
                    cm.keyword_count,
                    cm.avg_position,
                    cm.total_appearances,
                    COALESCE(ca.analyzed_pages, 0) as analyzed_pages,
                    COALESCE(ca.avg_relevance_score, 0) as avg_relevance_score,
                    tk.total as total_keywords
                FROM company_metrics cm
                LEFT JOIN content_analysis ca ON cm.company_domain = ca.company_domain
                CROSS JOIN total_keywords tk
                WHERE cm.company_domain IS NOT NULL
                ORDER BY cm.keyword_count DESC, cm.avg_position ASC
            """, pipeline_id)
            
            if not companies:
                logger.warning(f"No companies found for pipeline {pipeline_id}")
                return []
            
            # Calculate DSI scores
            scores = []
            for company in companies:
                # Calculate component scores
                keyword_overlap = min(company['keyword_count'] / max(company['total_keywords'], 1), 1.0)
                
                # Position score (lower position = higher score)
                position_score = max(0, 1 - (company['avg_position'] - 1) / 10)
                
                # Content relevance from analysis
                content_relevance = company['avg_relevance_score'] / 10 if company['avg_relevance_score'] else 0
                
                # Market presence based on appearances and analyzed pages
                presence_score = min(
                    (company['total_appearances'] + company['analyzed_pages']) / 50,
                    1.0
                )
                
                # Calculate weighted DSI score
                dsi_score = (
                    keyword_overlap * 0.35 +      # 35% weight on keyword coverage
                    content_relevance * 0.30 +    # 30% weight on content relevance
                    presence_score * 0.20 +       # 20% weight on market presence
                    position_score * 0.15         # 15% weight on SERP position
                )
                
                score_data = {
                    'pipeline_execution_id': pipeline_id,
                    'company_domain': company['company_domain'],
                    'dsi_score': round(dsi_score, 4),
                    'keyword_overlap_score': round(keyword_overlap, 4),
                    'content_relevance_score': round(content_relevance, 4),
                    'market_presence_score': round(presence_score, 4),
                    'metadata': {
                        'keyword_count': company['keyword_count'],
                        'total_keywords': company['total_keywords'],
                        'avg_position': float(company['avg_position']),
                        'total_appearances': company['total_appearances'],
                        'analyzed_pages': company['analyzed_pages'],
                        'serp_visibility_score': round(position_score, 4)
                    }
                }
                
                scores.append(score_data)
            
            # Store scores in database
            if scores:
                await self._store_dsi_scores(conn, scores)
            
            return scores
    
    async def _store_dsi_scores(self, conn, scores: List[Dict[str, Any]]):
        """Store DSI scores in the database"""
        try:
            # Insert scores
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
                    score['pipeline_execution_id'],
                    score['company_domain'],
                    score['dsi_score'],
                    score['keyword_overlap_score'],
                    score['content_relevance_score'],
                    score['market_presence_score'],
                    score['metadata']
                )
                for score in scores
            ])
            
            logger.info(f"Stored {len(scores)} DSI scores")
            
        except Exception as e:
            logger.error(f"Failed to store DSI scores: {e}")
            raise
