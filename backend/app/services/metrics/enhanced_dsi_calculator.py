"""
Enhanced DSI Calculator with Different Formulas for Content Types
"""
import json
from typing import Dict, List, Any, Optional
from loguru import logger
from app.core.database import DatabasePool
from app.core.config import Settings


class EnhancedDSICalculator:
    """Enhanced DSI calculator with different formulas for organic vs news/video"""
    
    def __init__(self, settings: Settings, db: DatabasePool):
        self.settings = settings
        self.db = db
    
    async def calculate_dsi_for_pipeline(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """Calculate DSI scores with different formulas based on content type"""
        async with self.db.acquire() as conn:
            # Get organic company data with traffic estimates
            organic_scores = await self._calculate_organic_dsi(conn, pipeline_id)
            
            # Get news/video scores with simple calculation
            news_video_scores = await self._calculate_news_video_dsi(conn, pipeline_id)
            
            # Combine all scores
            all_scores = organic_scores + news_video_scores
            
            # Store scores
            if all_scores:
                await self._store_scores(conn, all_scores)
            
            return all_scores
    
    async def _calculate_organic_dsi(self, conn, pipeline_id: str) -> List[Dict[str, Any]]:
        """
        Calculate DSI for organic results using original formula:
        DSI = Keyword Coverage × Share of Est Traffic × Content Relevance (sum of persona scores)
        """
        # Get organic company data with traffic and persona scores
        companies = await conn.fetch("""
            WITH keyword_data AS (
                -- Get all keywords and their total traffic
                SELECT DISTINCT 
                    k.id as keyword_id,
                    k.keyword,
                    COALESCE(hkm.avg_monthly_searches, 1000) as search_volume
                FROM serp_results sr
                JOIN keywords k ON sr.keyword_id = k.id
                LEFT JOIN historical_keyword_metrics hkm ON k.id = hkm.keyword_id
                WHERE sr.pipeline_execution_id = $1
            ),
            total_traffic AS (
                -- Calculate total traffic across all keywords
                SELECT SUM(search_volume) as total_volume
                FROM keyword_data
            ),
            company_serp AS (
                -- Get company SERP performance
                SELECT 
                    sr.domain as company_domain,
                    sr.keyword_id,
                    sr.position,
                    kd.search_volume,
                    -- Estimate click share based on position (simplified CTR curve)
                    CASE 
                        WHEN sr.position = 1 THEN 0.30
                        WHEN sr.position = 2 THEN 0.15
                        WHEN sr.position = 3 THEN 0.10
                        WHEN sr.position <= 5 THEN 0.07
                        WHEN sr.position <= 10 THEN 0.03
                        ELSE 0.01
                    END as estimated_ctr
                FROM serp_results sr
                JOIN keyword_data kd ON sr.keyword_id = kd.keyword_id
                WHERE sr.pipeline_execution_id = $1
                    AND sr.serp_type = 'organic'
                    AND sr.domain IS NOT NULL
                    AND sr.domain != ''
            ),
            company_metrics AS (
                -- Aggregate by company
                SELECT 
                    company_domain,
                    COUNT(DISTINCT keyword_id) as keyword_count,
                    SUM(search_volume * estimated_ctr) as estimated_traffic,
                    AVG(position) as avg_position
                FROM company_serp
                GROUP BY company_domain
            ),
            content_analysis AS (
                -- Get persona scores for content relevance
                SELECT 
                    sc.domain as company_domain,
                    COUNT(DISTINCT oca.id) as analyzed_pages,
                    -- Sum of persona scores as content relevance
                    COALESCE(AVG(
                        COALESCE(
                            (SELECT SUM(CAST(score AS FLOAT)) 
                             FROM optimized_dimension_analysis 
                             WHERE analysis_id = oca.id 
                               AND dimension_type = 'persona'
                            ), 0
                        )
                    ), 0) as persona_score_sum
                FROM scraped_content sc
                JOIN optimized_content_analysis oca ON oca.url = sc.url
                WHERE sc.pipeline_execution_id = $1
                    AND sc.domain IS NOT NULL
                GROUP BY sc.domain
            ),
            keyword_totals AS (
                SELECT COUNT(DISTINCT keyword_id) as total_keywords
                FROM keyword_data
            )
            SELECT 
                cm.company_domain,
                cm.keyword_count,
                kt.total_keywords,
                cm.estimated_traffic,
                tt.total_volume as total_traffic,
                cm.avg_position,
                COALESCE(ca.analyzed_pages, 0) as analyzed_pages,
                COALESCE(ca.persona_score_sum, 0) as persona_score_sum,
                -- Calculate components
                cm.keyword_count::float / kt.total_keywords as keyword_coverage,
                cm.estimated_traffic / GREATEST(tt.total_volume, 1) as traffic_share,
                -- Normalize persona scores (assuming max 30 = 3 personas × 10 max score)
                COALESCE(ca.persona_score_sum, 0) / 30.0 as content_relevance
            FROM company_metrics cm
            CROSS JOIN keyword_totals kt
            CROSS JOIN total_traffic tt
            LEFT JOIN content_analysis ca ON cm.company_domain = ca.company_domain
            WHERE cm.company_domain IS NOT NULL
            ORDER BY cm.estimated_traffic DESC
        """, pipeline_id)
        
        scores = []
        for company in companies:
            # Original DSI formula for organic
            keyword_coverage = float(company['keyword_coverage'])
            traffic_share = float(company['traffic_share'])
            content_relevance = float(company['content_relevance'])
            
            # DSI = Keyword Coverage × Share of Est Traffic × Content Relevance
            dsi_score = keyword_coverage * traffic_share * content_relevance
            
            # Boost the score to make it more meaningful (since multiplying 3 small numbers)
            # Apply square root to make distribution less extreme
            dsi_score = min(dsi_score ** 0.5, 1.0)
            
            score_data = {
                'pipeline_execution_id': pipeline_id,
                'company_domain': company['company_domain'],
                'content_type': 'organic',
                'dsi_score': round(dsi_score, 4),
                'keyword_overlap_score': round(keyword_coverage, 4),
                'traffic_share_score': round(traffic_share, 4),
                'content_relevance_score': round(content_relevance, 4),
                'market_presence_score': 0,  # Not used in organic formula
                'metadata': {
                    'formula': 'original',
                    'keyword_count': int(company['keyword_count']),
                    'total_keywords': int(company['total_keywords']),
                    'estimated_traffic': float(company['estimated_traffic']),
                    'total_traffic': float(company['total_traffic']),
                    'avg_position': float(company['avg_position']),
                    'analyzed_pages': int(company['analyzed_pages']),
                    'persona_score_sum': float(company['persona_score_sum'])
                }
            }
            
            scores.append(score_data)
        
        return scores
    
    async def _calculate_news_video_dsi(self, conn, pipeline_id: str) -> List[Dict[str, Any]]:
        """
        Calculate DSI for news and video using simple formula
        """
        # Get news and video company data
        companies = await conn.fetch("""
            WITH company_data AS (
                SELECT 
                    sr.domain as company_domain,
                    sr.serp_type as content_type,
                    COUNT(*) as appearances,
                    AVG(sr.position) as avg_position,
                    COUNT(DISTINCT sr.keyword_id) as keyword_count
                FROM serp_results sr
                WHERE sr.pipeline_execution_id = $1
                    AND sr.serp_type IN ('news', 'video')
                    AND sr.domain IS NOT NULL
                    AND sr.domain != ''
                GROUP BY sr.domain, sr.serp_type
            ),
            content_analysis AS (
                SELECT 
                    sc.domain as company_domain,
                    COUNT(DISTINCT oca.id) as analyzed_count,
                    AVG(
                        CASE 
                            WHEN oda.score IS NOT NULL THEN CAST(oda.score AS FLOAT)
                            ELSE 5.0
                        END
                    ) as avg_relevance
                FROM scraped_content sc
                LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url
                LEFT JOIN optimized_dimension_analysis oda ON oda.analysis_id = oca.id
                WHERE sc.pipeline_execution_id = $1
                    AND sc.domain IS NOT NULL
                GROUP BY sc.domain
            ),
            total_stats AS (
                SELECT 
                    COUNT(DISTINCT keyword_id) as total_keywords,
                    serp_type as content_type
                FROM serp_results
                WHERE pipeline_execution_id = $1
                    AND serp_type IN ('news', 'video')
                GROUP BY serp_type
            )
            SELECT 
                cd.company_domain,
                cd.content_type,
                cd.appearances,
                cd.avg_position,
                cd.keyword_count,
                ts.total_keywords,
                COALESCE(ca.analyzed_count, 0) as analyzed_count,
                COALESCE(ca.avg_relevance, 5.0) as avg_relevance
            FROM company_data cd
            JOIN total_stats ts ON cd.content_type = ts.content_type
            LEFT JOIN content_analysis ca ON cd.company_domain = ca.company_domain
            ORDER BY cd.appearances DESC
        """, pipeline_id)
        
        scores = []
        for company in companies:
            # Simple formula for news/video
            keyword_coverage = min(float(company['keyword_count']) / max(float(company['total_keywords']), 1), 1.0)
            position_score = max(0, 1 - (float(company['avg_position']) - 1) / 20)
            content_relevance = float(company['avg_relevance']) / 10
            presence_score = min(float(company['appearances']) / 20, 1.0)
            
            # Simple weighted average
            dsi_score = (
                keyword_coverage * 0.40 +
                content_relevance * 0.30 +
                presence_score * 0.20 +
                position_score * 0.10
            )
            
            score_data = {
                'pipeline_execution_id': pipeline_id,
                'company_domain': company['company_domain'],
                'content_type': company['content_type'],
                'dsi_score': round(dsi_score, 4),
                'keyword_overlap_score': round(keyword_coverage, 4),
                'traffic_share_score': 0,  # Not used in simple formula
                'content_relevance_score': round(content_relevance, 4),
                'market_presence_score': round(presence_score, 4),
                'metadata': {
                    'formula': 'simple',
                    'keyword_count': int(company['keyword_count']),
                    'total_keywords': int(company['total_keywords']),
                    'avg_position': float(company['avg_position']),
                    'appearances': int(company['appearances']),
                    'analyzed_count': int(company['analyzed_count']),
                    'serp_visibility_score': round(position_score, 4)
                }
            }
            
            scores.append(score_data)
        
        return scores
    
    async def _store_scores(self, conn, scores: List[Dict[str, Any]]):
        """Store DSI scores in database with content type"""
        # First, clear existing scores for this pipeline
        pipeline_id = scores[0]['pipeline_execution_id'] if scores else None
        if pipeline_id:
            await conn.execute("""
                DELETE FROM dsi_scores 
                WHERE pipeline_execution_id = $1
            """, pipeline_id)
        
        # Insert new scores
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
        
        # Log summary by content type
        organic_count = sum(1 for s in scores if s['content_type'] == 'organic')
        news_count = sum(1 for s in scores if s['content_type'] == 'news')
        video_count = sum(1 for s in scores if s['content_type'] == 'video')
        
        logger.info(f"Stored {len(scores)} DSI scores: "
                   f"{organic_count} organic (original formula), "
                   f"{news_count} news (simple formula), "
                   f"{video_count} video (simple formula)")
