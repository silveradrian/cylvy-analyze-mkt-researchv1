"""
Phase Timeout Handler
Handles timeout detection and recovery for pipeline phases
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID
from loguru import logger

from app.core.database import db_pool


class PhaseTimeoutHandler:
    """Handles phase-level timeouts and recovery"""
    
    # Phase timeout configurations (in minutes)
    PHASE_TIMEOUTS = {
        "keyword_metrics": 30,
        "serp_collection": 120,
        "company_enrichment": 60,
        "video_enrichment": 60,
        "content_scraping": 180,
        "content_analysis": 240,
        "dsi_calculation": 30
    }
    
    @classmethod
    async def check_phase_timeout(cls, pipeline_id: str, phase_name: str, start_time: datetime) -> bool:
        """Check if a phase has exceeded its timeout"""
        timeout_minutes = cls.PHASE_TIMEOUTS.get(phase_name, 60)
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
        
        if elapsed > timeout_minutes:
            logger.warning(f"Phase {phase_name} in pipeline {pipeline_id} has exceeded timeout "
                         f"({elapsed:.0f} minutes > {timeout_minutes} minutes)")
            return True
        return False
    
    @classmethod
    async def handle_phase_timeout(cls, pipeline_id: str, phase_name: str) -> Dict[str, any]:
        """Handle a phase that has timed out"""
        async with db_pool.acquire() as conn:
            # Special handling for content_analysis
            if phase_name == "content_analysis":
                return await cls._handle_content_analysis_timeout(conn, pipeline_id)
            
            # Special handling for youtube_enrichment
            if phase_name == "youtube_enrichment":
                return await cls._handle_youtube_enrichment_timeout(conn, pipeline_id)
            
            # Special handling for content_scraping
            if phase_name == "content_scraping":
                return await cls._handle_content_scraping_timeout(conn, pipeline_id)
            
            # For other phases, attempt restart
            logger.warning(f"Phase {phase_name} timed out, attempting automatic restart")
            return {
                "action": "restart_phase",
                "reason": f"Phase exceeded {cls.PHASE_TIMEOUTS[phase_name]} minute timeout"
            }
    
    @classmethod
    async def _handle_content_analysis_timeout(cls, conn, pipeline_id: str) -> Dict[str, any]:
        """Special handling for content analysis timeout"""
        # Check if significant progress has been made
        stats = await conn.fetchrow("""
            WITH analyzed AS (
                SELECT COUNT(DISTINCT oca.id) as count
                FROM optimized_content_analysis oca
                JOIN scraped_content sc ON oca.url = sc.url
                WHERE sc.pipeline_execution_id = $1
            ),
            total AS (
                SELECT COUNT(*) as count
                FROM scraped_content
                WHERE pipeline_execution_id = $1
                  AND status = 'completed'
                  AND content IS NOT NULL
                  AND LENGTH(content) > 100
            )
            SELECT 
                analyzed.count as analyzed,
                total.count as total,
                CASE WHEN total.count > 0 
                     THEN analyzed.count::float / total.count::float 
                     ELSE 0 
                END as progress_ratio
            FROM analyzed, total
        """, pipeline_id)
        
        if stats['progress_ratio'] >= 0.8:  # 80% complete
            logger.info(f"Content analysis {stats['progress_ratio']*100:.0f}% complete, marking as sufficient")
            return {
                "action": "complete_phase",
                "reason": f"Analyzed {stats['analyzed']} of {stats['total']} pages (sufficient coverage)"
            }
        else:
            # Try to restart the analyzer
            logger.warning(f"Content analysis only {stats['progress_ratio']*100:.0f}% complete, attempting restart")
            return {
                "action": "restart_analyzer",
                "analyzed": stats['analyzed'],
                "total": stats['total']
            }
    
    @classmethod
    async def _handle_youtube_enrichment_timeout(cls, conn, pipeline_id: str) -> Dict[str, any]:
        """Handle YouTube enrichment timeout with circuit breaker reset"""
        # Check circuit breaker status
        cb_status = await conn.fetchrow("""
            SELECT state, failure_count, total_failures 
            FROM circuit_breakers 
            WHERE service_name = 'youtube_api'
        """)
        
        if cb_status and cb_status['state'] == 'open':
            # Reset circuit breaker
            await conn.execute("""
                UPDATE circuit_breakers 
                SET state = 'closed', failure_count = 0, opened_at = NULL 
                WHERE service_name = 'youtube_api'
            """)
            logger.info("Reset YouTube API circuit breaker due to timeout")
        
        # Check progress
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(DISTINCT sr.url) as total_videos,
                COUNT(DISTINCT vs.video_id) as enriched_videos
            FROM serp_results sr
            LEFT JOIN video_snapshots vs ON sr.url = vs.video_url
            WHERE sr.pipeline_execution_id = $1
            AND sr.url LIKE '%youtube.com%'
        """, pipeline_id)
        
        progress_ratio = stats['enriched_videos'] / stats['total_videos'] if stats['total_videos'] > 0 else 0
        
        if progress_ratio >= 0.5:  # 50% complete
            logger.info(f"YouTube enrichment {progress_ratio*100:.0f}% complete, marking as sufficient")
            return {
                "action": "complete_phase",
                "reason": f"Enriched {stats['enriched_videos']} of {stats['total_videos']} videos (sufficient coverage)"
            }
        else:
            logger.warning(f"YouTube enrichment only {progress_ratio*100:.0f}% complete, restarting")
            return {
                "action": "restart_youtube_enrichment",
                "enriched": stats['enriched_videos'],
                "total": stats['total_videos']
            }
    
    @classmethod
    async def _handle_content_scraping_timeout(cls, conn, pipeline_id: str) -> Dict[str, any]:
        """Handle content scraping timeout"""
        # Check progress
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(DISTINCT sr.url) as total_urls,
                COUNT(DISTINCT sc.url) as scraped_urls
            FROM serp_results sr
            LEFT JOIN scraped_content sc ON sr.url = sc.url AND sc.pipeline_execution_id = sr.pipeline_execution_id
            WHERE sr.pipeline_execution_id = $1
            AND sr.serp_type IN ('organic', 'news')
        """, pipeline_id)
        
        progress_ratio = stats['scraped_urls'] / stats['total_urls'] if stats['total_urls'] > 0 else 0
        
        if progress_ratio >= 0.7:  # 70% complete
            logger.info(f"Content scraping {progress_ratio*100:.0f}% complete, marking as sufficient")
            return {
                "action": "complete_phase",
                "reason": f"Scraped {stats['scraped_urls']} of {stats['total_urls']} pages (sufficient coverage)"
            }
        else:
            logger.warning(f"Content scraping only {progress_ratio*100:.0f}% complete, restarting")
            return {
                "action": "restart_content_scraping",
                "scraped": stats['scraped_urls'],
                "total": stats['total_urls']
            }
    
    @classmethod
    async def implement_phase_watchdog(cls, pipeline_id: str, phase_name: str, phase_task: asyncio.Task):
        """Implement a watchdog for a running phase"""
        timeout_minutes = cls.PHASE_TIMEOUTS.get(phase_name, 60)
        
        try:
            # Wait for phase completion with timeout
            await asyncio.wait_for(phase_task, timeout=timeout_minutes * 60)
        except asyncio.TimeoutError:
            logger.error(f"Phase {phase_name} timed out after {timeout_minutes} minutes")
            phase_task.cancel()
            
            # Handle the timeout
            action = await cls.handle_phase_timeout(pipeline_id, phase_name)
            
            if action["action"] == "restart_analyzer":
                # Restart content analyzer
                from app.services.analysis.concurrent_content_analyzer import ConcurrentContentAnalyzer
                from app.services.analysis.optimized_unified_analyzer import OptimizedUnifiedAnalyzer
                from app.core.config import settings
                
                try:
                    analyzer = OptimizedUnifiedAnalyzer(settings, db_pool)
                    content_analyzer = ConcurrentContentAnalyzer(analyzer)
                    asyncio.create_task(content_analyzer.start_monitoring(pipeline_id))
                    logger.info("Content analyzer restarted after timeout")
                except Exception as e:
                    logger.error(f"Failed to restart analyzer: {e}")
                    raise
            else:
                raise TimeoutError(f"Phase {phase_name} exceeded timeout limit")
