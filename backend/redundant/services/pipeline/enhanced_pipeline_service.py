"""
Enhanced Pipeline Service with Robustness Features
Includes state tracking, circuit breakers, job queue, and retry management
"""

import asyncio
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Set, Tuple
from uuid import UUID, uuid4
from enum import Enum
import json

from loguru import logger
from pydantic import BaseModel

from app.core.database import db_pool, DatabasePool
from app.services.serp.unified_serp_collector import UnifiedSERPCollector as SERPCollector
from app.services.enrichment.company_enricher import CompanyEnricher
from app.services.enrichment.video_enricher import VideoEnricher
from app.services.scraping.web_scraper import WebScraper
from app.services.analysis.content_analyzer import ContentAnalyzer
from app.services.metrics.dsi_calculator import DSICalculator
from app.services.historical_data_service import HistoricalDataService
from app.services.landscape.production_landscape_calculator import ProductionLandscapeCalculator
from app.services.websocket_service import WebSocketService

# Robustness imports
from app.services.robustness import (
    CircuitBreakerManager, StateTracker, JobQueueManager, 
    RetryManager, JobPriority, StateStatus
)
from app.core.robustness_logging import get_logger, set_context, clear_context, log_performance


class PipelineMode(str, Enum):
    BATCH_OPTIMIZED = "batch_optimized"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    RESUME = "resume"  # New mode for resuming failed pipelines


class PipelinePhase(str, Enum):
    KEYWORD_METRICS_ENRICHMENT = "keyword_metrics_enrichment"
    SERP_COLLECTION = "serp_collection"
    COMPANY_ENRICHMENT = "company_enrichment"
    VIDEO_ENRICHMENT = "video_enrichment"
    CONTENT_SCRAPING = "content_scraping"
    CONTENT_ANALYSIS = "content_analysis"
    DSI_CALCULATION = "dsi_calculation"
    HISTORICAL_SNAPSHOT = "historical_snapshot"
    LANDSCAPE_DSI_CALCULATION = "landscape_dsi_calculation"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # New status for partial completion


class PipelineConfig(BaseModel):
    """Enhanced pipeline execution configuration"""
    client_id: str = "system"
    keywords: Optional[List[str]] = None
    regions: List[str] = ["US", "UK"]
    content_types: List[str] = ["organic", "news", "video"]
    
    # Execution settings
    max_concurrent_serp: int = 10
    max_concurrent_enrichment: int = 15
    max_concurrent_analysis: int = 20
    
    # Feature flags
    enable_keyword_metrics: bool = True
    enable_company_enrichment: bool = True
    enable_video_enrichment: bool = True
    enable_content_analysis: bool = True
    enable_historical_tracking: bool = True
    enable_landscape_dsi: bool = True
    force_refresh: bool = False
    
    # Robustness settings
    enable_state_tracking: bool = True
    enable_circuit_breakers: bool = True
    enable_job_queue: bool = True
    enable_checkpoints: bool = True
    checkpoint_interval: int = 100  # Create checkpoint every N items
    
    # Resume settings
    resume_from_pipeline_id: Optional[UUID] = None
    resume_failed_only: bool = True
    
    # Scheduling
    schedule_id: Optional[UUID] = None
    scheduled_for: Optional[datetime] = None


class EnhancedPipelineService:
    """Enhanced pipeline orchestration with robustness features"""
    
    def __init__(self, settings, db: DatabasePool):
        self.settings = settings
        self.db = db
        self.logger = get_logger("pipeline_service")
        
        # Initialize service dependencies
        self.serp_collector = SERPCollector(settings, db)
        self.company_enricher = CompanyEnricher(settings, db)
        self.video_enricher = VideoEnricher(db, settings)
        self.web_scraper = WebScraper(settings, db)
        self.content_analyzer = ContentAnalyzer(settings, db)
        self.dsi_calculator = DSICalculator(settings, db)
        self.landscape_calculator = ProductionLandscapeCalculator(db)
        self.historical_service = HistoricalDataService(db, settings)
        self.websocket_service = WebSocketService()
        
        # Initialize robustness services
        self.state_tracker = StateTracker(db)
        self.circuit_breaker_manager = CircuitBreakerManager(db)
        self.job_queue_manager = JobQueueManager(db)
        self.retry_manager = RetryManager(db)
        
        # Configure circuit breakers for external services
        self._setup_circuit_breakers()
        
        # Configure job queues
        self._setup_job_queues()
        
        # Pipeline state
        self._active_pipelines: Dict[UUID, Any] = {}
        self._lock = asyncio.Lock()
    
    def _setup_circuit_breakers(self):
        """Configure circuit breakers for external services"""
        # Scale SERP API
        self.serp_breaker = self.circuit_breaker_manager.get_breaker(
            "scale_serp_api",
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=300
        )
        
        # Cognism API
        self.cognism_breaker = self.circuit_breaker_manager.get_breaker(
            "cognism_api",
            failure_threshold=5,
            success_threshold=3,
            timeout_seconds=600
        )
        
        # YouTube API
        self.youtube_breaker = self.circuit_breaker_manager.get_breaker(
            "youtube_api",
            failure_threshold=5,
            success_threshold=3,
            timeout_seconds=300
        )
        
        # ScrapingBee API
        self.scraping_breaker = self.circuit_breaker_manager.get_breaker(
            "scrapingbee_api",
            failure_threshold=20,
            success_threshold=10,
            timeout_seconds=300
        )
        
        # OpenAI API
        self.openai_breaker = self.circuit_breaker_manager.get_breaker(
            "openai_api",
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=600
        )
    
    def _setup_job_queues(self):
        """Configure job queues for async processing"""
        # SERP collection queue
        serp_queue = self.job_queue_manager.get_queue("serp_collection")
        serp_queue.register_handler("collect_serp", self._process_serp_job)
        
        # Company enrichment queue
        company_queue = self.job_queue_manager.get_queue("company_enrichment")
        company_queue.register_handler("enrich_company", self._process_company_job)
        
        # Content analysis queue
        analysis_queue = self.job_queue_manager.get_queue("content_analysis")
        analysis_queue.register_handler("analyze_content", self._process_analysis_job)
    
    @log_performance("pipeline_service", "start_pipeline")
    async def start_pipeline(
        self,
        config: PipelineConfig,
        mode: PipelineMode = PipelineMode.BATCH_OPTIMIZED
    ) -> UUID:
        """Start a new pipeline execution with robustness features"""
        pipeline_id = config.resume_from_pipeline_id or uuid4()
        
        # Set logging context
        set_context(
            pipeline_id=str(pipeline_id),
            client_id=config.client_id,
            mode=mode.value
        )
        
        self.logger.info(
            f"Starting pipeline",
            config=config.dict(),
            mode=mode
        )
        
        # Create pipeline result
        result = {
            'pipeline_id': pipeline_id,
            'status': PipelineStatus.PENDING,
            'mode': mode,
            'started_at': datetime.utcnow(),
            'config': config
        }
        
        # Store in memory
        async with self._lock:
            self._active_pipelines[pipeline_id] = result
        
        # Save to database
        await self._save_pipeline_state(result)
        
        # Initialize state tracking if enabled
        if config.enable_state_tracking and mode != PipelineMode.RESUME:
            await self._initialize_state_tracking(pipeline_id, config)
        
        # Start execution
        if config.enable_job_queue:
            # Queue the pipeline for async execution
            await self.job_queue_manager.get_queue("pipeline_execution").enqueue(
                job_type="execute_pipeline",
                payload={
                    'pipeline_id': str(pipeline_id),
                    'config': config.dict()
                },
                priority=JobPriority.HIGH
            )
        else:
            # Execute directly
            asyncio.create_task(self._execute_pipeline_with_robustness(pipeline_id, config))
        
        return pipeline_id
    
    async def _initialize_state_tracking(self, pipeline_id: UUID, config: PipelineConfig):
        """Initialize granular state tracking"""
        # Get all items to process
        items = []
        
        # Keywords for SERP phases
        keywords = await self._get_keywords(config)
        for keyword in keywords:
            for region in config.regions:
                for content_type in config.content_types:
                    items.append({
                        'type': 'keyword_region_type',
                        'keyword': keyword['keyword'],
                        'keyword_id': keyword['id'],
                        'region': region,
                        'content_type': content_type,
                        'metadata': {
                            'category': keyword.get('category'),
                            'jtbd_stage': keyword.get('jtbd_stage')
                        }
                    })
        
        # Initialize states for all phases
        phases = [
            PipelinePhase.SERP_COLLECTION,
            PipelinePhase.COMPANY_ENRICHMENT,
            PipelinePhase.VIDEO_ENRICHMENT,
            PipelinePhase.CONTENT_SCRAPING,
            PipelinePhase.CONTENT_ANALYSIS
        ]
        
        await self.state_tracker.initialize_pipeline(pipeline_id, phases, items)
        
        self.logger.info(
            f"Initialized state tracking",
            pipeline_id=str(pipeline_id),
            total_items=len(items),
            phases=len(phases)
        )
    
    async def _execute_pipeline_with_robustness(self, pipeline_id: UUID, config: PipelineConfig):
        """Execute pipeline with all robustness features"""
        result = self._active_pipelines[pipeline_id]
        
        try:
            result['status'] = PipelineStatus.RUNNING
            await self._save_pipeline_state(result)
            await self._broadcast_status(pipeline_id, "Pipeline started with robustness features")
            
            # Phase 1: SERP Collection
            if config.mode == PipelineMode.RESUME:
                self.logger.info("Resuming pipeline from previous state")
            
            serp_result = await self._execute_serp_phase_robust(pipeline_id, config)
            result['serp_results'] = serp_result
            
            # Create checkpoint after SERP
            if config.enable_checkpoints:
                await self.state_tracker.create_checkpoint(
                    pipeline_id,
                    PipelinePhase.SERP_COLLECTION,
                    "serp_complete",
                    {'unique_domains': serp_result.get('unique_domains', [])}
                )
            
            # Phase 2: Company Enrichment
            if config.enable_company_enrichment and serp_result.get('unique_domains'):
                company_result = await self._execute_company_phase_robust(
                    pipeline_id, 
                    serp_result['unique_domains'],
                    config
                )
                result['company_results'] = company_result
            
            # Phase 3: Content Analysis
            if config.enable_content_analysis:
                analysis_result = await self._execute_analysis_phase_robust(
                    pipeline_id,
                    config
                )
                result['analysis_results'] = analysis_result
            
            # Phase 4: DSI Calculation
            dsi_result = await self._execute_dsi_phase_robust(pipeline_id, config)
            result['dsi_results'] = dsi_result
            
            # Complete pipeline
            result['status'] = PipelineStatus.COMPLETED
            result['completed_at'] = datetime.utcnow()
            
            # Get final statistics
            if config.enable_state_tracking:
                progress = await self.state_tracker.get_pipeline_progress(pipeline_id)
                result['progress'] = progress
                
                # Check if partially complete
                if progress.get('failed_items', 0) > 0:
                    result['status'] = PipelineStatus.PARTIAL
            
            await self._broadcast_status(
                pipeline_id, 
                f"Pipeline completed: {result['status'].value}"
            )
            
        except Exception as e:
            result['status'] = PipelineStatus.FAILED
            result['completed_at'] = datetime.utcnow()
            result['error'] = str(e)
            
            self.logger.error(
                "Pipeline failed",
                error=e,
                pipeline_id=str(pipeline_id)
            )
            
            await self._broadcast_status(pipeline_id, f"Pipeline failed: {str(e)}")
        
        finally:
            await self._save_pipeline_state(result)
            clear_context()
    
    async def _execute_serp_phase_robust(
        self, 
        pipeline_id: UUID, 
        config: PipelineConfig
    ) -> Dict[str, Any]:
        """Execute SERP collection with robustness features"""
        self.logger.info("Starting SERP collection phase")
        
        if config.enable_state_tracking:
            # Get pending items from state tracker
            items = await self.state_tracker.get_pending_items(
                pipeline_id,
                PipelinePhase.SERP_COLLECTION,
                limit=1000
            )
        else:
            # Traditional approach
            items = await self._get_serp_items(config)
        
        unique_domains = set()
        video_urls = set()
        content_urls = set()
        processed = 0
        
        # Process with circuit breaker and retry
        async def process_serp_item(item: Dict[str, Any]):
            nonlocal processed
            
            # Update state to processing
            if config.enable_state_tracking:
                await self.state_tracker.update_state(
                    item['state_id'],
                    StateStatus.PROCESSING
                )
            
            try:
                # Use circuit breaker for SERP API call
                results = await self.serp_breaker.call(
                    self._collect_serp_with_retry,
                    item,
                    config,
                    fallback=lambda *args: []  # Return empty on circuit open
                )
                
                # Process results
                for result in results:
                    unique_domains.add(result['domain'])
                    if 'youtube.com' in result['url']:
                        video_urls.add(result['url'])
                    else:
                        content_urls.add(result['url'])
                
                # Update state to completed
                if config.enable_state_tracking:
                    await self.state_tracker.update_state(
                        item['state_id'],
                        StateStatus.COMPLETED,
                        progress_data={'results_count': len(results)}
                    )
                
                processed += 1
                
            except Exception as e:
                # Update state to failed
                if config.enable_state_tracking:
                    await self.state_tracker.update_state(
                        item['state_id'],
                        StateStatus.FAILED,
                        error=str(e),
                        error_category='serp_collection'
                    )
                raise
        
        # Process items with concurrency control
        semaphore = asyncio.Semaphore(config.max_concurrent_serp)
        
        async def limited_process(item):
            async with semaphore:
                await process_serp_item(item)
        
        # Process all items
        tasks = [limited_process(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count failures
        failures = sum(1 for r in results if isinstance(r, Exception))
        
        self.logger.info(
            f"SERP collection completed",
            processed=processed,
            failures=failures,
            unique_domains=len(unique_domains)
        )
        
        return {
            'items_processed': len(items),
            'items_succeeded': processed,
            'items_failed': failures,
            'unique_domains': list(unique_domains),
            'video_urls': list(video_urls),
            'content_urls': list(content_urls)
        }
    
    async def _collect_serp_with_retry(self, item: Dict[str, Any], config: PipelineConfig):
        """Collect SERP with retry logic"""
        return await self.retry_manager.retry_with_backoff(
            self.serp_collector.collect_serp_results,
            item['keyword'],
            item['keyword_id'],
            item['region'],
            item['content_type'],
            force_refresh=config.force_refresh,
            entity_type='serp_collection',
            entity_id=item.get('state_id', str(item))
        )
    
    async def _execute_company_phase_robust(
        self,
        pipeline_id: UUID,
        domains: List[str],
        config: PipelineConfig
    ) -> Dict[str, Any]:
        """Execute company enrichment with robustness"""
        self.logger.info("Starting company enrichment phase")
        
        enriched = 0
        failures = 0
        
        async def enrich_domain(domain: str):
            nonlocal enriched, failures
            
            try:
                # Use circuit breaker for Cognism API
                result = await self.cognism_breaker.call(
                    self.retry_manager.retry_with_backoff,
                    self.company_enricher.enrich_domain,
                    domain,
                    entity_type='company_enrichment',
                    entity_id=domain
                )
                
                if result:
                    enriched += 1
                    
            except Exception as e:
                failures += 1
                self.logger.error(f"Failed to enrich {domain}", error=e)
        
        # Process with concurrency control
        semaphore = asyncio.Semaphore(config.max_concurrent_enrichment)
        
        async def limited_enrich(domain):
            async with semaphore:
                await enrich_domain(domain)
        
        tasks = [limited_enrich(domain) for domain in domains]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'domains_processed': len(domains),
            'domains_enriched': enriched,
            'domains_failed': failures
        }
    
    async def _execute_analysis_phase_robust(
        self,
        pipeline_id: UUID,
        config: PipelineConfig
    ) -> Dict[str, Any]:
        """Execute content analysis with robustness"""
        self.logger.info("Starting content analysis phase")
        
        # Get unanalyzed content
        content_items = await self._get_unanalyzed_content()
        
        analyzed = 0
        failures = 0
        
        async def analyze_content_item(content: Dict[str, Any]):
            nonlocal analyzed, failures
            
            try:
                # Use circuit breaker for OpenAI API
                result = await self.openai_breaker.call(
                    self.retry_manager.retry_with_backoff,
                    self.content_analyzer.analyze_content,
                    url=content['url'],
                    content=content['content'],
                    title=content.get('title'),
                    entity_type='content_analysis',
                    entity_id=content['url']
                )
                
                if result:
                    analyzed += 1
                    
            except Exception as e:
                failures += 1
                self.logger.error(f"Failed to analyze {content['url']}", error=e)
        
        # Process with concurrency control
        semaphore = asyncio.Semaphore(config.max_concurrent_analysis)
        
        async def limited_analyze(content):
            async with semaphore:
                await analyze_content_item(content)
        
        # Create checkpoints periodically
        checkpoint_batch = []
        for i, content in enumerate(content_items):
            checkpoint_batch.append(content)
            
            if len(checkpoint_batch) >= config.checkpoint_interval:
                # Process batch
                tasks = [limited_analyze(c) for c in checkpoint_batch]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Create checkpoint
                if config.enable_checkpoints:
                    await self.state_tracker.create_checkpoint(
                        pipeline_id,
                        PipelinePhase.CONTENT_ANALYSIS,
                        f"batch_{i//config.checkpoint_interval}",
                        {'analyzed': analyzed, 'failed': failures}
                    )
                
                checkpoint_batch = []
        
        # Process remaining
        if checkpoint_batch:
            tasks = [limited_analyze(c) for c in checkpoint_batch]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'content_processed': len(content_items),
            'content_analyzed': analyzed,
            'content_failed': failures
        }
    
    async def _execute_dsi_phase_robust(
        self,
        pipeline_id: UUID,
        config: PipelineConfig
    ) -> Dict[str, Any]:
        """Execute DSI calculation with robustness"""
        try:
            result = await self.retry_manager.retry_with_backoff(
                self.dsi_calculator.calculate_dsi_rankings,
                max_attempts=3,
                entity_type='dsi_calculation',
                entity_id=str(pipeline_id)
            )
            
            return {
                'success': True,
                'companies_ranked': result.get('companies_ranked', 0),
                'pages_ranked': result.get('pages_ranked', 0)
            }
        except Exception as e:
            self.logger.error("DSI calculation failed", error=e)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def resume_pipeline(
        self,
        pipeline_id: UUID,
        resume_failed_only: bool = True
    ) -> UUID:
        """Resume a failed or partial pipeline"""
        self.logger.info(
            f"Resuming pipeline",
            pipeline_id=str(pipeline_id),
            resume_failed_only=resume_failed_only
        )
        
        # Load previous configuration
        previous_state = await self._load_pipeline_state(pipeline_id)
        if not previous_state:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        config = PipelineConfig(**previous_state.get('config', {}))
        config.resume_from_pipeline_id = pipeline_id
        config.resume_failed_only = resume_failed_only
        
        # Reset failed items if requested
        if resume_failed_only:
            reset_count = await self.state_tracker.reset_failed_items(pipeline_id)
            self.logger.info(f"Reset {reset_count} failed items for retry")
        
        # Start pipeline in resume mode
        return await self.start_pipeline(config, PipelineMode.RESUME)
    
    async def get_pipeline_metrics(self, pipeline_id: UUID) -> Dict[str, Any]:
        """Get detailed metrics for a pipeline"""
        metrics = {}
        
        # Get state tracking progress
        if pipeline_id in self._active_pipelines:
            config = self._active_pipelines[pipeline_id].get('config')
            if config and config.enable_state_tracking:
                progress = await self.state_tracker.get_pipeline_progress(pipeline_id)
                metrics['progress'] = progress
                
                # Get failed items
                failed_items = await self.state_tracker.get_failed_items(pipeline_id)
                metrics['failed_items'] = failed_items
        
        # Get circuit breaker metrics
        breaker_metrics = await self.circuit_breaker_manager.get_all_metrics()
        metrics['circuit_breakers'] = breaker_metrics
        
        # Get job queue metrics
        queue_metrics = await self.job_queue_manager.get_all_stats()
        metrics['job_queues'] = queue_metrics
        
        # Get retry statistics
        retry_stats = await self.retry_manager.get_retry_statistics()
        metrics['retry_stats'] = retry_stats
        
        return metrics
    
    # Job handlers for async processing
    async def _process_serp_job(self, payload: Dict[str, Any]):
        """Process SERP collection job"""
        item = payload['item']
        config = PipelineConfig(**payload['config'])
        
        return await self._collect_serp_with_retry(item, config)
    
    async def _process_company_job(self, payload: Dict[str, Any]):
        """Process company enrichment job"""
        domain = payload['domain']
        return await self.company_enricher.enrich_domain(domain)
    
    async def _process_analysis_job(self, payload: Dict[str, Any]):
        """Process content analysis job"""
        return await self.content_analyzer.analyze_content(
            url=payload['url'],
            content=payload['content'],
            title=payload.get('title')
        )
    
    # Helper methods
    async def _get_keywords(self, config: PipelineConfig) -> List[Dict]:
        """Get keywords based on config"""
        if config.keywords:
            return await self._get_keywords_by_text(config.keywords)
        else:
            return await self._get_all_keywords()
    
    async def _get_keywords_by_text(self, keyword_texts: List[str]) -> List[Dict]:
        """Get keyword records by text"""
        async with self.db.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT id, keyword, category, jtbd_stage
                FROM keywords 
                WHERE keyword = ANY($1::text[])
                """,
                keyword_texts
            )
            return [dict(row) for row in results]
    
    async def _get_all_keywords(self) -> List[Dict]:
        """Get all keyword records"""
        async with self.db.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT id, keyword, category, jtbd_stage
                FROM keywords 
                ORDER BY keyword
                """
            )
            return [dict(row) for row in results]
    
    async def _get_serp_items(self, config: PipelineConfig) -> List[Dict]:
        """Get SERP items without state tracking"""
        keywords = await self._get_keywords(config)
        items = []
        
        for keyword in keywords:
            for region in config.regions:
                for content_type in config.content_types:
                    items.append({
                        'keyword': keyword['keyword'],
                        'keyword_id': keyword['id'],
                        'region': region,
                        'content_type': content_type
                    })
        
        return items
    
    async def _get_unanalyzed_content(self) -> List[Dict]:
        """Get content that hasn't been analyzed"""
        async with self.db.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT sc.url, sc.title, sc.content
                FROM scraped_content sc
                LEFT JOIN content_analysis ca ON sc.url = ca.url
                WHERE sc.status = 'completed' 
                AND sc.content IS NOT NULL 
                AND ca.id IS NULL
                ORDER BY sc.scraped_at DESC
                LIMIT 1000
                """
            )
            return [dict(row) for row in results]
    
    async def _save_pipeline_state(self, result: Dict[str, Any]):
        """Save pipeline state to database"""
        # Implementation similar to original but with additional fields
        pass
    
    async def _load_pipeline_state(self, pipeline_id: UUID) -> Optional[Dict[str, Any]]:
        """Load pipeline state from database"""
        # Implementation to load pipeline state
        pass
    
    async def _broadcast_status(self, pipeline_id: UUID, message: str):
        """Broadcast status update via WebSocket"""
        await self.websocket_service.broadcast_to_channel(
            f"pipeline_{pipeline_id}",
            {
                "type": "pipeline_status",
                "pipeline_id": str(pipeline_id),
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
