"""
Pipeline Resumption Service
Automatically resumes interrupted pipelines after backend restart
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
from loguru import logger

from app.core.database import db_pool
from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig


class PipelineResumptionService:
    """
    Handles automatic resumption of pipelines after backend restarts
    """
    
    def __init__(self, pipeline_service: PipelineService):
        self.pipeline_service = pipeline_service
        self.logger = logger.bind(component="pipeline_resumption")
        
    async def resume_interrupted_pipelines(self) -> List[UUID]:
        """
        Find and resume pipelines that were interrupted
        Returns list of resumed pipeline IDs
        """
        resumed_pipelines = []
        
        try:
            async with db_pool.acquire() as conn:
                # Find running pipelines that haven't been updated recently
                interrupted = await conn.fetch("""
                    SELECT 
                        pe.id,
                        pe.status,
                        pe.started_at,
                        pe.phase_results,
                        EXTRACT(EPOCH FROM (NOW() - COALESCE(pe.updated_at, pe.started_at)))/60 as mins_since_update
                    FROM pipeline_executions pe
                    WHERE pe.status = 'running'
                    AND (
                        -- No update in last 5 minutes
                        EXTRACT(EPOCH FROM (NOW() - COALESCE(pe.updated_at, pe.started_at)))/60 > 5
                        OR
                        -- SERP phase running but no batch monitoring
                        EXISTS (
                            SELECT 1 FROM pipeline_phase_status pps
                            WHERE pps.pipeline_execution_id = pe.id
                            AND pps.phase_name = 'serp_collection'
                            AND pps.status = 'running'
                        )
                    )
                    ORDER BY pe.started_at DESC
                """)
                
                self.logger.info(f"Found {len(interrupted)} potentially interrupted pipelines")
                
                for pipeline in interrupted:
                    pipeline_id = pipeline['id']
                    mins_inactive = pipeline['mins_since_update']
                    
                    # Check if SERP batches need monitoring
                    serp_batches = await self._get_unmonitored_serp_batches(conn, pipeline_id)
                    
                    if serp_batches:
                        self.logger.info(f"Resuming SERP monitoring for pipeline {pipeline_id} with {len(serp_batches)} batches")
                        await self._resume_serp_monitoring(pipeline_id, serp_batches)
                        resumed_pipelines.append(pipeline_id)
                    
                    # Check if content scraping needs resuming
                    elif await self._needs_content_scraping_resume(conn, pipeline_id):
                        self.logger.info(f"Resuming content scraping for pipeline {pipeline_id}")
                        await self._resume_content_scraping(pipeline_id)
                        resumed_pipelines.append(pipeline_id)
                    
                    # Check if content analysis needs resuming
                    elif await self._needs_content_analysis_resume(conn, pipeline_id):
                        self.logger.info(f"Resuming content analysis for pipeline {pipeline_id}")
                        await self._resume_content_analysis(pipeline_id)
                        resumed_pipelines.append(pipeline_id)
                    
                    # Check if pipeline can continue to next phase
                    elif mins_inactive > 10:
                        self.logger.info(f"Attempting to resume pipeline {pipeline_id} (inactive {mins_inactive:.1f} mins)")
                        try:
                            # Create a proper config for resumption
                            from app.services.pipeline.pipeline_service import PipelineConfig
                            config = PipelineConfig(
                                enable_content_scraping=True,
                                enable_content_analysis=True,
                                force_refresh=False
                            )
                            success = await self.pipeline_service.resume_pipeline(pipeline_id, config)
                            if success:
                                resumed_pipelines.append(pipeline_id)
                        except Exception as e:
                            self.logger.error(f"Failed to resume pipeline {pipeline_id}: {e}")
                
        except Exception as e:
            self.logger.error(f"Error during pipeline resumption check: {e}")
            
        return resumed_pipelines
    
    async def _get_unmonitored_serp_batches(self, conn, pipeline_id: UUID) -> List[Dict[str, Any]]:
        """Get SERP batches that need monitoring"""
        # TODO: Fix this query when serp_batch_coordinator_runs table is properly structured
        # For now, return empty list to avoid errors
        return []
        
        # Original query commented out due to missing columns in table
        # batches = await conn.fetch("""
        #     SELECT DISTINCT
        #         sbcr.batch_id,
        #         sbcr.content_type,
        #         sbcr.status,
        #         sbcr.batch_size,
        #         sbcr.created_at
        #     FROM serp_batch_coordinator_runs sbcr
        #     WHERE sbcr.pipeline_execution_id = $1
        #     AND sbcr.status IN ('created', 'running')
        #     AND sbcr.created_at > NOW() - INTERVAL '24 hours'
        #     ORDER BY sbcr.created_at
        # """, pipeline_id)
    
    async def _needs_content_analysis_resume(self, conn, pipeline_id: UUID) -> bool:
        """Check if content analysis needs to be resumed"""
        # Check for scraped content without analysis
        pending = await conn.fetchval("""
            SELECT COUNT(*)
            FROM scraped_content sc
            LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url
            WHERE sc.pipeline_execution_id = $1
            AND sc.status = 'completed'
            AND sc.content IS NOT NULL
            AND LENGTH(sc.content) > 100
            AND oca.id IS NULL
        """, pipeline_id)
        
        return pending > 0
    
    async def _resume_serp_monitoring(self, pipeline_id: UUID, batches: List[Dict[str, Any]]):
        """Resume SERP batch monitoring"""
        # Create monitoring tasks for each batch
        monitoring_tasks = []
        
        for batch in batches:
            # Reconstruct batch requests (we'll need to query or store this)
            batch_requests = await self._reconstruct_batch_requests(pipeline_id, batch['content_type'])
            
            if batch_requests:
                task = self.pipeline_service.serp_collector.monitor_batch(
                    batch_id=batch['batch_id'],
                    batch_requests=batch_requests,
                    content_type=batch['content_type'],
                    pipeline_execution_id=str(pipeline_id),
                    state_tracker=self.pipeline_service.state_tracker,
                    progress_callback=None  # Could add WebSocket callback here
                )
                monitoring_tasks.append(task)
        
        if monitoring_tasks:
            # Run monitoring tasks in background
            asyncio.create_task(self._run_monitoring_tasks(pipeline_id, monitoring_tasks))
    
    async def _reconstruct_batch_requests(self, pipeline_id: UUID, content_type: str) -> List[Dict[str, Any]]:
        """Reconstruct batch requests from pipeline data"""
        async with db_pool.acquire() as conn:
            # Get keywords and regions from the pipeline
            pipeline_data = await conn.fetchrow("""
                SELECT 
                    pe.phase_results,
                    ps.keywords,
                    ps.regions
                FROM pipeline_executions pe
                LEFT JOIN pipeline_schedules ps ON ps.is_active = true
                WHERE pe.id = $1
            """, pipeline_id)
            
            if not pipeline_data:
                return []
            
            # Extract keywords and regions
            phase_results = pipeline_data['phase_results'] or {}
            keywords = []
            regions = pipeline_data['regions'] or ['US', 'UK']
            
            # Try to get keywords from phase results
            if 'keyword_metrics_enrichment' in phase_results:
                keyword_count = phase_results['keyword_metrics_enrichment'].get('total_keywords', 0)
                if keyword_count > 0:
                    # Get actual keywords from database
                    keyword_rows = await conn.fetch("""
                        SELECT id, keyword FROM keywords 
                        WHERE is_active = true 
                        ORDER BY keyword
                    """)
                    keywords = [{'id': r['id'], 'keyword': r['keyword']} for r in keyword_rows]
            
            if not keywords:
                return []
            
            # Build batch requests
            batch_requests = []
            for kw in keywords:
                for region in regions:
                    batch_requests.append({
                        'keyword': kw['keyword'],
                        'keyword_id': kw['id'],
                        'region': region,
                        'location': self._get_location_string(region),
                        'gl': region.lower(),
                        'content_type': content_type
                    })
            
            return batch_requests
    
    def _get_location_string(self, region: str) -> str:
        """Convert region code to location string"""
        location_map = {
            'US': 'United States',
            'UK': 'United Kingdom',
            'CA': 'Canada',
            'AU': 'Australia',
            'DE': 'Germany',
            'FR': 'France',
            'ES': 'Spain',
            'IT': 'Italy',
            'JP': 'Japan',
            'BR': 'Brazil'
        }
        return location_map.get(region, region)
    
    async def _run_monitoring_tasks(self, pipeline_id: UUID, tasks):
        """Run monitoring tasks and update pipeline on completion"""
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
            failed = sum(1 for r in results if isinstance(r, Exception) or (isinstance(r, dict) and not r.get('success')))
            
            self.logger.info(f"SERP monitoring resumed for pipeline {pipeline_id}: {successful} successful, {failed} failed")
            
            # Update pipeline phase if all batches completed
            if successful > 0 and failed == 0:
                async with db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE pipeline_phase_status
                        SET status = 'completed',
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE pipeline_execution_id = $1
                        AND phase_name = 'serp_collection'
                        AND status = 'running'
                    """, pipeline_id)
                    
                # Try to continue pipeline
                await self.pipeline_service.resume_pipeline(pipeline_id)
                
        except Exception as e:
            self.logger.error(f"Error in monitoring tasks for pipeline {pipeline_id}: {e}")
    
    async def _needs_content_scraping_resume(self, conn, pipeline_id: UUID) -> bool:
        """Check if content scraping needs to be resumed"""
        # Check if content scraping phase is marked as running but has stalled
        phase_status = await conn.fetchrow("""
            SELECT status, updated_at, 
                   EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as mins_since_update
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1 AND phase_name = 'content_scraping'
        """, pipeline_id)
        
        if not phase_status:
            return False
            
        # If phase is running and hasn't updated in > 5 minutes, it needs resuming
        if phase_status['status'] == 'running' and phase_status['mins_since_update'] > 5:
            # Check if there are unscraped URLs
            unscraped = await conn.fetchval("""
                SELECT COUNT(DISTINCT sr.url)
                FROM serp_results sr
                LEFT JOIN scraped_content sc ON sr.url = sc.url 
                    AND sc.pipeline_execution_id = sr.pipeline_execution_id
                WHERE sr.pipeline_execution_id = $1
                AND sr.serp_type IN ('organic', 'news')
                AND sc.url IS NULL
            """, pipeline_id)
            
            return unscraped > 0
            
        return False
    
    async def _resume_content_scraping(self, pipeline_id: UUID):
        """Resume content scraping for a pipeline"""
        try:
            # Simply call resume_pipeline which will continue from where it left off
            # The pipeline service will skip completed phases and continue with scraping
            success = await self.pipeline_service.resume_pipeline(pipeline_id)
            if success:
                self.logger.info(f"Content scraping resumed for pipeline {pipeline_id}")
            else:
                self.logger.error(f"Failed to resume content scraping for pipeline {pipeline_id}")
        except Exception as e:
            self.logger.error(f"Error resuming content scraping: {e}")
    
    async def _resume_content_analysis(self, pipeline_id: UUID, fresh_analysis: bool = False):
        """Resume content analysis for a pipeline"""
        try:
            # Start concurrent content analyzer
            await self.pipeline_service.concurrent_content_analyzer.start_monitoring(
                pipeline_id=pipeline_id,
                project_id=None,  # Will be determined from pipeline
                fresh_analysis=fresh_analysis
            )
            self.logger.info(f"Content analyzer resumed for pipeline {pipeline_id} (fresh_analysis: {fresh_analysis})")
        except Exception as e:
            self.logger.error(f"Failed to resume content analyzer: {e}")


async def check_and_resume_pipelines():
    """Standalone function to check and resume pipelines"""
    from app.core.config import get_settings
    from app.services.pipeline.pipeline_service import PipelineService
    
    settings = get_settings()
    pipeline_service = PipelineService(settings, db_pool)
    resumption_service = PipelineResumptionService(pipeline_service)
    
    logger.info("Checking for interrupted pipelines...")
    resumed = await resumption_service.resume_interrupted_pipelines()
    
    if resumed:
        logger.info(f"Resumed {len(resumed)} pipelines: {[str(p) for p in resumed]}")
    else:
        logger.info("No pipelines needed resumption")
    
    return resumed
