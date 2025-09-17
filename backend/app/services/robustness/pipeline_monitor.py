"""
Pipeline Health Monitor
Monitors running pipelines and handles stuck/failed phases
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from uuid import UUID
from loguru import logger
import asyncpg

from app.core.database import db_pool
from app.services.pipeline.pipeline_alerting import PipelineAlerter
from app.services.pipeline.flexible_phase_completion import FlexiblePhaseCompletion


class PipelineMonitor:
    """
    Monitors pipeline health and handles stuck phases with:
    - Phase timeout detection
    - Automatic recovery attempts
    - Pipeline completion validation
    - Alerting for manual intervention
    """
    
    # Phase timeout configurations (in minutes)
    PHASE_TIMEOUTS = {
        "keyword_metrics": 30,
        "serp_collection": 120,  # Can take longer for many keywords
        "company_enrichment": 60,
        "video_enrichment": 60,
        "content_scraping": 180,  # Can take very long for many URLs
        "content_analysis": 240,  # Depends on content volume
        "dsi_calculation": 30
    }
    
    # Maximum pipeline runtime before considered stuck (hours)
    MAX_PIPELINE_RUNTIME = 48
    
    def __init__(self):
        self.monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self.alerter = PipelineAlerter(db_pool)
        self.phase_completion = FlexiblePhaseCompletion(db_pool)
        
    async def start_monitoring(self):
        """Start the pipeline monitor"""
        if self.monitoring:
            logger.warning("Pipeline monitor already running")
            return
            
        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Pipeline monitor started")
        
    async def stop_monitoring(self):
        """Stop the pipeline monitor"""
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Pipeline monitor stopped")
        
    async def _monitor_loop(self):
        """Main monitoring loop"""
        check_count = 0
        while self.monitoring:
            try:
                await self._check_pipelines()
                
                # Check for alerts every 5 minutes
                check_count += 1
                if check_count % 5 == 0:
                    alerts = await self.alerter.check_long_running_pipelines()
                    if alerts:
                        logger.warning(f"Generated {len(alerts)} pipeline alerts")
                    
                    # Clean up old alerts
                    await self.alerter.clear_completed_pipeline_alerts()
                
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(60)
                
    async def _check_pipelines(self):
        """Check all active pipelines for issues"""
        async with db_pool.acquire() as conn:
            # Get all running pipelines
            pipelines = await conn.fetch("""
                SELECT id, status, created_at, updated_at,
                       EXTRACT(EPOCH FROM (NOW() - created_at))/3600 as hours_running,
                       EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as mins_since_update
                FROM pipeline_executions
                WHERE status IN ('running', 'pending')
            """)
            
            for pipeline in pipelines:
                pipeline_id = str(pipeline['id'])
                
                # Check if pipeline is stuck (running too long)
                if pipeline['hours_running'] > self.MAX_PIPELINE_RUNTIME:
                    logger.error(f"Pipeline {pipeline_id} has been running for {pipeline['hours_running']:.1f} hours")
                    await self._handle_stuck_pipeline(conn, pipeline_id, "Exceeded maximum runtime")
                    continue
                
                # Check individual phases
                await self._check_pipeline_phases(conn, pipeline_id)
                
                # Check for flexible phase completion
                try:
                    completion_results = await self.phase_completion.check_all_phases(UUID(pipeline_id))
                    for phase_name, was_completed in completion_results.items():
                        if was_completed:
                            logger.info(f"Phase {phase_name} marked as completed for pipeline {pipeline_id}")
                except Exception as e:
                    logger.warning(f"Error checking flexible phase completion: {e}")
                
                # Check if we need to trigger pending phases (e.g., DSI after content analysis)
                try:
                    from app.services.pipeline.pipeline_service import PipelineService
                    from app.core.config import get_settings
                    from app.core.database import db_pool as database_pool
                    
                    settings = get_settings()
                    pipeline_service = PipelineService(settings, database_pool)
                    triggered = await pipeline_service.check_and_trigger_pending_phases(UUID(pipeline_id))
                    if triggered:
                        logger.info(f"Triggered pending phases for pipeline {pipeline_id}")
                except Exception as e:
                    logger.warning(f"Error checking/triggering pending phases: {e}")
                
    async def _check_pipeline_phases(self, conn: asyncpg.Connection, pipeline_id: str):
        """Check phases of a specific pipeline"""
        # Get phase status from pipeline_status table if it exists
        try:
            phases = await conn.fetch("""
                SELECT phase_name, status, progress, updated_at,
                       EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as mins_since_update
                FROM pipeline_status
                WHERE pipeline_id = $1
            """, pipeline_id)
            
            for phase in phases:
                if phase['status'] == 'running':
                    timeout = self.PHASE_TIMEOUTS.get(phase['phase_name'], 60)
                    if phase['mins_since_update'] > timeout:
                        logger.warning(f"Phase {phase['phase_name']} in pipeline {pipeline_id} "
                                     f"hasn't updated in {phase['mins_since_update']:.0f} minutes")
                        await self._handle_stuck_phase(conn, pipeline_id, phase['phase_name'])
                        
        except asyncpg.UndefinedTableError:
            # Fallback: check content analysis status directly
            await self._check_content_analysis(conn, pipeline_id)
            
    async def _check_content_analysis(self, conn: asyncpg.Connection, pipeline_id: str):
        """Check if content analysis is stuck"""
        # Get analysis stats
        stats = await conn.fetchrow("""
            WITH scraped AS (
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status='completed' AND content IS NOT NULL 
                           AND LENGTH(content) > 100 THEN 1 ELSE 0 END) as ready,
                       MAX(created_at) as last_scrape
                FROM scraped_content
                WHERE pipeline_execution_id = $1
            ),
            analyzed AS (
                SELECT COUNT(DISTINCT oca.id) as done,
                       MAX(oca.analyzed_at) as last_analysis
                FROM optimized_content_analysis oca
                JOIN scraped_content sc ON oca.url = sc.url
                WHERE sc.pipeline_execution_id = $1
            )
            SELECT 
                scraped.ready as ready_to_analyze,
                analyzed.done as already_analyzed,
                scraped.ready - analyzed.done as pending,
                scraped.last_scrape,
                analyzed.last_analysis,
                EXTRACT(EPOCH FROM (NOW() - analyzed.last_analysis))/60 as mins_since_analysis
            FROM scraped, analyzed
        """, pipeline_id)
        
        if stats['pending'] > 0:
            # Check if analysis has stalled
            if stats['last_analysis'] is None or stats['mins_since_analysis'] > 30:
                logger.warning(f"Content analysis appears stuck for pipeline {pipeline_id}: "
                             f"{stats['pending']} URLs pending, last analysis "
                             f"{stats['mins_since_analysis']:.0f} minutes ago")
                await self._restart_content_analysis(conn, pipeline_id)
                
    async def _restart_content_analysis(self, conn: asyncpg.Connection, pipeline_id: str):
        """Attempt to restart content analysis"""
        logger.info(f"Attempting to restart content analysis for pipeline {pipeline_id}")
        
        # Import here to avoid circular imports
        try:
            from app.services.analysis.concurrent_content_analyzer import ConcurrentContentAnalyzer
            from app.services.analysis.optimized_unified_analyzer import OptimizedUnifiedAnalyzer
            from app.services.model_config import ModelConfigService
            
            model_config = ModelConfigService()
            analyzer = OptimizedUnifiedAnalyzer(model_config)
            content_analyzer = ConcurrentContentAnalyzer(analyzer)
            
            # Start monitoring in background
            asyncio.create_task(content_analyzer.start_monitoring(pipeline_id))
            logger.info(f"Content analyzer restarted for pipeline {pipeline_id}")
            
        except Exception as e:
            logger.error(f"Failed to restart content analyzer: {e}")
    
    async def _restart_youtube_enrichment(self, conn: asyncpg.Connection, pipeline_id: str):
        """Restart YouTube enrichment after resetting circuit breaker"""
        logger.info(f"Attempting to restart YouTube enrichment for pipeline {pipeline_id}")
        
        # Reset circuit breaker
        await conn.execute("""
            UPDATE circuit_breakers 
            SET state = 'closed', failure_count = 0, opened_at = NULL 
            WHERE service_name = 'youtube_api'
        """)
        
        # Update phase to trigger re-processing
        await conn.execute("""
            UPDATE pipeline_phase_status 
            SET updated_at = NOW()
            WHERE pipeline_execution_id = $1 AND phase_name = 'youtube_enrichment'
        """, pipeline_id)
        
        # Trigger pipeline service to resume
        try:
            from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig
            from app.core.config import get_settings
            from app.core.database import db_pool as database_pool
            
            settings = get_settings()
            pipeline_service = PipelineService(settings, database_pool)
            config = PipelineConfig(enable_content_scraping=True, enable_content_analysis=True)
            await pipeline_service.resume_pipeline(UUID(pipeline_id), config)
            logger.info(f"YouTube enrichment restarted for pipeline {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to restart YouTube enrichment: {e}")
    
    async def _restart_content_scraping(self, conn: asyncpg.Connection, pipeline_id: str):
        """Restart content scraping"""
        logger.info(f"Attempting to restart content scraping for pipeline {pipeline_id}")
        
        # Update phase to trigger re-processing
        await conn.execute("""
            UPDATE pipeline_phase_status 
            SET updated_at = NOW()
            WHERE pipeline_execution_id = $1 AND phase_name = 'content_scraping'
        """, pipeline_id)
        
        # Trigger pipeline service to resume
        try:
            from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig
            from app.core.config import get_settings
            from app.core.database import db_pool as database_pool
            
            settings = get_settings()
            pipeline_service = PipelineService(settings, database_pool)
            config = PipelineConfig(enable_content_scraping=True, enable_content_analysis=True)
            await pipeline_service.resume_pipeline(UUID(pipeline_id), config)
            logger.info(f"Content scraping restarted for pipeline {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to restart content scraping: {e}")
    
    async def _restart_phase(self, conn: asyncpg.Connection, pipeline_id: str, phase_name: str):
        """Generic phase restart"""
        logger.info(f"Attempting to restart phase {phase_name} for pipeline {pipeline_id}")
        
        # Update phase to trigger re-processing
        await conn.execute("""
            UPDATE pipeline_phase_status 
            SET updated_at = NOW()
            WHERE pipeline_execution_id = $1 AND phase_name = $2
        """, pipeline_id, phase_name)
        
        # Trigger pipeline service to check and trigger pending phases
        try:
            from app.services.pipeline.pipeline_service import PipelineService
            from app.core.config import get_settings
            from app.core.database import db_pool as database_pool
            
            settings = get_settings()
            pipeline_service = PipelineService(settings, database_pool)
            triggered = await pipeline_service.check_and_trigger_pending_phases(UUID(pipeline_id))
            if triggered:
                logger.info(f"Phase {phase_name} restarted for pipeline {pipeline_id}")
            else:
                logger.warning(f"Could not restart phase {phase_name} for pipeline {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to restart phase {phase_name}: {e}")
            
    async def _handle_stuck_pipeline(self, conn: asyncpg.Connection, pipeline_id: str, reason: str):
        """Handle a stuck pipeline"""
        logger.error(f"Handling stuck pipeline {pipeline_id}: {reason}")
        
        # Check if we should auto-complete or fail
        can_complete = await self._check_if_can_complete(conn, pipeline_id)
        
        if can_complete:
            logger.info(f"Auto-completing pipeline {pipeline_id}")
            await conn.execute("""
                UPDATE pipeline_executions
                SET status = 'completed',
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
            """, pipeline_id)
        else:
            logger.error(f"Marking pipeline {pipeline_id} as failed")
            await conn.execute("""
                UPDATE pipeline_executions
                SET status = 'failed',
                    completed_at = NOW(),
                    updated_at = NOW(),
                    error_message = $2
                WHERE id = $1
            """, pipeline_id, f"Pipeline stuck: {reason}")
            
    async def _check_if_can_complete(self, conn: asyncpg.Connection, pipeline_id: str) -> bool:
        """Check if a pipeline has enough data to be considered complete"""
        # Check if critical data exists
        checks = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM serp_results WHERE pipeline_execution_id = $1) as serp_count,
                (SELECT COUNT(*) FROM scraped_content WHERE pipeline_execution_id = $1 AND status = 'completed') as scraped_count,
                (SELECT COUNT(DISTINCT oca.id) FROM optimized_content_analysis oca 
                 JOIN scraped_content sc ON oca.url = sc.url 
                 WHERE sc.pipeline_execution_id = $1) as analyzed_count,
                (SELECT COUNT(*) FROM dsi_scores WHERE pipeline_execution_id = $1) as dsi_count
        """, pipeline_id)
        
        # Pipeline can complete if it has SERP results and either analysis or DSI scores
        return (checks['serp_count'] > 0 and 
                (checks['analyzed_count'] > 0 or checks['dsi_count'] > 0))
                
    async def _handle_stuck_phase(self, conn: asyncpg.Connection, pipeline_id: str, phase_name: str):
        """Handle a stuck phase"""
        logger.warning(f"Phase {phase_name} is stuck in pipeline {pipeline_id}")
        
        # Use the phase timeout handler to determine action
        from app.services.pipeline.phase_timeout_handler import PhaseTimeoutHandler
        action = await PhaseTimeoutHandler.handle_phase_timeout(pipeline_id, phase_name)
        
        if action["action"] == "restart_analyzer":
            await self._restart_content_analysis(conn, pipeline_id)
        elif action["action"] == "restart_youtube_enrichment":
            await self._restart_youtube_enrichment(conn, pipeline_id)
        elif action["action"] == "restart_content_scraping":
            await self._restart_content_scraping(conn, pipeline_id)
        elif action["action"] == "restart_phase":
            await self._restart_phase(conn, pipeline_id, phase_name)
        elif action["action"] == "complete_phase":
            # Mark phase as completed with reason
            await conn.execute("""
                UPDATE pipeline_phase_status
                SET status = 'completed',
                    completed_at = NOW(),
                    result_data = jsonb_build_object(
                        'flexible_completion', true,
                        'completion_reason', $3
                    )
                WHERE pipeline_execution_id = $1 AND phase_name = $2
            """, pipeline_id, phase_name, action["reason"])
            logger.info(f"Marked phase {phase_name} as completed: {action['reason']}")
        else:
            # Mark as failed
            await conn.execute("""
                UPDATE pipeline_phase_status
                SET status = 'failed',
                    result_data = jsonb_build_object('error', $3)
                WHERE pipeline_execution_id = $1 AND phase_name = $2
            """, pipeline_id, phase_name, action.get("reason", "Phase timeout"))


# Global monitor instance
pipeline_monitor = PipelineMonitor()


async def ensure_monitor_running():
    """Ensure the pipeline monitor is running"""
    if not pipeline_monitor.monitoring:
        await pipeline_monitor.start_monitoring()
