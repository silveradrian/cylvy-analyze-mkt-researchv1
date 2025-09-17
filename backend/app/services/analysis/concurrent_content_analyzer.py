"""
Concurrent Content Analysis Service

This service monitors the database for content that has been scraped and enriched
but not yet analyzed, and processes it immediately without waiting for all
scraping to complete.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID
import json

from loguru import logger
from asyncpg.pool import Pool

from app.core.database import db_pool
from app.services.analysis.optimized_unified_analyzer import OptimizedUnifiedAnalyzer


class ConcurrentContentAnalyzer:
    """
    Monitors and analyzes content as soon as it's ready (scraped + enriched)
    """
    
    def __init__(self, settings, db: Pool):
        self.settings = settings
        self.db = db
        self.analyzer = OptimizedUnifiedAnalyzer(settings, db)
        self.is_running = False
        self._monitor_task = None
        self._processed_urls: Set[str] = set()
        self._batch_size = 50  # Increased batch size for faster processing
        self._check_interval = 5  # Check for new content every 5 seconds
        self._concurrent_limit = getattr(settings, 'DEFAULT_ANALYZER_CONCURRENT_LIMIT', 50)  # OpenAI limits support high concurrency
        # Global semaphore to limit total concurrent API calls across all batches
        self._global_semaphore = asyncio.Semaphore(self._concurrent_limit)
        # Ensure attribute exists even before start_monitoring is called
        self.pipeline_id: Optional[UUID] = None
        self.project_id: Optional[str] = None
        self._start_time: Optional[float] = None
        # Fresh analysis flag - when True, reprocess all content regardless of previous analysis
        self._fresh_analysis: bool = False
        
    async def start_monitoring(self, pipeline_id: UUID, project_id: Optional[str] = None, fresh_analysis: bool = False):
        """Start monitoring for new content to analyze"""
        if self.is_running:
            logger.warning("Concurrent content analyzer already running")
            return
        
        # Validate analyzer is properly configured
        test_dimensions = await self.analyzer._load_all_dimensions_as_generic(project_id)
        if not test_dimensions:
            logger.error(f"Cannot start content analyzer for pipeline {pipeline_id}: No dimensions configured")
            return
        
        validation_result = await self.analyzer._validate_dimensions(test_dimensions, project_id)
        if not validation_result['valid']:
            logger.error(f"Cannot start content analyzer: {validation_result['message']}")
            return
            
        self.is_running = True
        self.pipeline_id = pipeline_id
        self.project_id = project_id
        self._processed_urls = set()
        self._start_time = asyncio.get_event_loop().time()
        self._fresh_analysis = fresh_analysis
        
        # Clear processed URLs cache if doing fresh analysis
        if fresh_analysis:
            self._total_processed = 0  # Initialize counter for fresh analysis
            self._fresh_analysis_offset = 0  # Track offset for fresh analysis progression
            logger.info(f"🧹 FRESH ANALYSIS MODE: Will reprocess all content, ignoring previous analysis")
        
        logger.info(f"Starting concurrent content analysis for pipeline {pipeline_id}, project_id={project_id} (fresh_analysis: {fresh_analysis})")
        logger.info(f"Analyzer configured with {len(test_dimensions)} dimensions")
        logger.info(f"Concurrency: {self._concurrent_limit} total, batch size: {self._batch_size}")
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
    async def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped concurrent content analysis monitoring")
        
    async def _monitor_loop(self):
        """Main monitoring loop with concurrent batch processing"""
        logger.info(f"Monitor loop started for pipeline {self.pipeline_id}")
        iterations = 0
        
        # Track active batch tasks
        active_batches = set()
        max_concurrent_batches = max(1, self._concurrent_limit // self._batch_size)  # e.g., 50/20 = 2 concurrent batches
        
        logger.info(f"Concurrent batch processing enabled: {max_concurrent_batches} batches × {self._batch_size} items = {max_concurrent_batches * self._batch_size} concurrent analyses")
        
        while self.is_running:
            try:
                iterations += 1
                if iterations % 6 == 1:  # Log every 30 seconds (6 * 5s)
                    logger.info(f"Monitor loop iteration {iterations}, active batches: {len(active_batches)}")
                
                # Debug: Log is_running status periodically
                if iterations % 3 == 1:  # Every 15 seconds
                    logger.debug(f"Monitor loop debug: is_running={self.is_running}, pipeline_id={self.pipeline_id}")
                
                # Clean up completed batches
                if active_batches:
                    done_batches = {task for task in active_batches if task.done()}
                    for task in done_batches:
                        try:
                            await task  # Retrieve any exceptions
                        except Exception as e:
                            logger.error(f"Batch processing error: {e}")
                    active_batches -= done_batches
                
                # Launch new batches if under limit
                while len(active_batches) < max_concurrent_batches:
                    logger.debug(f"🔍 Checking for ready content (iteration {iterations})")
                    ready_content = await self._get_ready_content()
                    logger.debug(f"🔍 Found {len(ready_content) if ready_content else 0} items ready for analysis")
                    
                    if ready_content:
                        sample = [c.get('url') for c in ready_content[:3]]
                        logger.info(f"Starting batch {len(active_batches)+1}/{max_concurrent_batches} with {len(ready_content)} items; sample={sample}")
                        
                        # Launch batch processing as background task
                        batch_task = asyncio.create_task(self._process_batch(ready_content))
                        active_batches.add(batch_task)
                        logger.debug(f"✅ Batch task created and added to active_batches")
                    else:
                        # No more content available
                        logger.debug(f"❌ No ready content found, breaking from batch creation loop")
                        break
                
                # Log status periodically
                if iterations % 12 == 1 and active_batches:  # Every minute
                    elapsed_minutes = (asyncio.get_event_loop().time() - self._start_time) / 60
                    items_per_minute = len(self._processed_urls) / elapsed_minutes if elapsed_minutes > 0 else 0
                    logger.info(f"Concurrent batch status: {len(active_batches)} active batches | ~{len(active_batches) * self._batch_size} items in flight | Rate: {items_per_minute:.1f} items/min")
                
                # Wait before checking again
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in content monitor loop: {e}")
                await asyncio.sleep(self._check_interval)
                
    async def _get_ready_content(self) -> List[Dict]:
        """
        Get content that:
        1. Has been successfully scraped
        2. Has company enrichment data (REQUIRED - only enriched pages are analyzed)
        3. Has not been analyzed yet
        4. Has not been processed in this session
        """
        # If not initialized yet, nothing to process
        if not self.pipeline_id:
            logger.warning("_get_ready_content called but pipeline_id is None")
            return []

        logger.debug(f"Checking for ready content: pipeline_id={self.pipeline_id}")
        async with self.db.acquire() as conn:
            # Allow content analysis to proceed even if company enrichment phase isn't complete,
            # but only analyze pages that have been successfully enriched with company data
            enrichment_complete = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM pipeline_phase_status
                    WHERE pipeline_execution_id = $1
                    AND phase_name = 'company_enrichment_serp'
                    AND status = 'completed'
                )
            """, self.pipeline_id)
            
            if not enrichment_complete:
                logger.info("Company enrichment not complete, but proceeding with content analysis for already enriched pages")
            
            # Build the query with proper parameterization
            params = [self.pipeline_id]
            param_count = 2
            
            # Add URL filter if needed
            url_filter = ""
            if self._processed_urls and not self._fresh_analysis:
                url_filter = f"AND sc.url != ALL(${param_count}::text[])"
                params.append(list(self._processed_urls))
                param_count += 1
            
            # Content analysis matches pipeline service approach - process all scraped content
            # Get company data based on domain extracted from URL when available
            query = f"""
                SELECT DISTINCT
                    sc.url,
                    sc.title,
                    sc.content,
                    sc.meta_description,
                    sc.domain,
                    -- Company name from enriched data or fallback to domain
                    COALESCE(cp.company_name, sc.domain) as company_name,
                    COALESCE(cp.domain, sc.domain) as company_domain,
                    cp.industry,
                    cp.employee_count as company_size,
                    COALESCE(cp.source, 'domain_fallback') as source_type
                FROM scraped_content sc
                LEFT JOIN company_domains cd ON cd.domain = sc.domain
                LEFT JOIN company_profiles cp ON cp.id = cd.company_id
                LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url AND oca.project_id IS NULL
                WHERE sc.pipeline_execution_id = $1
                    AND sc.status = 'completed'
                    AND sc.content IS NOT NULL
                    AND LENGTH(sc.content) > 100
                    {self._get_analysis_filter()}
                    {url_filter}
                ORDER BY sc.url  -- Ensure consistent ordering for progression
                LIMIT {self._batch_size}
                {f"OFFSET {self._fresh_analysis_offset}" if self._fresh_analysis else ""}
            """

            results = await conn.fetch(query, *params)
            return [dict(row) for row in results]
    
    def _get_analysis_filter(self) -> str:
        """Get SQL filter condition based on fresh analysis mode"""
        if self._fresh_analysis:
            # Fresh analysis: process ALL content regardless of previous analysis
            logger.debug("Fresh analysis mode: including all content")
            return ""  # No filter - include all content
        else:
            # Normal mode: only process content that hasn't been analyzed yet
            return "AND oca.id IS NULL"
            
    async def _process_batch(self, content_batch: List[Dict]):
        """Process a batch of content concurrently using global semaphore"""
        
        async def analyze_with_semaphore(content_data: Dict):
            async with self._global_semaphore:
                return await self._analyze_single_content(content_data)
                
        tasks = [analyze_with_semaphore(content) for content in content_batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Track successfully processed URLs (but not in fresh analysis mode)
        if not self._fresh_analysis:
            for i, result in enumerate(results):
                if result and not isinstance(result, Exception):
                    self._processed_urls.add(content_batch[i]['url'])
                
        # Log summary with performance metrics
        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        # Track total processed correctly for both modes
        if self._fresh_analysis:
            # In fresh analysis mode, increment a counter and offset for progression
            if not hasattr(self, '_total_processed'):
                self._total_processed = 0
            if not hasattr(self, '_fresh_analysis_offset'):
                self._fresh_analysis_offset = 0
            self._total_processed += success_count
            self._fresh_analysis_offset += len(content_batch)  # Move offset forward by batch size
            total_processed = self._total_processed
        else:
            total_processed = len(self._processed_urls)
        
        if error_count > 0:
            logger.info(f"Batch complete: {success_count}/{len(content_batch)} successful, {error_count} errors | Total processed: {total_processed}")
        else:
            logger.info(f"Batch complete: {success_count}/{len(content_batch)} successful | Total processed: {total_processed}")
        
    async def _analyze_single_content(self, content_data: Dict) -> Optional[Dict]:
        """Analyze a single piece of content"""
        try:
            # Prepare enriched metadata for analysis
            metadata = content_data.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
                    
            # Add company enrichment data to metadata
            metadata.update({
                'company_name': content_data.get('company_name'),
                'company_domain': content_data.get('company_domain'),
                'industry': content_data.get('industry'),
                'company_size': content_data.get('company_size'),
                'source_type': content_data.get('source_type')
            })
            
            # Analyze content
            result = await self.analyzer.analyze_content(
                url=content_data['url'],
                content=content_data['content'],
                title=content_data.get('title', ''),
                project_id=self.project_id,
                metadata=metadata
            )
            
            if result:
                # Update pipeline metrics
                await self._update_pipeline_metrics()
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze {content_data['url']}: {e}")
            return None
            
    async def _update_pipeline_metrics(self):
        """Update pipeline metrics for content analyzed"""
        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE pipeline_executions
                    SET content_analyzed = content_analyzed + 1
                    WHERE id = $1
                    """,
                    self.pipeline_id
                )
        except Exception as e:
            logger.error(f"Failed to update pipeline metrics: {e}")
            
    async def get_analysis_stats(self) -> Dict:
        """Get statistics about the concurrent analysis"""
        # If not initialized yet, return zeros to avoid attribute errors
        if not self.pipeline_id:
            return {
                'total_scraped': 0,
                'total_enriched': 0,
                'total_analyzed': 0,
                'pending_analysis': 0,
                'processed_this_session': len(self._processed_urls),
                'is_running': self.is_running
            }

        async with self.db.acquire() as conn:
            # Get stats for all content, not just this pipeline
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(DISTINCT sc.url) as total_scraped,
                    COUNT(DISTINCT cp.domain) as total_enriched,
                    COUNT(DISTINCT oca.url) as total_analyzed,
                    COUNT(DISTINCT CASE 
                        WHEN sc.url IS NOT NULL 
                        AND sc.status = 'completed'
                        AND sc.content IS NOT NULL
                        AND LENGTH(sc.content) > 100
                        AND oca.url IS NULL 
                        THEN sc.url 
                    END) as pending_analysis
                FROM scraped_content sc
                LEFT JOIN company_profiles cp ON cp.domain = sc.domain
                LEFT JOIN optimized_content_analysis oca ON oca.url = sc.url
            """
            )
            
            return {
                'total_scraped': stats['total_scraped'],
                'total_enriched': stats['total_enriched'],
                'total_analyzed': stats['total_analyzed'],
                'pending_analysis': stats['pending_analysis'],
                'processed_this_session': len(self._processed_urls),
                'is_running': self.is_running
            }
