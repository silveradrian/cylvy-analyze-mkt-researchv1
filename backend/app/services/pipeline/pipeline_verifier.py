"""
Pipeline Verification Service
Verifies completeness of pipeline data and identifies missing fields
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from uuid import UUID
from loguru import logger
from app.core.database import DatabasePool


class PipelineVerifier:
    """Verifies pipeline data completeness and quality"""
    
    def __init__(self, db: DatabasePool):
        self.db = db
    
    async def verify_pipeline_completeness(self, pipeline_id: str) -> Dict[str, Any]:
        """Comprehensive verification of pipeline data completeness"""
        async with self.db.acquire() as conn:
            verification_result = {
                'pipeline_id': pipeline_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'overall_status': 'complete',
                'phases': {},
                'issues': [],
                'warnings': [],
                'recommendations': []
            }
            
            # 1. Check pipeline execution status
            pipeline = await conn.fetchrow("""
                SELECT *, 
                       EXTRACT(EPOCH FROM (NOW() - created_at))/3600 as hours_elapsed
                FROM pipeline_executions 
                WHERE id = $1
            """, pipeline_id)
            
            if not pipeline:
                verification_result['overall_status'] = 'failed'
                verification_result['issues'].append('Pipeline not found')
                return verification_result
            
            # 2. Verify each phase
            phase_verifications = {
                'keyword_metrics': self._verify_keyword_metrics,
                'serp_collection': self._verify_serp_collection,
                'company_enrichment': self._verify_company_enrichment,
                'video_enrichment': self._verify_video_enrichment,
                'content_scraping': self._verify_content_scraping,
                'content_analysis': self._verify_content_analysis,
                'dsi_calculation': self._verify_dsi_calculation
            }
            
            for phase_name, verify_func in phase_verifications.items():
                phase_result = await verify_func(conn, pipeline_id)
                verification_result['phases'][phase_name] = phase_result
                
                if phase_result['status'] == 'failed':
                    verification_result['overall_status'] = 'incomplete'
                    verification_result['issues'].extend(phase_result.get('issues', []))
                elif phase_result['status'] == 'warning':
                    verification_result['warnings'].extend(phase_result.get('warnings', []))
            
            # 3. Check pipeline timing
            if pipeline['hours_elapsed'] > 24:
                verification_result['warnings'].append(
                    f"Pipeline took {pipeline['hours_elapsed']:.1f} hours to complete"
                )
            
            # 4. Generate recommendations
            verification_result['recommendations'] = await self._generate_recommendations(
                conn, pipeline_id, verification_result
            )
            
            # 5. Store verification results
            await self._store_verification(conn, verification_result)
            
            return verification_result
    
    async def _verify_keyword_metrics(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Verify keyword metrics phase"""
        result = await conn.fetchrow("""
            SELECT COUNT(DISTINCT k.id) as keyword_count,
                   COUNT(DISTINCT kc.country_code) as country_count,
                   COUNT(hkm.id) as metrics_count
            FROM keywords k
            LEFT JOIN keywords_countries kc ON k.id = kc.keyword_id
            LEFT JOIN historical_keyword_metrics hkm ON k.id = hkm.keyword_id
            WHERE EXISTS (
                SELECT 1 FROM serp_results sr 
                WHERE sr.keyword_id = k.id 
                AND sr.pipeline_execution_id = $1
            )
        """, pipeline_id)
        
        phase_result = {
            'status': 'complete',
            'metrics': {
                'keywords': result['keyword_count'],
                'countries': result['country_count'],
                'historical_metrics': result['metrics_count']
            }
        }
        
        if result['keyword_count'] == 0:
            phase_result['status'] = 'failed'
            phase_result['issues'] = ['No keywords found']
        elif result['metrics_count'] < result['keyword_count']:
            phase_result['status'] = 'warning'
            phase_result['warnings'] = [
                f"Only {result['metrics_count']} of {result['keyword_count']} keywords have metrics"
            ]
        
        return phase_result
    
    async def _verify_serp_collection(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Verify SERP collection phase"""
        result = await conn.fetchrow("""
            SELECT COUNT(*) as total_results,
                   COUNT(DISTINCT keyword_id) as keywords_with_results,
                   COUNT(DISTINCT domain) as unique_domains,
                   AVG(position) as avg_position,
                   COUNT(CASE WHEN serp_type = 'organic' THEN 1 END) as organic_results,
                   COUNT(CASE WHEN serp_type = 'news' THEN 1 END) as news_results,
                   COUNT(CASE WHEN serp_type = 'video' THEN 1 END) as video_results
            FROM serp_results
            WHERE pipeline_execution_id = $1
        """, pipeline_id)
        
        phase_result = {
            'status': 'complete',
            'metrics': {
                'total_results': result['total_results'],
                'keywords_with_results': result['keywords_with_results'],
                'unique_domains': result['unique_domains'],
                'avg_position': float(result['avg_position']) if result['avg_position'] else 0,
                'organic': result['organic_results'],
                'news': result['news_results'],
                'video': result['video_results']
            }
        }
        
        if result['total_results'] == 0:
            phase_result['status'] = 'failed'
            phase_result['issues'] = ['No SERP results collected']
        elif result['unique_domains'] < 10:
            phase_result['status'] = 'warning'
            phase_result['warnings'] = [
                f"Only {result['unique_domains']} unique domains found"
            ]
        
        return phase_result
    
    async def _verify_company_enrichment(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Verify company enrichment phase"""
        # Since enriched_companies table doesn't exist, check domain data
        result = await conn.fetchrow("""
            SELECT COUNT(DISTINCT domain) as domains_with_data
            FROM serp_results
            WHERE pipeline_execution_id = $1
                AND domain IS NOT NULL
                AND domain != ''
        """, pipeline_id)
        
        return {
            'status': 'complete',
            'metrics': {
                'enriched_domains': result['domains_with_data']
            }
        }
    
    async def _verify_video_enrichment(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Verify video enrichment phase"""
        # First check if youtube_channels table exists and has the column
        has_youtube_table = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'youtube_channels' 
                AND column_name = 'pipeline_execution_id'
            )
        """)
        
        if has_youtube_table:
            result = await conn.fetchrow("""
                SELECT 
                    (SELECT COUNT(*) FROM serp_results 
                     WHERE pipeline_execution_id = $1 AND serp_type = 'video') as video_count,
                    COUNT(DISTINCT yc.channel_id) as channel_count,
                    COUNT(CASE WHEN yc.company_domain IS NOT NULL THEN 1 END) as resolved_channels
                FROM youtube_channels yc
                WHERE yc.pipeline_execution_id = $1
            """, pipeline_id)
        else:
            # Fallback for missing table/column
            video_count = await conn.fetchval("""
                SELECT COUNT(*) FROM serp_results 
                WHERE pipeline_execution_id = $1 AND serp_type = 'video'
            """, pipeline_id)
            
            result = {
                'video_count': video_count,
                'channel_count': 0,
                'resolved_channels': 0
            }
        
        phase_result = {
            'status': 'complete',
            'metrics': {
                'video_results': result['video_count'],
                'youtube_channels': result['channel_count'],
                'resolved_channels': result['resolved_channels']
            }
        }
        
        if result['video_count'] > 0 and result['channel_count'] == 0:
            phase_result['status'] = 'warning'
            phase_result['warnings'] = ['Video results found but no YouTube channels extracted']
        
        return phase_result
    
    async def _verify_content_scraping(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Verify content scraping phase"""
        result = await conn.fetchrow("""
            SELECT COUNT(*) as total_urls,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful,
                   COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                   COUNT(CASE WHEN content IS NOT NULL AND LENGTH(content) > 100 THEN 1 END) as with_content,
                   AVG(CASE WHEN content IS NOT NULL THEN LENGTH(content) ELSE 0 END) as avg_content_length
            FROM scraped_content
            WHERE pipeline_execution_id = $1
        """, pipeline_id)
        
        phase_result = {
            'status': 'complete',
            'metrics': {
                'total_urls': result['total_urls'],
                'successful': result['successful'],
                'failed': result['failed'],
                'with_content': result['with_content'],
                'avg_content_length': float(result['avg_content_length']) if result['avg_content_length'] else 0,
                'success_rate': result['successful'] / result['total_urls'] if result['total_urls'] > 0 else 0
            }
        }
        
        if result['total_urls'] == 0:
            phase_result['status'] = 'failed'
            phase_result['issues'] = ['No content scraping attempted']
        elif phase_result['metrics']['success_rate'] < 0.5:
            phase_result['status'] = 'warning'
            phase_result['warnings'] = [
                f"Low scraping success rate: {phase_result['metrics']['success_rate']:.1%}"
            ]
        
        return phase_result
    
    async def _verify_content_analysis(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Verify content analysis phase"""
        result = await conn.fetchrow("""
            WITH analysis_data AS (
                SELECT oca.id, oca.url,
                       COUNT(DISTINCT oda.dimension_name) as dimensions_analyzed,
                       AVG(CAST(oda.score AS FLOAT)) as avg_score
                FROM scraped_content sc
                JOIN optimized_content_analysis oca ON oca.url = sc.url
                LEFT JOIN optimized_dimension_analysis oda ON oda.analysis_id = oca.id
                WHERE sc.pipeline_execution_id = $1
                GROUP BY oca.id, oca.url
            )
            SELECT COUNT(*) as analyzed_count,
                   AVG(dimensions_analyzed) as avg_dimensions,
                   AVG(avg_score) as overall_avg_score,
                   MIN(dimensions_analyzed) as min_dimensions,
                   MAX(dimensions_analyzed) as max_dimensions
            FROM analysis_data
        """, pipeline_id)
        
        # Get ready but unanalyzed content
        pending = await conn.fetchval("""
            SELECT COUNT(*)
            FROM scraped_content sc
            WHERE sc.pipeline_execution_id = $1
                AND sc.status = 'completed'
                AND sc.content IS NOT NULL
                AND LENGTH(sc.content) > 100
                AND NOT EXISTS (
                    SELECT 1 FROM optimized_content_analysis oca 
                    WHERE oca.url = sc.url
                )
        """, pipeline_id)
        
        phase_result = {
            'status': 'complete',
            'metrics': {
                'analyzed_pages': result['analyzed_count'] or 0,
                'pending_analysis': pending,
                'avg_dimensions_per_page': float(result['avg_dimensions']) if result['avg_dimensions'] else 0,
                'avg_relevance_score': float(result['overall_avg_score']) if result['overall_avg_score'] else 0
            }
        }
        
        if result['analyzed_count'] == 0:
            phase_result['status'] = 'failed'
            phase_result['issues'] = ['No content analysis performed']
        elif pending > 10:
            phase_result['status'] = 'warning'
            phase_result['warnings'] = [f"{pending} pages still pending analysis"]
        
        return phase_result
    
    async def _verify_dsi_calculation(self, conn, pipeline_id: str) -> Dict[str, Any]:
        """Verify DSI calculation phase"""
        result = await conn.fetchrow("""
            SELECT COUNT(*) as companies_scored,
                   AVG(dsi_score) as avg_dsi,
                   MAX(dsi_score) as max_dsi,
                   MIN(dsi_score) as min_dsi,
                   COUNT(CASE WHEN dsi_score >= 0.7 THEN 1 END) as high_scores,
                   COUNT(CASE WHEN dsi_score <= 0.3 THEN 1 END) as low_scores
            FROM dsi_scores
            WHERE pipeline_execution_id = $1
        """, pipeline_id)
        
        phase_result = {
            'status': 'complete',
            'metrics': {
                'companies_scored': result['companies_scored'] or 0,
                'avg_dsi': float(result['avg_dsi']) if result['avg_dsi'] else 0,
                'max_dsi': float(result['max_dsi']) if result['max_dsi'] else 0,
                'min_dsi': float(result['min_dsi']) if result['min_dsi'] else 0,
                'high_scores': result['high_scores'] or 0,
                'low_scores': result['low_scores'] or 0
            }
        }
        
        if result['companies_scored'] == 0:
            phase_result['status'] = 'failed'
            phase_result['issues'] = ['No DSI scores calculated']
        elif result['companies_scored'] < 10:
            phase_result['status'] = 'warning'
            phase_result['warnings'] = [f"Only {result['companies_scored']} companies scored"]
        
        return phase_result
    
    async def _generate_recommendations(self, conn, pipeline_id: str, verification: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on verification results"""
        recommendations = []
        
        # Check for low scraping success
        scraping = verification['phases'].get('content_scraping', {})
        if scraping.get('metrics', {}).get('success_rate', 1) < 0.7:
            recommendations.append("Consider implementing retry logic for failed scrapes")
        
        # Check for incomplete analysis
        analysis = verification['phases'].get('content_analysis', {})
        if analysis.get('metrics', {}).get('pending_analysis', 0) > 0:
            recommendations.append("Resume content analysis to process remaining pages")
        
        # Check for missing DSI
        dsi = verification['phases'].get('dsi_calculation', {})
        if dsi.get('status') == 'failed':
            recommendations.append("Run DSI calculation to generate market intelligence scores")
        
        # Check for data quality
        if verification['overall_status'] != 'complete':
            recommendations.append("Review failed phases and re-run with improved error handling")
        
        return recommendations
    
    async def _store_verification(self, conn, verification: Dict[str, Any]):
        """Store verification results for historical tracking"""
        try:
            await conn.execute("""
                INSERT INTO pipeline_verifications (
                    pipeline_id, verification_time, overall_status,
                    phase_results, issues, warnings, recommendations
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, 
                verification['pipeline_id'],
                verification['timestamp'],
                verification['overall_status'],
                verification['phases'],
                verification['issues'],
                verification['warnings'],
                verification['recommendations']
            )
        except Exception:
            # Table might not exist yet
            logger.warning("Could not store verification results")


# Create verification table
VERIFICATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id UUID NOT NULL,
    verification_time TIMESTAMP WITH TIME ZONE NOT NULL,
    overall_status VARCHAR(50) NOT NULL,
    phase_results JSONB NOT NULL DEFAULT '{}',
    issues TEXT[] DEFAULT '{}',
    warnings TEXT[] DEFAULT '{}',
    recommendations TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verifications_pipeline ON pipeline_verifications(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_verifications_time ON pipeline_verifications(verification_time);
"""
