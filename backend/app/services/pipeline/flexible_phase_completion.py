"""
Flexible Phase Completion Handler

Handles phase completion logic that accounts for:
- Some content might not be analyzable (too short, failed scraping)
- Some companies might not be enrichable
- Phases should complete when all eligible work is done
"""

from datetime import datetime
from typing import Dict
from uuid import UUID
from loguru import logger
from app.core.database import DatabasePool


class FlexiblePhaseCompletion:
    """Handles flexible phase completion logic"""
    
    def __init__(self, db: DatabasePool):
        self.db = db
        
    async def check_and_complete_content_analysis(self, pipeline_id: UUID) -> bool:
        """
        Check if content analysis phase should be marked as completed.
        
        Returns True if the phase was marked as completed, False otherwise.
        """
        pipeline_id_str = str(pipeline_id)
        
        async with self.db.acquire() as conn:
            # Get current phase status
            phase_status = await conn.fetchrow("""
                SELECT status, started_at 
                FROM pipeline_phase_status
                WHERE pipeline_execution_id = $1 
                AND phase_name = 'content_analysis'
            """, pipeline_id_str)
            
            if not phase_status or phase_status['status'] != 'running':
                return False
                
            # Check if company enrichment is complete
            enrichment_complete = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM pipeline_phase_status
                    WHERE pipeline_execution_id = $1
                    AND phase_name = 'company_enrichment_serp'
                    AND status = 'completed'
                )
            """, pipeline_id_str)
            
            if not enrichment_complete:
                logger.debug("Company enrichment not complete, cannot complete content analysis")
                return False
            
            # Get analysis statistics
            stats = await conn.fetchrow("""
                WITH scraped_stats AS (
                    SELECT 
                        COUNT(DISTINCT sc.url) as total_scraped,
                        COUNT(DISTINCT CASE 
                            WHEN sc.status = 'completed' 
                            AND sc.content IS NOT NULL 
                            AND LENGTH(sc.content) > 100 
                            THEN sc.url 
                        END) as eligible_for_analysis
                    FROM scraped_content sc
                    INNER JOIN serp_results sr ON sr.url = sc.url
                    WHERE sr.pipeline_execution_id = $1
                ),
                analyzed_stats AS (
                    SELECT COUNT(DISTINCT oca.url) as total_analyzed
                    FROM optimized_content_analysis oca
                    INNER JOIN serp_results sr ON sr.url = oca.url
                    WHERE sr.pipeline_execution_id = $1
                )
                SELECT 
                    ss.total_scraped,
                    ss.eligible_for_analysis,
                    aas.total_analyzed,
                    CASE 
                        WHEN ss.eligible_for_analysis > 0 
                        THEN (aas.total_analyzed::float / ss.eligible_for_analysis::float) * 100
                        ELSE 100
                    END as completion_percentage
                FROM scraped_stats ss, analyzed_stats aas
            """, pipeline_id_str)
            
            if not stats:
                return False
                
            total_scraped = stats['total_scraped'] or 0
            eligible = stats['eligible_for_analysis'] or 0
            analyzed = stats['total_analyzed'] or 0
            completion_pct = stats['completion_percentage'] or 0
            
            logger.info(f"Content analysis stats for pipeline {pipeline_id}: "
                       f"scraped={total_scraped}, eligible={eligible}, "
                       f"analyzed={analyzed}, completion={completion_pct:.1f}%")
            
            # Completion criteria:
            # 1. All eligible content has been analyzed (100% completion)
            # 2. OR: 95%+ completion AND no new content analyzed in last 5 minutes
            # 3. OR: Phase has been running for over 2 hours with 90%+ completion
            
            should_complete = False
            completion_reason = ""
            
            if completion_pct >= 100:
                should_complete = True
                completion_reason = "All eligible content analyzed"
            elif completion_pct >= 95:
                # Check if there's been recent activity
                recent_analysis = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM optimized_content_analysis oca
                        INNER JOIN serp_results sr ON sr.url = oca.url
                        WHERE sr.pipeline_execution_id = $1
                        AND oca.created_at > NOW() - INTERVAL '5 minutes'
                    )
                """, pipeline_id_str)
                
                if not recent_analysis:
                    should_complete = True
                    completion_reason = f"No recent activity at {completion_pct:.1f}% completion"
            elif completion_pct >= 90 and phase_status['started_at']:
                # Check if phase has been running for over 2 hours
                runtime_hours = (datetime.utcnow() - phase_status['started_at']).total_seconds() / 3600
                if runtime_hours >= 2:
                    should_complete = True
                    completion_reason = f"Runtime exceeded 2 hours at {completion_pct:.1f}% completion"
                    
            if should_complete:
                logger.info(f"Marking content analysis as completed: {completion_reason}")
                
                # Update phase status
                await conn.execute("""
                    UPDATE pipeline_phase_status
                    SET status = 'completed',
                        completed_at = NOW()
                    WHERE pipeline_execution_id = $1
                    AND phase_name = 'content_analysis'
                    AND status = 'running'
                """, pipeline_id_str)
                
                # Log the completion in pipeline_executions phase_results
                await conn.execute("""
                    UPDATE pipeline_executions
                    SET phase_results = COALESCE(phase_results, '{}'::jsonb) || 
                        jsonb_build_object('content_analysis_flexible_completion', jsonb_build_object(
                            'completion_reason', $2::text,
                            'total_scraped', $3::integer,
                            'eligible_for_analysis', $4::integer,
                            'total_analyzed', $5::integer,
                            'completion_percentage', $6::float,
                            'completed_at', NOW()
                        ))
                    WHERE id = $1::uuid
                """, pipeline_id_str, completion_reason, total_scraped, 
                    eligible, analyzed, completion_pct)
                
                return True
                
            return False
            
    async def check_and_complete_youtube_enrichment(self, pipeline_id: UUID) -> bool:
        """
        Check if YouTube enrichment phase should be marked as completed or retried.
        
        Returns True if the phase was marked as completed, False otherwise.
        """
        pipeline_id_str = str(pipeline_id)
        
        async with self.db.acquire() as conn:
            # Get current phase status
            phase_status = await conn.fetchrow("""
                SELECT status, started_at, result_data
                FROM pipeline_phase_status
                WHERE pipeline_execution_id = $1 
                AND phase_name = 'youtube_enrichment'
            """, pipeline_id_str)
            
            if not phase_status or phase_status['status'] not in ['running', 'failed']:
                return False
                
            # Get video enrichment statistics
            stats = await conn.fetchrow("""
                WITH video_stats AS (
                    SELECT 
                        COUNT(DISTINCT sr.url) as total_videos
                    FROM serp_results sr
                    WHERE sr.pipeline_execution_id = $1
                    AND sr.url LIKE '%youtube.com%'
                ),
                enriched_stats AS (
                    SELECT COUNT(DISTINCT vs.video_url) as enriched_videos
                    FROM video_snapshots vs
                    INNER JOIN serp_results sr ON sr.url = vs.video_url
                    WHERE sr.pipeline_execution_id = $1
                )
                SELECT 
                    vs.total_videos,
                    es.enriched_videos,
                    CASE 
                        WHEN vs.total_videos > 0 
                        THEN (es.enriched_videos::float / vs.total_videos::float) * 100
                        ELSE 100
                    END as completion_percentage
                FROM video_stats vs, enriched_stats es
            """, pipeline_id_str)
            
            if not stats:
                return False
                
            total_videos = stats['total_videos'] or 0
            enriched = stats['enriched_videos'] or 0
            completion_pct = stats['completion_percentage'] or 0
            
            logger.info(f"YouTube enrichment stats for pipeline {pipeline_id}: "
                       f"total={total_videos}, enriched={enriched}, "
                       f"completion={completion_pct:.1f}%")
            
            # Completion criteria:
            # 1. All videos have been enriched (100% completion)
            # 2. OR: 80%+ completion (YouTube API often has quota/rate limits)
            # 3. OR: Phase has been running for over 1 hour with 50%+ completion
            # 4. OR: Phase previously failed but has 50%+ completion
            
            should_complete = False
            completion_reason = ""
            
            if completion_pct >= 100:
                should_complete = True
                completion_reason = "All videos enriched"
            elif completion_pct >= 80:
                should_complete = True
                completion_reason = f"Acceptable completion rate: {completion_pct:.1f}%"
            elif completion_pct >= 50:
                if phase_status['status'] == 'failed':
                    should_complete = True
                    completion_reason = f"Previous failure with {completion_pct:.1f}% completion"
                elif phase_status['started_at']:
                    runtime_hours = (datetime.utcnow() - phase_status['started_at']).total_seconds() / 3600
                    if runtime_hours >= 1:
                        should_complete = True
                        completion_reason = f"Runtime exceeded 1 hour at {completion_pct:.1f}% completion"
                        
            if should_complete:
                logger.info(f"Marking YouTube enrichment as completed: {completion_reason}")
                
                # Update phase status
                await conn.execute("""
                    UPDATE pipeline_phase_status
                    SET status = 'completed',
                        completed_at = NOW(),
                        result_data = COALESCE(result_data, '{}'::jsonb) || 
                            jsonb_build_object(
                                'flexible_completion', true,
                                'completion_reason', $2,
                                'total_videos', $3,
                                'enriched_videos', $4,
                                'completion_percentage', $5
                            )
                    WHERE pipeline_execution_id = $1
                    AND phase_name = 'youtube_enrichment'
                    AND status IN ('running', 'failed')
                """, pipeline_id_str, completion_reason, total_videos, 
                    enriched, completion_pct)
                
                return True
                
            return False
    
    async def check_all_phases(self, pipeline_id: UUID) -> Dict[str, bool]:
        """
        Check all phases for flexible completion criteria.
        
        Returns a dict of phase_name -> was_completed
        """
        results = {}
        
        # Check both content analysis and YouTube enrichment
        results['content_analysis'] = await self.check_and_complete_content_analysis(pipeline_id)
        results['youtube_enrichment'] = await self.check_and_complete_youtube_enrichment(pipeline_id)
        
        return results
