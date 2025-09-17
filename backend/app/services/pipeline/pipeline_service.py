"""
Unified Pipeline Service - Batch Optimized with Scheduling Support
Consolidates all pipeline variants into a single, configurable service
"""

import asyncio
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Set, Tuple
from uuid import UUID, uuid4
from enum import Enum
import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

from loguru import logger
from pydantic import BaseModel

from app.core.database import db_pool
from app.services.robustness.state_tracker import StateStatus
from app.services.serp.unified_serp_collector import UnifiedSERPCollector
from app.services.enrichment.enhanced_company_enricher import EnhancedCompanyEnricher
from app.services.enrichment.video_enricher import OptimizedVideoEnricher as VideoEnricher
from app.services.enrichment.channel_company_resolver import ChannelCompanyResolver
from app.services.scraping.web_scraper import WebScraper
# from app.services.analysis.content_analyzer import ContentAnalyzer  # Moved to redundant
from app.services.metrics.simplified_dsi_calculator import SimplifiedDSICalculator as DSICalculator
from app.services.keywords.simplified_google_ads_service import SimplifiedGoogleAdsService
from app.services.historical_data_service import HistoricalDataService
from app.services.landscape.production_landscape_calculator import ProductionLandscapeCalculator
from app.services.websocket_service import WebSocketService
from app.services.pipeline.pipeline_phases import PipelinePhaseManager
from app.services.pipeline.flexible_phase_completion import FlexiblePhaseCompletion


class PipelineMode(str, Enum):
    BATCH_OPTIMIZED = "batch_optimized"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    TESTING = "testing"  # Force full pipeline run for testing


class PipelinePhase(str, Enum):
    KEYWORD_METRICS = "keyword_metrics"
    SERP_COLLECTION = "serp_collection"
    COMPANY_ENRICHMENT_SERP = "company_enrichment_serp"
    YOUTUBE_ENRICHMENT = "youtube_enrichment"
    CONTENT_SCRAPING = "content_scraping"
    CONTENT_ANALYSIS = "content_analysis"
    DSI_CALCULATION = "dsi_calculation"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineConfig(BaseModel):
    """Pipeline execution configuration"""
    client_id: str = "system"  # Client ID for data isolation
    keywords: Optional[List[str]] = None  # If None, uses all keywords
    regions: List[str] = ["US", "UK"]
    content_types: List[str] = ["organic", "news", "video"]
    
    # Execution settings
    max_concurrent_serp: int = 10
    max_concurrent_enrichment: int = 15
    max_concurrent_analysis: int = 20
    
    # Scheduling settings
    is_initial_run: bool = False  # True for first/manual runs to get historical data
    schedule_id: Optional[UUID] = None  # Reference to pipeline schedule if scheduled
    scheduled_for: Optional[datetime] = None
    
    # Feature flags
    enable_keyword_metrics: bool = True
    enable_serp_collection: bool = True  # Set to False when processing webhook results
    enable_company_enrichment: bool = True
    enable_video_enrichment: bool = True
    enable_content_scraping: bool = True  # Enable web content scraping
    enable_content_analysis: bool = True
    enable_historical_tracking: bool = True
    enable_landscape_dsi: bool = True
    force_refresh: bool = False
    
    # Testing mode configuration
    testing_mode: bool = False  # When True, forces full pipeline run regardless of data freshness
    testing_batch_size: Optional[int] = None  # Limit batch size for faster testing (e.g., 5 keywords)
    testing_skip_delays: bool = False  # Skip rate limiting delays in testing mode
    
    # Webhook-specific configuration
    serp_batch_id: Optional[str] = None  # ScaleSERP batch ID for webhook-triggered pipelines
    serp_result_set_id: Optional[int] = None  # ScaleSERP result set ID for webhook-triggered pipelines
    serp_download_links: Optional[Dict[str, Any]] = None  # ScaleSERP download links for webhook-triggered pipelines
    
    # SERP reuse configuration
    reuse_serp_from_pipeline_id: Optional[UUID] = None  # Copy SERP results from previous successful pipeline


class PipelineResult(BaseModel):
    """Pipeline execution result"""
    pipeline_id: UUID
    status: PipelineStatus
    mode: PipelineMode
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Configuration details
    content_types: List[str] = []
    regions: List[str] = []
    current_phase: Optional[str] = None
    phases_completed: List[str] = []
    
    # Phase results
    phase_results: Dict[str, Dict[str, Any]] = {}
    
    # Summary statistics
    keywords_processed: int = 0
    keywords_with_metrics: int = 0
    serp_results_collected: int = 0
    companies_enriched: int = 0
    videos_enriched: int = 0
    content_analyzed: int = 0
    landscapes_calculated: int = 0
    
    # Errors
    errors: List[str] = []
    warnings: List[str] = []
    
    # Resources used
    api_calls_made: Dict[str, int] = {}
    estimated_cost: float = 0.0


class PipelineService:
    """Unified pipeline orchestration service"""
    
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db
        
        # Initialize service dependencies with robustness integration
        from app.services.robustness import CircuitBreakerManager, StateTracker, JobQueueManager, RetryManager, PhaseOrchestrator
        
        # Initialize robustness services
        self.state_tracker = StateTracker(db)
        self.circuit_breaker_manager = CircuitBreakerManager(db)
        self.job_queue_manager = JobQueueManager(db)
        self.retry_manager = RetryManager(db)
        self.phase_orchestrator = PhaseOrchestrator(db)
        
        # Register phase handlers with orchestrator
        self._register_phase_handlers()
        
        # Initialize core services with circuit breaker protection
        serp_circuit_breaker = self.circuit_breaker_manager.get_breaker(
            "scale_serp_api",
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=300
        )
        
        # Initialize unified SERP collector with robustness features
        self.serp_collector = UnifiedSERPCollector(
            settings=settings, 
            db=db,
            circuit_breaker=self.circuit_breaker_manager.get_breaker("scale_serp") if self.circuit_breaker_manager else None,
            retry_manager=self.retry_manager
        )
        # Enable circuit breaker for company enrichment to prevent cascading failures
        self.company_enricher = EnhancedCompanyEnricher(
            settings, db, 
            circuit_breaker=self.circuit_breaker_manager.get_breaker(
                "company_enrichment",
                failure_threshold=10,
                success_threshold=5,
                timeout_seconds=300
            ) if self.circuit_breaker_manager else None,
            retry_manager=self.retry_manager
        )
        self.video_enricher = VideoEnricher(db, settings)
        self.web_scraper = WebScraper(settings, db)
        # Use Optimized Unified Analyzer for reduced verbosity and better performance
        from app.services.analysis.optimized_unified_analyzer import OptimizedUnifiedAnalyzer
        self.content_analyzer = OptimizedUnifiedAnalyzer(settings, db)
        # Concurrent content analyzer for real-time analysis
        from app.services.analysis.concurrent_content_analyzer import ConcurrentContentAnalyzer
        self.concurrent_content_analyzer = ConcurrentContentAnalyzer(settings, db)
        self.dsi_calculator = DSICalculator(settings, db)
        self.google_ads_service = SimplifiedGoogleAdsService()
        self.landscape_calculator = ProductionLandscapeCalculator(db)
        self.historical_service = HistoricalDataService(db, settings)
        self.websocket_service = WebSocketService()
        # Background channel resolver
        self.channel_resolver = ChannelCompanyResolver(db=self.db, settings=self.settings)
        
        # Pipeline state
        self._active_pipelines: Dict[UUID, PipelineResult] = {}
        self._lock = asyncio.Lock()
    
    def _register_phase_handlers(self):
        """Register all phase handlers with orchestrator"""
        self.phase_orchestrator.register_phase_handler(
            "keyword_metrics", 
            self._execute_keyword_metrics_enrichment_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "serp_collection",
            self._execute_serp_collection_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "company_enrichment_serp",
            lambda: self._execute_company_enrichment_phase(self._get_unique_serp_domains())
        )
        self.phase_orchestrator.register_phase_handler(
            "youtube_enrichment",
            lambda: self._execute_video_enrichment_phase(self._get_video_urls_from_serp())
        )
        self.phase_orchestrator.register_phase_handler(
            "content_scraping",
            lambda: self._execute_content_scraping_phase(self._get_content_urls_from_serp())
        )
        self.phase_orchestrator.register_phase_handler(
            "content_analysis",
            self._execute_content_analysis_phase
        )
        self.phase_orchestrator.register_phase_handler(
            "dsi_calculation",
            self._execute_dsi_calculation_phase
        )

    async def _get_phase_statuses(self, pipeline_id: UUID) -> Dict[str, str]:
        """Fetch current statuses for all phases for a given pipeline."""
        try:
            async with self.db.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT phase_name, status::text AS status
                    FROM pipeline_phase_status
                    WHERE pipeline_execution_id = $1
                    """,
                    pipeline_id,
                )
                return {row["phase_name"]: row["status"] for row in rows}
        except Exception as e:
            logger.warning(f"Failed to fetch phase statuses for {pipeline_id}: {e}")
            return {}

    async def _is_phase_completed(self, pipeline_id: UUID, phase_name: str) -> bool:
        statuses = await self._get_phase_statuses(pipeline_id)
        return statuses.get(phase_name) == "completed"
    
    async def start_pipeline(
        self,
        config: PipelineConfig,
        mode: PipelineMode = PipelineMode.BATCH_OPTIMIZED
    ) -> UUID:
        """Start a new pipeline execution"""
        pipeline_id = uuid4()
        
        # Override mode if testing mode is enabled
        if config.testing_mode:
            mode = PipelineMode.TESTING
            logger.info(f"🧪 Testing mode enabled - forcing full pipeline run")
            
            # Force all phases to be enabled in testing mode
            config.enable_keyword_metrics = True
            config.enable_company_enrichment = True
            config.enable_video_enrichment = True
            config.enable_content_scraping = True
            config.enable_content_analysis = True
            config.enable_historical_tracking = True
            config.enable_landscape_dsi = True
            config.force_refresh = True  # Force data refresh
            
            if config.testing_batch_size:
                logger.info(f"🧪 Testing mode: limiting to {config.testing_batch_size} keywords")
        
        # Create pipeline result
        result = PipelineResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.PENDING,
            mode=mode,
            started_at=datetime.utcnow(),
            content_types=config.content_types,
            regions=config.regions
        )
        
        # Store in memory and database
        async with self._lock:
            self._active_pipelines[pipeline_id] = result
        
        await self._save_pipeline_state(result)
        
        # Start execution in background
        asyncio.create_task(self._execute_pipeline(pipeline_id, config))
        
        logger.info(f"Pipeline {pipeline_id} started in {mode} mode")
        return pipeline_id

    async def resume_pipeline(self, pipeline_id: UUID, config: Optional[PipelineConfig] = None) -> bool:
        """Resume an existing pipeline from where it left off."""
        # Load prior state
        prior = await self._load_pipeline_state(pipeline_id)
        if not prior:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        # Prepare config if not provided (basic default)
        if config is None:
            config = PipelineConfig()

        # Put in active set and mark running
        async with self._lock:
            self._active_pipelines[pipeline_id] = prior
        prior.status = PipelineStatus.RUNNING
        await self._save_pipeline_state(prior)

        # Continue execution in background; completed phases will be skipped by gating checks
        asyncio.create_task(self._execute_pipeline(pipeline_id, config))
        logger.info(f"Resuming pipeline {pipeline_id}")
        return True
    
    async def get_pipeline_status(self, pipeline_id: UUID) -> Optional[PipelineResult]:
        """Get current pipeline status"""
        if pipeline_id in self._active_pipelines:
            return self._active_pipelines[pipeline_id]
        
        # Load from database if not in memory
        return await self._load_pipeline_state(pipeline_id)
    
    async def cancel_pipeline(self, pipeline_id: UUID) -> bool:
        """Cancel running pipeline"""
        if pipeline_id not in self._active_pipelines:
            return False
        
        result = self._active_pipelines[pipeline_id]
        if result.status not in [PipelineStatus.PENDING, PipelineStatus.RUNNING]:
            return False
        
        result.status = PipelineStatus.CANCELLED
        result.completed_at = datetime.utcnow()
        await self._save_pipeline_state(result)
        
        logger.info(f"Pipeline {pipeline_id} cancelled")
        return True
    
    async def _copy_serp_from_pipeline(self, config: PipelineConfig, current_pipeline_id: UUID, source_pipeline_id: UUID) -> Optional[Dict[str, Any]]:
        """Copy SERP results from a previous successful pipeline"""
        try:
            async with self.db.acquire() as conn:
                # First, verify the source pipeline has completed SERP collection successfully
                source_pipeline = await conn.fetchrow(
                    """
                    SELECT status, serp_results_collected, started_at
                    FROM pipeline_executions 
                    WHERE id = $1
                    """, 
                    source_pipeline_id
                )
                
                if not source_pipeline:
                    logger.error(f"Source pipeline {source_pipeline_id} not found")
                    return None
                    
                if source_pipeline['serp_results_collected'] == 0:
                    logger.error(f"Source pipeline {source_pipeline_id} has no SERP results to copy")
                    return None
                
                logger.info(f"🔄 Copying {source_pipeline['serp_results_collected']} SERP results from pipeline {source_pipeline_id}")
                
                # Copy SERP results with new pipeline reference
                copied_count = await conn.fetchval(
                    """
                    INSERT INTO serp_results (
                        keyword, region, content_type, rank, title, url, description,
                        displayed_url, favicon_url, snippet, is_sponsored,
                        additional_data, scraped_at, created_at, pipeline_execution_id
                    )
                    SELECT 
                        sr.keyword, sr.region, sr.content_type, sr.rank, sr.title, sr.url, sr.description,
                        sr.displayed_url, sr.favicon_url, sr.snippet, sr.is_sponsored,
                        sr.additional_data, sr.scraped_at, NOW(), $2
                    FROM serp_results sr
                    WHERE sr.pipeline_execution_id = $1
                    RETURNING (SELECT COUNT(*) FROM (SELECT 1) AS dummy)
                    """,
                    source_pipeline_id, current_pipeline_id
                )
                
                if copied_count > 0:
                    logger.info(f"✅ Successfully copied {copied_count} SERP results")
                    
                    return {
                        "total_results": copied_count,
                        "keywords_processed": len(config.keywords or []),
                        "batches_completed": 1,
                        "status": "reused_from_pipeline",
                        "source_pipeline_id": str(source_pipeline_id)
                    }
                else:
                    logger.warning(f"⚠️ No SERP results found to copy from pipeline {source_pipeline_id}")
                    return None
                
        except Exception as e:
            logger.error(f"Failed to copy SERP results from pipeline {source_pipeline_id}: {e}")
            return None
    
    async def _get_existing_serp_results(self, config: PipelineConfig, pipeline_id: UUID) -> Dict[str, Any]:
        """Get count of existing SERP results for webhook-triggered pipelines"""
        try:
            async with self.db.acquire() as conn:
                # Get count of SERP results for this pipeline
                count_result = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as total_results,
                           COUNT(DISTINCT k.keyword) as keywords_processed,
                           COUNT(DISTINCT sr.domain) as unique_domains,
                           COUNT(DISTINCT CASE WHEN sr.url LIKE '%youtube.com%' THEN sr.url END) as video_urls,
                           COUNT(DISTINCT CASE WHEN sr.serp_type IN ('organic', 'news') THEN sr.url END) as content_urls
                    FROM serp_results sr
                    LEFT JOIN keywords k ON k.id = sr.keyword_id
                    WHERE sr.pipeline_execution_id = $1
                    """,
                    pipeline_id
                )
                
                # Get unique domains
                domains_result = await conn.fetch(
                    """
                    SELECT DISTINCT domain 
                    FROM serp_results 
                    WHERE pipeline_execution_id = $1
                    AND domain IS NOT NULL
                    LIMIT 1000
                    """,
                    pipeline_id
                )
                
                # Get video URLs
                videos_result = await conn.fetch(
                    """
                    SELECT DISTINCT url 
                    FROM serp_results 
                    WHERE pipeline_execution_id = $1
                    AND url LIKE '%youtube.com%'
                    LIMIT 1000
                    """,
                    pipeline_id
                )
                
                # Get content URLs (for scraping)
                content_result = await conn.fetch(
                    """
                    SELECT DISTINCT url, MIN(position) as min_position
                    FROM serp_results 
                    WHERE pipeline_execution_id = $1
                    AND serp_type IN ('organic', 'news')
                    AND url IS NOT NULL
                    GROUP BY url
                    ORDER BY MIN(position)
                    """,
                    pipeline_id
                )
                
                return {
                    'total_results': count_result['total_results'] or 0,
                    'keywords_processed': count_result['keywords_processed'] or 0,
                    'unique_domains': [row['domain'] for row in domains_result],
                    'video_urls': [row['url'] for row in videos_result],
                    'content_urls': [row['url'] for row in content_result]
                }
        except Exception as e:
            logger.error(f"Failed to get existing SERP results: {str(e)}")
            return {
                'total_results': 0,
                'keywords_processed': 0,
                'unique_domains': [],
                'video_urls': [],
                'content_urls': []
            }
    
    async def _update_pipeline_metrics(self, execution_id: str, **metrics):
        """Update pipeline execution metrics in real-time"""
        try:
            async with self.db.acquire() as conn:
                # Build dynamic update query
                set_clauses = []
                values = []
                for i, (key, value) in enumerate(metrics.items(), 1):
                    set_clauses.append(f"{key} = ${i+1}")
                    values.append(value)
                
                if not set_clauses:
                    return
                
                query = f"""
                    UPDATE pipeline_executions 
                    SET {', '.join(set_clauses)}
                    WHERE id = $1
                """
                
                await conn.execute(query, execution_id, *values)
                logger.info(f"📊 Updated pipeline metrics: {metrics}")
        except Exception as e:
            logger.error(f"Failed to update pipeline metrics: {str(e)}")
    
    async def _execute_pipeline(self, pipeline_id: UUID, config: PipelineConfig):
        """Execute pipeline phases in sequence"""
        result = self._active_pipelines[pipeline_id]
        
        try:
            # Ensure downstream storage (e.g., scraped_content) can associate rows to this run
            try:
                self.current_pipeline_id = pipeline_id
            except Exception:
                pass
            # Propagate project/client context for downstream services (e.g., analyzer)
            try:
                client_id = getattr(config, 'client_id', None)
                # Don't use 'system' as project_id - it's not a valid UUID
                if client_id and client_id != 'system':
                    self.current_project_id = client_id
                else:
                    self.current_project_id = None
            except Exception:
                self.current_project_id = None
            result.status = PipelineStatus.RUNNING
            await self._save_pipeline_state(result)
            await self._broadcast_status(pipeline_id, "Pipeline started")
            
            # Initialize phase tracking - using PhaseOrchestrator phase names
            enabled_phases = []
            if config.enable_keyword_metrics:
                enabled_phases.append("keyword_metrics")
            if config.enable_serp_collection:
                enabled_phases.append("serp_collection")
            if config.enable_company_enrichment:
                enabled_phases.append("company_enrichment_serp")
            if config.enable_video_enrichment:
                enabled_phases.append("youtube_enrichment")
            if config.enable_content_scraping:
                enabled_phases.append("content_scraping")
            if config.enable_content_analysis:
                enabled_phases.append("content_analysis")
            # DSI calculation is always enabled as part of content analysis
            if config.enable_content_analysis:
                enabled_phases.append("dsi_calculation")
            
            # Initialize pipeline phases in the database
            await self.phase_orchestrator.initialize_pipeline(
                pipeline_id,
                enabled_phases,
                config.dict()
            )
            logger.info(f"Initialized {len(enabled_phases)} phases for pipeline {pipeline_id}")
            
            # Helper to update phase status
            async def update_phase_status(phase_name: str, status: str, result: dict = None):
                """Update phase status in database"""
                try:
                    # Safely serialize result data (handle Decimal, UUID, sets, etc.)
                    def _json_default(value):
                        try:
                            from decimal import Decimal
                            from uuid import UUID
                            if isinstance(value, Decimal):
                                return float(value)
                            if isinstance(value, UUID):
                                return str(value)
                            if isinstance(value, set):
                                return list(value)
                        except Exception:
                            pass
                        # Fallback to string representation for unknown objects
                        return str(value)
                    serialized_result = json.dumps(result, default=_json_default) if result else None

                    async with self.db.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE pipeline_phase_status
                            SET status = $3::varchar,
                                updated_at = NOW(),
                                result_data = $4,
                                started_at = CASE WHEN $3 = 'running' THEN NOW() ELSE started_at END,
                                completed_at = CASE WHEN $3 IN ('completed', 'failed') THEN NOW() ELSE completed_at END
                            WHERE pipeline_execution_id = $1 AND phase_name = $2
                            """,
                            pipeline_id,  # Keep as UUID
                            phase_name,
                            status,
                            serialized_result
                        )
                except Exception as e:
                    logger.error(f"Failed to update phase status: {e}")
            
            # Phase 1: Keyword Metrics Enrichment (if enabled)
            if config.enable_keyword_metrics:
                result.current_phase = "keyword_metrics"
                logger.info(f"🎯 Pipeline {pipeline_id}: Starting keyword metrics enrichment")
                logger.info(f"🎯 Config.enable_keyword_metrics = {config.enable_keyword_metrics}")
                await self._broadcast_status(pipeline_id, "Enriching keyword metrics...")
                await update_phase_status("keyword_metrics", "running")
                
                logger.info(f"🎯 About to call _execute_keyword_metrics_enrichment_phase...")
                keyword_metrics_result = await self._execute_keyword_metrics_enrichment_phase(config, pipeline_id)
                logger.info(f"🎯 Keyword metrics phase returned: {keyword_metrics_result}")
                
                result.phase_results[PipelinePhase.KEYWORD_METRICS] = keyword_metrics_result
                result.keywords_with_metrics = keyword_metrics_result.get('keywords_with_metrics', 0)
                await update_phase_status("keyword_metrics", "completed", keyword_metrics_result)
                logger.info(f"🎯 Phase 1 complete, moving to Phase 2...")
            else:
                logger.info(f"🎯 Keyword metrics enrichment DISABLED in config")
            
            # Phase 2: SERP Collection (skip if already completed or reusing from another pipeline)
            if config.enable_serp_collection:
                # Check if SERP collection already completed (e.g., on resume)
                serp_already_completed = False
                try:
                    async with self.db.acquire() as conn:
                        existing = await conn.fetchval(
                            """
                            SELECT status::text FROM pipeline_phase_status
                            WHERE pipeline_execution_id = $1 AND phase_name = 'serp_collection'
                            """,
                            pipeline_id,
                        )
                        serp_already_completed = (existing == 'completed')
                except Exception as e:
                    logger.warning(f"Failed to read serp_collection status: {e}")

                # Check if we should reuse SERP from another pipeline
                if config.reuse_serp_from_pipeline_id and not serp_already_completed:
                    logger.info(f"🔄 PIPELINE PHASE 2: Reusing SERP data from pipeline {config.reuse_serp_from_pipeline_id}")
                    await self._broadcast_status(pipeline_id, "Reusing SERP data from previous pipeline...")
                    await update_phase_status("serp_collection", "running")
                    
                    serp_result = await self._copy_serp_from_pipeline(config, pipeline_id, config.reuse_serp_from_pipeline_id)
                    
                    if serp_result:
                        await update_phase_status("serp_collection", "completed")
                        logger.info(f"✅ SERP data reused successfully from pipeline {config.reuse_serp_from_pipeline_id}")
                    else:
                        logger.warning(f"⚠️ Failed to reuse SERP data, falling back to fresh collection")
                        await self._broadcast_status(pipeline_id, "Fallback: Collecting fresh SERP data...")
                        serp_result = await self._execute_serp_collection_phase(config, pipeline_id)
                elif serp_already_completed:
                    logger.info(f"🔍 PIPELINE PHASE 2: Skipping SERP collection for pipeline {pipeline_id} (already completed)")
                    # Load existing SERP results from the database
                    serp_result = await self._get_existing_serp_results(config, pipeline_id)
                else:
                    result.current_phase = "serp_collection"
                    logger.info(f"🔍 PIPELINE PHASE 2: Starting fresh SERP collection for pipeline {pipeline_id}")
                    logger.info(f"🔍 PIPELINE: About to call _execute_serp_collection_phase with config: {config}")
                    await self._broadcast_status(pipeline_id, "Collecting SERP data...")
                    await update_phase_status("serp_collection", "running")
                    
                    logger.info(f"🔍 CALLING: _execute_serp_collection_phase(config, {pipeline_id})")
                    serp_result = await self._execute_serp_collection_phase(config, pipeline_id)
                # Log only summary counts to avoid huge payloads in logs
                try:
                    serp_log = {
                        'keywords_processed': serp_result.get('keywords_processed', 0),
                        'total_results': serp_result.get('total_results', serp_result.get('total_results_stored', 0)),
                        'total_results_stored': serp_result.get('total_results_stored', serp_result.get('total_results', 0)),
                        'discrete_batches': serp_result.get('discrete_batches', False),
                        'content_type_results': serp_result.get('content_type_results', {}),
                        'batches_created': serp_result.get('batches_created', 0),
                        'regions': serp_result.get('regions', []),
                        'content_types': serp_result.get('content_types', []),
                        'granular_scheduling_enabled': serp_result.get('granular_scheduling_enabled', False),
                        'unique_domains_count': len(serp_result.get('unique_domains', []) or []),
                        'video_urls_count': len(serp_result.get('video_urls', []) or []),
                        'content_urls_count': len(serp_result.get('content_urls', []) or []),
                    }
                    logger.info(f"🔍 SERP PHASE COMPLETED: {serp_log}")
                except Exception:
                    logger.info("🔍 SERP PHASE COMPLETED (summary logged)")

                # Always persist SERP phase completion and summary
                result.phase_results[PipelinePhase.SERP_COLLECTION] = serp_result
                await update_phase_status("serp_collection", "completed", serp_result)
                # Handle both batch and non-batch result formats
                result.serp_results_collected = serp_result.get('total_results', serp_result.get('total_results_stored', 0))
                result.keywords_processed = serp_result.get('keywords_processed', 0)
                
                # Update metrics in real-time
                await self._update_pipeline_metrics(
                    str(pipeline_id),
                    keywords_processed=result.keywords_processed,
                    serp_results_collected=result.serp_results_collected
                )
            else:
                logger.info(f"🔍 PIPELINE PHASE 2: Processing webhook SERP results")
                # For webhook-triggered pipelines, we need to:
                # 1. Fetch the results from the completed ScaleSERP batch
                # 2. Store them in our database
                # 3. Return the same format as regular SERP collection
                
                # Get batch info from config (webhook handler should set this)
                batch_id = getattr(config, 'serp_batch_id', None)
                result_set_id = getattr(config, 'serp_result_set_id', None)
                download_links = getattr(config, 'serp_download_links', None)
                if batch_id:
                    logger.info(f"📥 Fetching and processing results from ScaleSERP batch: {batch_id}, result_set: {result_set_id}")
                    # Use the SERP collector to fetch and store results
                    from app.services.serp.unified_serp_collector import UnifiedSERPCollector
                    serp_collector = UnifiedSERPCollector(self.settings, self.db)
                    
                    # Process the batch results (fetch from ScaleSERP and store)
                    serp_result = await serp_collector.process_webhook_batch(
                        batch_id=batch_id,
                        pipeline_id=str(pipeline_id),
                        content_type=config.content_types[0] if config.content_types else "organic",
                        result_set_id=result_set_id,
                        download_links=download_links
                    )
                else:
                    logger.warning("⚠️ No batch_id provided for webhook pipeline, getting existing results")
                    serp_result = await self._get_existing_serp_results(config, pipeline_id)

                # Persist webhook SERP results and update metrics
                result.phase_results[PipelinePhase.SERP_COLLECTION] = serp_result
                result.serp_results_collected = serp_result.get('total_results', 0)
                result.keywords_processed = serp_result.get('keywords_processed', 0)
                await self._update_pipeline_metrics(
                    str(pipeline_id),
                    keywords_processed=result.keywords_processed,
                    serp_results_collected=result.serp_results_collected
                )
            
            # Check for cancellation
            if result.status == PipelineStatus.CANCELLED:
                return
            
            # Phase 3: Company Enrichment (strictly after SERPs stored for THIS pipeline)
            serp_count = 0
            serp_domains: List[str] = []
            try:
                async with self.db.acquire() as conn:
                    serp_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM serp_results WHERE pipeline_execution_id = $1",
                        pipeline_id,
                    ) or 0
                    if serp_count > 0:
                        domain_rows = await conn.fetch(
                            "SELECT DISTINCT domain FROM serp_results WHERE pipeline_execution_id = $1 AND domain IS NOT NULL",
                            pipeline_id,
                        )
                        serp_domains = [row['domain'] for row in domain_rows]
            except Exception as e:
                logger.error(f"Failed to verify SERP readiness for enrichment: {e}")

            # Require that the SERP phase is marked completed for this pipeline
            serp_phase_completed = False
            try:
                async with self.db.acquire() as conn:
                    status = await conn.fetchval(
                        """
                        SELECT status::text FROM pipeline_phase_status
                        WHERE pipeline_execution_id = $1 AND phase_name = 'serp_collection'
                        """,
                        pipeline_id,
                    )
                    serp_phase_completed = (status == 'completed')
            except Exception as e:
                logger.error(f"Failed to read serp_collection phase status: {e}")

            # Check if company enrichment is already completed
            company_enrichment_completed = await self._is_phase_completed(pipeline_id, "company_enrichment_serp")
            
            if config.enable_company_enrichment and serp_phase_completed and serp_count > 0 and not company_enrichment_completed:
                logger.info(f"Pipeline {pipeline_id}: Starting company enrichment")
                await self._broadcast_status(pipeline_id, "Enriching company data...")
                await update_phase_status("company_enrichment_serp", "running")
                
                # Filter out already enriched domains to avoid re-processing
                domains_to_enrich = serp_domains
                if serp_domains:
                    try:
                        async with self.db.acquire() as conn:
                            # Check which domains are already in company_profiles
                            existing_result = await conn.fetch(
                                """
                                SELECT DISTINCT domain 
                                FROM company_profiles 
                                WHERE domain = ANY($1::text[])
                                """,
                                serp_domains
                            )
                            existing_domains = {row['domain'] for row in existing_result}
                            domains_to_enrich = [d for d in serp_domains if d not in existing_domains]
                            
                            logger.info(f"Company enrichment: {len(serp_domains)} total domains, "
                                      f"{len(existing_domains)} already enriched, "
                                      f"{len(domains_to_enrich)} new domains to process")
                    except Exception as e:
                        logger.warning(f"Failed to filter existing domains, processing all: {e}")
                        domains_to_enrich = serp_domains
                
                # Add error handling and check for empty domain list
                try:
                    if not domains_to_enrich:
                        logger.info("No new domains to enrich, marking phase as complete")
                        enrichment_result = {
                            'success': True,
                            'phase_name': 'company_enrichment_serp',
                            'domains_processed': 0,
                            'companies_enriched': 0,
                            'errors': [],
                            'message': 'All domains already enriched'
                        }
                    else:
                        enrichment_result = await self._execute_company_enrichment_phase(
                            domains_to_enrich
                        )
                except Exception as e:
                    logger.error(f"Company enrichment phase failed: {e}", exc_info=True)
                    enrichment_result = {
                        'success': False,
                        'phase_name': 'company_enrichment_serp',
                        'domains_processed': 0,
                        'companies_enriched': 0,
                        'errors': [str(e)]
                    }
                result.phase_results[PipelinePhase.COMPANY_ENRICHMENT_SERP] = enrichment_result
                result.companies_enriched = enrichment_result.get('companies_enriched', 0)
                await update_phase_status("company_enrichment_serp", "completed", enrichment_result)
                
                # Update metrics in real-time
                await self._update_pipeline_metrics(
                    str(pipeline_id),
                    companies_enriched=result.companies_enriched
                )
            elif config.enable_company_enrichment and company_enrichment_completed:
                logger.info(f"Pipeline {pipeline_id}: Skipping company enrichment (already completed)")
                # Load existing results from database
                async with self.db.acquire() as conn:
                    phase_result = await conn.fetchrow(
                        """
                        SELECT result_data
                        FROM pipeline_phase_status
                        WHERE pipeline_execution_id = $1 AND phase_name = 'company_enrichment_serp'
                        """,
                        pipeline_id
                    )
                    if phase_result and phase_result['result_data']:
                        enrichment_result = phase_result['result_data']
                        result.phase_results[PipelinePhase.COMPANY_ENRICHMENT_SERP] = enrichment_result
                        result.companies_enriched = enrichment_result.get('companies_enriched', 0)
            elif config.enable_company_enrichment:
                # Explicitly block company enrichment until SERP results exist
                block_reason = "SERP collection not completed or no results stored"
                logger.warning(f"Pipeline {pipeline_id}: Blocking company enrichment - {block_reason}")
                await update_phase_status("company_enrichment_serp", "blocked", {
                    'success': False,
                    'blocked_by': 'serp_collection',
                    'reason': block_reason
                })
            
            # Phase 4: Video Enrichment (Non-Critical)
            if config.enable_video_enrichment and serp_result.get('video_urls'):
                result.current_phase = "youtube_enrichment"
                logger.info(f"Pipeline {pipeline_id}: Starting video enrichment (non-critical phase)")
                await self._broadcast_status(pipeline_id, "Enriching video content (optional)...")
                await update_phase_status("youtube_enrichment", "running")
                
                try:
                    # Always start background channel resolver early; inline AI channel resolution is disabled
                    try:
                        if getattr(self.settings, 'CHANNEL_COMPANY_RESOLVER_ENABLED', True):
                            self.channel_resolver.start_background()
                    except Exception:
                        pass
                    video_result = await self._execute_video_enrichment_phase(
                        serp_result['video_urls'],
                        pipeline_execution_id=str(pipeline_id)
                    )
                    result.phase_results[PipelinePhase.YOUTUBE_ENRICHMENT] = video_result
                    result.videos_enriched = video_result.get('videos_enriched', 0)
                    
                    # Only mark as completed if it was successful or processed most videos
                    if video_result.get('success', False):
                        await update_phase_status("youtube_enrichment", "completed", video_result)
                    else:
                        # Mark as skipped instead of failed for non-critical phase
                        await update_phase_status("youtube_enrichment", "skipped", {
                            **video_result,
                            'reason': f"Low success rate: {video_result.get('success_rate', 0):.1f}% (non-critical)"
                        })
                        logger.warning(f"YouTube enrichment had low success rate but continuing pipeline (non-critical)")
                except Exception as e:
                    error_msg = str(e) if hasattr(e, '__str__') else 'Unknown error'
                    logger.warning(f"YouTube enrichment failed (non-critical, continuing): {error_msg}")
                    result.phase_results[PipelinePhase.YOUTUBE_ENRICHMENT] = {
                        'success': False,
                        'videos_enriched': 0,
                        'error': error_msg,
                        'skipped_reason': 'YouTube API error - phase skipped (non-critical)'
                    }
                    await update_phase_status("youtube_enrichment", "skipped", {
                        'error': error_msg,
                        'reason': 'YouTube API error - phase skipped (non-critical)'
                    })
                    # Don't fail the pipeline - YouTube is not critical
                    logger.info(f"Pipeline {pipeline_id}: Continuing despite YouTube enrichment failure (non-critical phase)")
            
            # Phase 5: Content Scraping
            if config.enable_content_scraping and serp_result.get('content_urls'):
                # Check if content scraping is already completed
                scraping_already_completed = await self._is_phase_completed(pipeline_id, "content_scraping")
                
                if scraping_already_completed:
                    logger.info(f"Pipeline {pipeline_id}: Skipping content scraping (already completed)")
                    # Get existing scraping results
                    async with self.db.acquire() as conn:
                        scraped_count = await conn.fetchval("""
                            SELECT COUNT(*) FROM scraped_content 
                            WHERE pipeline_execution_id = $1
                        """, str(pipeline_id))
                    
                    scraping_result = {
                        'urls_total': len(serp_result.get('content_urls', [])),
                        'urls_scraped': scraped_count or 0,
                        'scraped_results': [],
                        'errors': []
                    }
                else:
                    result.current_phase = "content_scraping"
                    logger.info(f"Pipeline {pipeline_id}: Starting content scraping")
                    await self._broadcast_status(pipeline_id, "Scraping web content...")
                    await update_phase_status("content_scraping", "running")
                    
                    # Start concurrent content analyzer in the background
                    if config.enable_content_analysis:
                        logger.info(f"Pipeline {pipeline_id}: Starting concurrent content analysis monitor")
                        await self.concurrent_content_analyzer.start_monitoring(
                            pipeline_id=pipeline_id,
                            project_id=getattr(self, 'current_project_id', None)
                        )
                    
                    scraping_result = await self._execute_content_scraping_phase(
                        serp_result['content_urls']
                    )
                    await update_phase_status("content_scraping", "completed", scraping_result)
                    
                result.phase_results[PipelinePhase.CONTENT_SCRAPING] = scraping_result
                # Scrape phase summary logging (counts by status for this pipeline)
                try:
                    pipeline_id_str = str(pipeline_id)
                    async with db_pool.acquire() as conn:
                        rows = await conn.fetch(
                            """
                            SELECT COALESCE(status,'unknown') AS status, COUNT(*)::int AS cnt
                            FROM scraped_content
                            WHERE pipeline_execution_id = $1
                            GROUP BY COALESCE(status,'unknown')
                            ORDER BY COALESCE(status,'unknown')
                            """,
                            pipeline_id_str,
                        )
                    status_counts = {r['status']: r['cnt'] for r in rows} if rows else {}
                    completed_cnt = status_counts.get('completed', 0)
                    failed_cnt = status_counts.get('failed', 0)
                    unknown_cnt = status_counts.get('unknown', 0)
                    logger.info(
                        f"Scrape summary for pipeline {pipeline_id_str}: "
                        f"total_urls={scraping_result.get('urls_total', 0)}, "
                        f"candidates={scraping_result.get('urls_candidates', 0)}, "
                        f"scraped_completed={completed_cnt}, "
                        f"scraped_failed={failed_cnt}, "
                        f"scraped_unknown={unknown_cnt}, "
                        f"errors_recorded={len(scraping_result.get('errors', []))}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to log scrape summary for pipeline {pipeline_id}: {e}")
            
            # Phase 6: Content Analysis
            # Now we wait for the concurrent analyzer to complete
            if config.enable_content_analysis:
                result.current_phase = "content_analysis"
                logger.info(f"Pipeline {pipeline_id}: Waiting for content analysis to complete")
                await self._broadcast_status(pipeline_id, "Analyzing content with AI...")
                await update_phase_status("content_analysis", "running")
                
                # Wait for all content to be analyzed or timeout
                analysis_result = await self._wait_for_content_analysis_completion(pipeline_id)
                
                # Stop the concurrent analyzer
                await self.concurrent_content_analyzer.stop_monitoring()
                
                result.phase_results[PipelinePhase.CONTENT_ANALYSIS] = analysis_result
                result.content_analyzed = analysis_result.get('content_analyzed', 0)
                content_analysis_success = bool(analysis_result.get('success')) and result.content_analyzed > 0
                await update_phase_status(
                    "content_analysis",
                    "completed" if content_analysis_success else "failed",
                    analysis_result
                )
            
            # Phase 7: DSI Calculation
            # Check all DSI dependencies using PhaseOrchestrator logic
            # DSI depends on: content_analysis, youtube_enrichment
            dsi_dependencies_met = True
            dsi_skip_reasons = []
            
            # Check if we have SERP results (foundation for everything)
            if result.serp_results_collected == 0:
                dsi_dependencies_met = False
                dsi_skip_reasons.append("No SERP results collected")
            
            # Check content_analysis dependency
            if config.enable_content_analysis:
                content_analysis_result = result.phase_results.get(PipelinePhase.CONTENT_ANALYSIS, {})
                # Consider flexible completion as success
                is_flexible_completion = content_analysis_result.get('flexible_completion', False)
                has_analyzed_content = content_analysis_result.get('content_analyzed', 0) > 0
                
                if not content_analysis_result.get('success', False) and not is_flexible_completion:
                    dsi_dependencies_met = False
                    dsi_skip_reasons.append("Content analysis did not complete successfully")
                elif not has_analyzed_content:
                    dsi_dependencies_met = False
                    dsi_skip_reasons.append("No content was analyzed")
            
            # Check company_enrichment dependency (both SERP and YouTube enrichment)
            if config.enable_company_enrichment:
                company_enrichment_result = result.phase_results.get(PipelinePhase.COMPANY_ENRICHMENT_SERP, {})
                if not company_enrichment_result.get('success', False):
                    dsi_dependencies_met = False
                    dsi_skip_reasons.append("Company enrichment (SERP) did not complete successfully")
            
            # Check video enrichment if enabled (Non-Critical - Don't block DSI)
            if config.enable_video_enrichment:
                video_enrichment_result = result.phase_results.get(PipelinePhase.YOUTUBE_ENRICHMENT, {})
                # YouTube enrichment is non-critical - never block DSI calculation
                if not video_enrichment_result and serp_result.get('video_urls'):
                    # No result at all means it didn't run, but don't block DSI
                    logger.warning("Video enrichment did not run, but continuing with DSI (non-critical)")
                elif video_enrichment_result.get('success_rate', 0) < 10 and video_enrichment_result.get('total_videos', 0) > 0:
                    # Low success rate in YouTube is acceptable - it's non-critical
                    logger.warning(f"Video enrichment had low success rate: {video_enrichment_result.get('success_rate', 0):.1f}% (non-critical, not blocking DSI)")
            
            if dsi_dependencies_met:
                logger.info(f"Pipeline {pipeline_id}: Calculating DSI metrics")
                await self._broadcast_status(pipeline_id, "Calculating DSI rankings...")
                await update_phase_status("dsi_calculation", "running")
                
                dsi_result = await self._execute_dsi_calculation_phase()
                result.phase_results[PipelinePhase.DSI_CALCULATION] = dsi_result
                await update_phase_status("dsi_calculation", "completed", dsi_result)
            else:
                logger.warning(f"Pipeline {pipeline_id}: Skipping DSI calculation - dependencies not met")
                for reason in dsi_skip_reasons:
                    logger.warning(f"  - {reason}")
                logger.warning(f"  Current metrics: SERP={result.serp_results_collected}, Companies={result.companies_enriched}, Content={result.content_analyzed}")
                result.phase_results[PipelinePhase.DSI_CALCULATION] = {
                    'success': False,
                    'skipped': True,
                    'reason': 'Dependencies not met',
                    'skip_reasons': dsi_skip_reasons
                }
                await update_phase_status("dsi_calculation", "skipped", {
                    'reason': 'Dependencies not met',
                    'skip_reasons': dsi_skip_reasons
                })
            
            # Phase 8: Historical Snapshot (if enabled)
            if config.enable_historical_tracking:
                logger.info(f"Pipeline {pipeline_id}: Creating historical snapshot")
                await self._broadcast_status(pipeline_id, "Creating historical snapshot...")
                
                snapshot_result = await self._execute_historical_snapshot_phase()
                result.phase_results[PipelinePhase.HISTORICAL_SNAPSHOT] = snapshot_result
            
            # Phase 9: Landscape DSI Calculation (if enabled)
            if config.enable_landscape_dsi and dsi_dependencies_met:
                logger.info(f"Pipeline {pipeline_id}: Calculating Landscape DSI metrics")
                await self._broadcast_status(pipeline_id, "Calculating Digital Landscape DSI metrics...")
                
                landscape_result = await self._execute_landscape_dsi_calculation_phase(config)
                result.phase_results[PipelinePhase.LANDSCAPE_DSI_CALCULATION] = landscape_result
                result.landscapes_calculated = landscape_result.get('landscapes_calculated', 0)
            elif config.enable_landscape_dsi:
                logger.warning(f"Pipeline {pipeline_id}: Skipping Landscape DSI calculation - dependencies not met")
                result.phase_results[PipelinePhase.LANDSCAPE_DSI_CALCULATION] = {
                    'success': False,
                    'skipped': True,
                    'reason': 'Dependencies not met (same as DSI calculation)',
                    'skip_reasons': dsi_skip_reasons
                }
                result.landscapes_calculated = 0
            
            # Complete pipeline with correctness: fail if any enabled phase failed/incomplete or critical deps not met
            final_message = "Pipeline completed successfully!"
            try:
                # Read persisted phase statuses
                async with self.db.acquire() as conn:
                    phase_rows = await conn.fetch(
                        """
                        SELECT phase_name, status::text AS status
                        FROM pipeline_phase_status
                        WHERE pipeline_execution_id = $1
                        """,
                        pipeline_id,
                    )
                status_map = {r['phase_name']: r['status'] for r in phase_rows} if phase_rows else {}

                enabled_set = set(enabled_phases)
                failed_phases = [p for p, s in status_map.items() if p in enabled_set and s in ("failed", "blocked")]
                incomplete_phases = [p for p, s in status_map.items() if p in enabled_set and s in ("pending", "queued", "running")]

                # Critical phase checks
                critical_fail = False
                if "serp_collection" in enabled_set and status_map.get("serp_collection") != "completed":
                    critical_fail = True
                if "content_scraping" in enabled_set and status_map.get("content_scraping") != "completed":
                    critical_fail = True
                if "content_analysis" in enabled_set and status_map.get("content_analysis") != "completed":
                    critical_fail = True
                if "dsi_calculation" in enabled_set and status_map.get("dsi_calculation") != "completed":
                    # DSI is critical when enabled (depends on prior phases)
                    critical_fail = True

                should_fail = bool(failed_phases or incomplete_phases or critical_fail)
                result.status = PipelineStatus.FAILED if should_fail else PipelineStatus.COMPLETED
                if should_fail:
                    reasons = []
                    if failed_phases:
                        reasons.append(f"failed phases: {failed_phases}")
                    if incomplete_phases:
                        reasons.append(f"incomplete phases: {incomplete_phases}")
                    if critical_fail and not (failed_phases or incomplete_phases):
                        reasons.append("critical dependencies not met")
                    final_message = f"Pipeline {'failed' if should_fail else 'completed'} - " + ", ".join(reasons)
            except Exception as e:
                # Conservative default: if content analysis produced zero, mark failed
                logger.warning(f"Final status evaluation error: {e}")
                ca_ok = bool(result.phase_results.get(PipelinePhase.CONTENT_ANALYSIS, {}).get('success')) and \
                        (result.phase_results.get(PipelinePhase.CONTENT_ANALYSIS, {}).get('content_analyzed', 0) > 0)
                result.status = PipelineStatus.COMPLETED if ca_ok else PipelineStatus.FAILED
                if result.status == PipelineStatus.FAILED:
                    final_message = "Pipeline failed - final status evaluation error and content analysis incomplete"

            result.completed_at = datetime.utcnow()
            
            await self._broadcast_status(pipeline_id, final_message)
            logger.info(f"Pipeline {pipeline_id} finished with status={result.status.value}")
            
            # Save final result
            await self._save_pipeline_state(result)
            
        except asyncio.TimeoutError as e:
            result.status = PipelineStatus.FAILED
            result.completed_at = datetime.utcnow()
            current_phase = getattr(result, 'current_phase', 'unknown')
            error_msg = f"Pipeline timed out at phase: {current_phase}"
            result.errors.append(error_msg)
            
            await self._broadcast_status(pipeline_id, error_msg)
            logger.error(f"Pipeline {pipeline_id} failed: {error_msg}")
        except Exception as e:
            result.status = PipelineStatus.FAILED
            result.completed_at = datetime.utcnow()
            error_msg = f"{type(e).__name__}: {str(e)}"
            result.errors.append(error_msg)
            
            # Log with full stack trace for debugging
            logger.error(f"Pipeline {pipeline_id} failed with {type(e).__name__}", exc_info=True)
            await self._broadcast_status(pipeline_id, f"Pipeline failed: {error_msg}")
        
        finally:
            await self._save_pipeline_state(result)
            # Keep in memory for a while for status queries
            asyncio.create_task(self._cleanup_pipeline_after_delay(pipeline_id, 3600))
    
    async def _execute_serp_collection_phase(self, config: PipelineConfig, pipeline_id: UUID) -> Dict[str, Any]:
        """Execute SERP collection phase"""
        logger.info(f"🔍 SERP PHASE START: Collection beginning for pipeline {pipeline_id}")
        logger.info(f"🔍 SERP CONFIG: regions={config.regions}, content_types={config.content_types}, force_refresh={config.force_refresh}")
        logger.info(f"🔍 SERP SETTINGS: max_concurrent={getattr(config, 'max_concurrent_serp', 'default')}")
        
        # Get keywords - either specific ones from API or all project keywords
        if config.keywords:
            logger.info(f"🔍 Looking up specific keywords from project: {config.keywords}")
            keywords = await self._get_keywords_by_text(config.keywords)
            if not keywords:
                logger.error(f"❌ Keywords not found in project database: {config.keywords}")
                logger.error(f"❌ Please ensure these keywords exist in the project")
                return {'keywords_processed': 0, 'total_results': 0, 'message': 'Keywords not found in project database'}
        else:
            logger.info(f"🔍 No specific keywords provided - getting all ACTIVE project keywords")
            keywords = await self._get_all_keywords(active_only=True)
            if not keywords:
                logger.warning(f"⚠️ No keywords found in project database")
                return {'keywords_processed': 0, 'total_results': 0, 'message': 'No keywords in project'}
        
        logger.info(f"🔍 KEYWORDS PREPARED: {len(keywords) if keywords else 0} keywords ready for SERP collection")
        
        # Apply testing mode batch size limit
        if config.testing_mode and config.testing_batch_size and len(keywords) > config.testing_batch_size:
            logger.info(f"🧪 Testing mode: Limiting keywords from {len(keywords)} to {config.testing_batch_size}")
            keywords = keywords[:config.testing_batch_size]
        
        if keywords:
            logger.info(f"🔍 KEYWORDS DETAILS: {[kw['keyword'] for kw in keywords]}")
            logger.info(f"🔍 REGIONS CONFIG: {config.regions}")
            logger.info(f"🔍 CONTENT TYPES CONFIG: {config.content_types}")
        else:
            logger.warning(f"🔍 CRITICAL: No keywords available for SERP - returning early")
            return {'keywords_processed': 0, 'total_results': 0, 'message': 'No keywords available for SERP'}
        
        # Collect SERP results for all keyword-region-type combinations
        total_results = 0
        unique_domains = set()
        video_urls = set()
        content_urls = set()
        
        logger.info(f"🔍 SERP config: regions={config.regions}, content_types={config.content_types}")
        
        semaphore = asyncio.Semaphore(config.max_concurrent_serp)
        
        async def collect_serp(keyword: Dict, region: str, content_type: str):
            nonlocal total_results
            async with semaphore:
                logger.info(f"🔍 SERP: Calling collect_serp_results for {keyword['keyword']} in {region} ({content_type})")
                
                try:
                    results = await self.serp_collector.collect_serp_results(
                        keyword['keyword'],
                        keyword['id'],
                        region,
                        content_type,
                        force_refresh=config.force_refresh
                    )
                    
                    logger.info(f"🔍 SERP: Got {len(results) if results else 0} results for {keyword['keyword']}")
                    
                    if results:
                        for result in results:
                            total_results += 1
                            unique_domains.add(result['domain'])
                            
                            if content_type == 'video' and 'youtube.com' in result['url']:
                                video_urls.add(result['url'])
                            elif content_type in ['organic', 'news']:
                                content_urls.add(result['url'])
                    
                    return len(results) if results else 0
                    
                except Exception as e:
                    logger.error(f"❌ SERP collection failed for {keyword['keyword']} in {region}: {e}")
                    return 0
        
        # 🔧 SINGLE BATCH APPROACH: Add ALL project keywords to one batch
        keyword_texts = [kw['keyword'] for kw in keywords]
        keyword_ids = [kw['id'] for kw in keywords]
        
        total_searches = len(keywords) * len(config.regions) * len(config.content_types)
        logger.info(f"🚀 SERP CONTENT-TYPE BATCHES: Creating separate batches for each content type")
        logger.info(f"🔍 SERP: {len(keywords)} keywords × {len(config.regions)} regions across {len(config.content_types)} content types = {total_searches} total searches")
        logger.info(f"💡 SCHEDULING: Separate batches enable independent scheduling (organic daily, news hourly, video weekly)")
        
        # Create and run batch via Scale SERP batch API with robust monitoring
        from uuid import UUID
        pipeline_uuid = UUID(str(pipeline_id)) if hasattr(self, '_active_pipelines') else None
        
        # Create progress callback for real-time monitoring
        async def serp_progress_callback(event_type: str, data: Dict):
            logger.info(f"📊 SERP PROGRESS: {event_type} - {data}")
            # Broadcast to WebSocket for real-time updates
            if hasattr(self, 'websocket_service'):
                await self.websocket_service.broadcast_to_channel(
                    f"pipeline_{pipeline_id}",
                    {
                        "type": "serp_progress",
                        "event": event_type, 
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        
        # 🔧 CORE APP INTEGRATION: Use application-wide robustness services  
        state_tracker = self.state_tracker
        
        # Initialize SERP items in state tracker for progress tracking
        if state_tracker:
            serp_items = []
            for keyword in keywords:
                for region in config.regions:
                    for content_type in config.content_types:
                        serp_items.append({
                            'type': 'serp_search',
                            'keyword': keyword['keyword'],
                            'keyword_id': keyword['id'],
                            'region': region,
                            'content_type': content_type,
                            'metadata': {'phase': 'serp_collection'}
                        })
            
            try:
                # Check if state tracking already exists for this pipeline
                async with self.db.acquire() as conn:
                    existing_count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM pipeline_state 
                        WHERE pipeline_execution_id = $1 AND phase = 'serp_collection'
                        """,
                        pipeline_id
                    )
                
                if existing_count == 0:
                    # Initialize state tracking for SERP items
                    await state_tracker.initialize_pipeline(
                        pipeline_id, 
                        ["serp_collection"], 
                        serp_items
                    )
                    logger.info(f"🔧 STATE TRACKING: Initialized {len(serp_items)} SERP items for tracking")
                else:
                    logger.info(f"🔧 STATE TRACKING: Found {existing_count} existing SERP items, skipping initialization")
            except Exception as e:
                logger.warning(f"⚠️ STATE TRACKING: Could not initialize state tracking: {str(e)}")
                logger.warning(f"⚠️ Continuing without state tracking for this phase")
        
        # 🚀 CONCURRENT BATCH STRATEGY: Create all batches at once, then monitor concurrently
        content_type_results = {}
        total_stored = 0
        batch_infos = []
        
        logger.info(f"🚀 CONCURRENT BATCHES: Creating {len(config.content_types)} batches in parallel")
        
        # PHASE 1: Create all batches (but don't wait for completion)
        for content_type in config.content_types:
            searches_for_type = len(keywords) * len(config.regions)
            logger.info(f"🚀 PREPARING {content_type.upper()} BATCH: {len(keywords)} keywords × {len(config.regions)} regions = {searches_for_type} searches")
            
            # Load scheduling configuration
            content_scheduler_config = await self._get_content_type_schedule_config(content_type, config)
            content_frequency = content_scheduler_config.get('frequency', 'immediate')
            
            # Calculate time period for news
            news_time_period = None
            if content_type == 'news':
                is_initial_run = getattr(config, 'is_initial_run', False)
                
                frequency_to_time_period = {
                    'daily': 'last_day',
                    'weekly': 'last_week',
                    'monthly': 'last_month',
                    'quarterly': 'last_year',
                    'immediate': 'last_day'
                }
                
                if is_initial_run and content_frequency in ['weekly', 'monthly', 'quarterly']:
                    initial_time_periods = {
                        'weekly': 'last_month',
                        'monthly': 'last_year',
                        'quarterly': 'last_year'
                    }
                    news_time_period = initial_time_periods.get(content_frequency, 'last_month')
                else:
                    news_time_period = frequency_to_time_period.get(content_frequency, 'last_day')
                
                logger.info(f"📰 News time period: '{news_time_period}' for {content_frequency} schedule")
            
            # Get circuit breaker
            serp_circuit_breaker = self.circuit_breaker_manager.get_breaker("scale_serp_api")
            
            try:
                # Create batch WITHOUT waiting for completion
                logger.info(f"🔍 Creating {content_type.upper()} batch...")
                await self._broadcast_status(pipeline_id, f"Creating {content_type} SERP batch...")
                
                batch_result = await serp_circuit_breaker.call(
                    self.serp_collector.create_batch_only,  # New method that doesn't wait
                    keywords=keyword_texts,
                    keyword_ids=keyword_ids,
                    regions=config.regions,
                    content_type=content_type,
                    batch_frequency=content_frequency,
                    scheduler_config=content_scheduler_config,
                    include_html=getattr(config, 'include_html', False),
                    progress_callback=serp_progress_callback,
                    news_time_period=news_time_period if content_type == 'news' else None,
                    fallback=lambda *args, **kwargs: {'success': False, 'error': 'Circuit breaker open'}
                )
                
                if batch_result.get('success'):
                    batch_infos.append({
                        'batch_id': batch_result['batch_id'],
                        'content_type': content_type,
                        'batch_requests': batch_result.get('batch_requests', [])
                    })
                    logger.info(f"✅ {content_type.upper()} batch created: {batch_result['batch_id']}")
                    
                    # Store batch details for recovery after restart
                    try:
                        from app.services.serp.batch_persistence import BatchPersistenceService
                        await BatchPersistenceService.store_batch_details(
                            pipeline_id=pipeline_id,
                            batch_id=batch_result['batch_id'],
                            content_type=content_type,
                            batch_requests=batch_result.get('batch_requests', []),
                            batch_config={
                                'frequency': content_frequency,
                                'news_time_period': news_time_period if content_type == 'news' else None
                            }
                        )
                    except Exception as persist_error:
                        logger.warning(f"Failed to persist batch details: {persist_error}")
                else:
                    logger.error(f"❌ Failed to create {content_type} batch: {batch_result.get('error')}")
                    content_type_results[content_type] = {'success': False, 'error': batch_result.get('error')}
                    
            except Exception as e:
                logger.error(f"❌ Error creating {content_type} batch: {str(e)}")
                content_type_results[content_type] = {'success': False, 'error': str(e)}
                continue
        
        # PHASE 2: Monitor all batches concurrently
        if batch_infos:
            logger.info(f"👀 MONITORING: {len(batch_infos)} batches concurrently")
            await self._broadcast_status(pipeline_id, f"Monitoring {len(batch_infos)} SERP batches...")
            
            # Create monitoring tasks for all batches
            monitoring_tasks = []
            for batch_info in batch_infos:
                task = self.serp_collector.monitor_batch(
                    batch_id=batch_info['batch_id'],
                    batch_requests=batch_info['batch_requests'],
                    content_type=batch_info['content_type'],
                    pipeline_execution_id=str(pipeline_id),
                    state_tracker=state_tracker,
                    progress_callback=serp_progress_callback
                )
                monitoring_tasks.append(task)
            
            # Wait for all batches to complete
            batch_results = await asyncio.gather(*monitoring_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(batch_results):
                content_type = batch_infos[i]['content_type']
                batch_id = batch_infos[i]['batch_id']
                
                if isinstance(result, Exception):
                    logger.error(f"❌ {content_type.upper()} batch {batch_id} failed with exception: {str(result)}")
                    content_type_results[content_type] = {'success': False, 'error': str(result)}
                elif isinstance(result, dict):
                    logger.info(f"📊 {content_type.upper()} batch {batch_id} result: {result}")
                    
                    # Process successful batch result
                    if result.get('success'):
                        results_stored = result.get('results_stored', 0)
                        results_failed = result.get('results_failed', 0)
                        
                        logger.info(f"✅ {content_type.upper()} batch completed: {results_stored} results stored")
                        
                        content_type_results[content_type] = {
                            'success': True,
                            'batch_id': batch_id,
                            'results_stored': results_stored,
                            'results_failed': results_failed,
                            'content_type': content_type
                        }
                        
                        total_stored += results_stored
                        
                        await self._broadcast_status(
                            pipeline_id,
                            f"✅ {content_type.upper()} batch complete: {results_stored} results"
                        )
                    else:
                        logger.error(f"❌ {content_type.upper()} batch failed: {result.get('error', 'Unknown error')}")
                        content_type_results[content_type] = {
                            'success': False,
                            'error': result.get('error', 'Unknown error'),
                            'content_type': content_type
                        }
                else:
                    logger.error(f"❌ Unexpected result type for {content_type} batch: {type(result)}")
                    content_type_results[content_type] = {
                        'success': False,
                        'error': f'Unexpected result type: {type(result)}',
                        'content_type': content_type
                    }
        
        # Aggregate results
        batch_result = {
            'success': total_stored > 0,
            'content_type_results': content_type_results,
            'total_results_stored': total_stored,
            'batches_created': len([r for r in content_type_results.values() if r.get('success')]),
            'message': f"Created and monitored {len(batch_infos)} batches concurrently"
        }
        
        logger.info(f"🔍 CONCURRENT BATCHES RESULT: {batch_result}")
        
        if batch_result.get('success'):
            total_results = batch_result.get('total_results_stored', 0)
            logger.info(f"✅ CONCURRENT BATCHES SUCCESS: {total_results} results stored across {len(batch_infos)} batches")
        else:
            total_results = 0
            logger.error(f"❌ CONCURRENT BATCHES FAILED: Check individual batch errors")
        
        # Note: In batch mode, we don't track individual domains/URLs in pipeline
        # They're stored directly in the database by the batch processor
        
        # Get unique domains from the database for batch mode
        unique_domains = []
        video_urls = []
        content_urls = []
        if total_results > 0:
            # Since batch mode stores results directly, query the database
            unique_domains = await self._get_unique_serp_domains()
            video_urls = await self._get_video_urls_from_serp()
            content_urls = await self._get_content_urls_from_serp()
            # Log only counts, not the actual lists, to keep logs compact
            logger.info(
                f"🔍 Found {len(unique_domains)} unique domains, {len(video_urls)} video URLs, and {len(content_urls)} content URLs from batch results"
            )
        
        return {
            'keywords_processed': len(keywords),
            'total_results': total_results,
            'total_results_stored': total_results,  # For compatibility
            'discrete_batches': True,  # Indicate discrete batches per content type
            'content_type_results': content_type_results,
            'batches_created': len([r for r in content_type_results.values() if r.get('success')]),
            'regions': config.regions,
            'content_types': config.content_types,
            'granular_scheduling_enabled': True,
            'unique_domains': unique_domains,
            'video_urls': video_urls,
            'content_urls': content_urls
        }
    
    async def _execute_company_enrichment_phase(self, domains: List[str], phase_name: str = "default") -> Dict[str, Any]:
        """Execute company enrichment phase
        
        Args:
            domains: List of domains to enrich
            phase_name: Name of the phase for logging (e.g., 'serp_domains', 'youtube_domains')
        """
        logger.info(f"🏢 Starting company enrichment for {phase_name}: {len(domains)} domains")
        
        # Filter out already enriched domains
        try:
            async with db_pool.acquire() as conn:
                existing_domains = await conn.fetch(
                    "SELECT DISTINCT domain FROM company_profiles WHERE domain = ANY($1::text[])",
                    domains
                )
                existing_set = {row['domain'] for row in existing_domains}
                domains_to_enrich = [d for d in domains if d not in existing_set]
                
                logger.info(f"🏢 Filtered domains: {len(domains)} total, {len(existing_set)} already enriched, {len(domains_to_enrich)} to process")
                domains = domains_to_enrich
        except Exception as e:
            logger.error(f"Failed to filter domains: {e}")
            # Continue with all domains if filtering fails
        
        companies_enriched = 0
        errors = []
        
        semaphore = asyncio.Semaphore(15)  # Respect API limits
        
        async def enrich_domain(domain: str):
            nonlocal companies_enriched
            async with semaphore:
                try:
                    result = await self.company_enricher.enrich_domain(domain)
                    if result:
                        companies_enriched += 1
                    return result
                except asyncio.TimeoutError:
                    error_msg = f"Timeout enriching {domain}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    return None
                except httpx.HTTPError as e:
                    error_msg = f"HTTP error for {domain}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    return None
                except Exception as e:
                    error_msg = f"Failed to enrich {domain}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    return None
        
        # Process in smaller batches to avoid overwhelming the system
        batch_size = 50
        for i in range(0, len(domains), batch_size):
            batch = domains[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(domains) + batch_size - 1) // batch_size
            
            logger.info(f"🏢 Processing enrichment batch {batch_num}/{total_batches} ({len(batch)} domains)")
            
            tasks = [enrich_domain(domain) for domain in batch]
            try:
                # Add timeout for each batch
                async with asyncio.timeout(300):  # 5 minute timeout per batch
                    await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.TimeoutError:
                logger.error(f"Batch {batch_num} timed out after 5 minutes")
                errors.append(f"Batch {batch_num} timed out")
        
        # Log summary
        success = companies_enriched > 0 or len(domains) == 0
        if not success and errors:
            logger.warning(f"Company enrichment completed with errors: {len(errors)} errors for {len(domains)} domains")
            for error in errors[:5]:  # Log first 5 errors
                logger.warning(f"  - {error}")
                
        return {
            'success': success,
            'phase_name': phase_name,
            'domains_processed': len(domains),
            'companies_enriched': companies_enriched,
            'errors': errors,
            'message': f"Enriched {companies_enriched}/{len(domains)} domains"
        }
    
    async def _execute_video_enrichment_phase(self, video_urls: List[str], pipeline_execution_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute video enrichment phase with robustness integration"""
        logger.info(f"📹 Starting video enrichment phase with {len(video_urls)} videos")
        
        # Initialize state tracking for video enrichment
        state_tracker = self.state_tracker
        if state_tracker and pipeline_execution_id:
            try:
                video_items = [
                    {
                        'type': 'video',
                        'url': url,
                        'metadata': {'position': idx}
                    }
                    for idx, url in enumerate(video_urls)
                ]
                await state_tracker.initialize_pipeline(
                    pipeline_execution_id,
                    ["video_enrichment"],
                    video_items
                )
                logger.info(f"🔧 STATE TRACKING: Initialized {len(video_urls)} videos for tracking")
            except Exception as e:
                logger.warning(f"⚠️ STATE TRACKING: Could not initialize: {e}")
                state_tracker = None  # Continue without state tracking
        
        # Get circuit breaker for YouTube API
        youtube_circuit_breaker = self.circuit_breaker_manager.get_breaker(
            "youtube_api",
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=300
        )
        
        # Batch videos for efficient processing
        batch_size = 50  # YouTube API allows up to 50 videos per request
        video_batches = [video_urls[i:i+batch_size] for i in range(0, len(video_urls), batch_size)]
        
        total_enriched = 0
        total_cached = 0
        total_failed = 0
        errors = []
        
        # Skip job queue for now - process directly
        # This avoids the complexity of job queue integration
        logger.info(f"📹 Processing {len(video_batches)} video batches directly")
        
        # Process batches with increased concurrency for better performance
        semaphore = asyncio.Semaphore(10)  # Process up to 10 batches concurrently
        
        async def process_batch(batch: List[str], batch_num: int):
            nonlocal total_enriched, total_cached, total_failed
            
            async with semaphore:
                # Skip detailed state tracking for now - just track at batch level
                
                try:
                    logger.info(f"Processing video batch {batch_num+1}/{len(video_batches)} with {len(batch)} videos")
                    
                    # Use retry manager for resilient API calls
                    async def enrich_with_retry():
                        # Call through circuit breaker
                        return await youtube_circuit_breaker.call(
                            self.video_enricher.enrich_videos,
                            batch,
                            client_id="test",  # TODO: Get from pipeline config
                            keyword=None  # TODO: Pass keyword if available
                        )
                    
                    # Apply retry logic
                    enrichment_result = await self.retry_manager.retry_with_backoff(
                        enrich_with_retry,
                        entity_type='video_batch',
                        entity_id=f'batch_{batch_num}'
                    )
                    
                    if enrichment_result:
                        total_enriched += enrichment_result.enriched_count
                        total_cached += enrichment_result.cached_count
                        total_failed += enrichment_result.failed_count
                        
                        # Skip detailed state tracking for now
                        
                        logger.info(f"Batch {batch_num+1} complete: "
                                  f"{enrichment_result.enriched_count} enriched, "
                                  f"{enrichment_result.cached_count} cached, "
                                  f"{enrichment_result.failed_count} failed")
                    
                    # Job status update removed - processing directly
                    
                    return enrichment_result
                    
                except Exception as e:
                    logger.error(f"Failed to process video batch {batch_num+1}: {str(e)}")
                    errors.append(f"Batch {batch_num+1} error: {str(e)}")
                    
                    # Skip detailed state tracking for now
                    
                    # Job status update removed - processing directly
                    
                    return None
        
        # Create checkpoints
        if state_tracker and pipeline_execution_id:
            await state_tracker.create_checkpoint(
                pipeline_execution_id,
                "video_enrichment",
                "batch_processing_start",
                {
                    'total_videos': len(video_urls),
                    'batch_count': len(video_batches),
                    'batch_size': batch_size
                }
            )
        
        # Process all batches
        logger.info(f"📹 Creating {len(video_batches)} processing tasks")
        tasks = [process_batch(batch, i) for i, batch in enumerate(video_batches)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions in results
        logger.info(f"📹 Processing results: {len(results)} batches processed")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch {i+1} exception: {type(result).__name__}: {str(result)}")
                errors.append(f"Batch {i+1} failed with exception: {str(result)}")
            elif result:
                logger.info(f"Batch {i+1} result: {result}")
        
        # Get progress summary
        progress_summary = {}
        if state_tracker and pipeline_execution_id:
            progress_summary = await state_tracker.get_phase_progress(
                pipeline_execution_id,
                "video_enrichment"
            )
            logger.info(f"📊 Video enrichment progress: {progress_summary}")
        
        # Calculate success rate
        total_videos = len(video_urls)
        successfully_processed = total_enriched + total_cached
        success_rate = (successfully_processed / total_videos * 100) if total_videos > 0 else 100
        
        # Determine if this was successful based on completion rate
        success = success_rate >= 50 or total_videos == 0  # At least 50% success rate
        
        logger.info(f"📹 Video enrichment complete: "
                   f"{total_enriched} enriched, {total_cached} cached, {total_failed} failed "
                   f"(success rate: {success_rate:.1f}%)")
        
        return {
            'success': success,
            'success_rate': success_rate,
            'total_videos': total_videos,
            'videos_processed': total_videos,
            'videos_enriched': total_enriched,
            'videos_cached': total_cached,
            'videos_failed': total_failed,
            'batch_count': len(video_batches),
            'errors': errors,
            'progress_summary': progress_summary
        }
    
    async def _execute_content_scraping_phase(self, urls: List[str]) -> Dict[str, Any]:
        """Execute content scraping phase"""
        scraped_count = 0
        errors = []
        scraped_results = []
        
        # Attach current pipeline id to any already-scraped URLs so the analyzer can pick them up
        try:
            await self._attach_pipeline_id_to_existing_scraped(urls)
        except Exception as e:
            logger.warning(f"Failed to attach pipeline id to existing scraped rows: {e}")
        
        # Filter out already scraped URLs if not force refresh
        urls_to_scrape = await self._filter_unscraped_urls(urls)
        logger.info(f"Content scraping: {len(urls)} total URLs, {len(urls) - len(urls_to_scrape)} already scraped, {len(urls_to_scrape)} new URLs to scrape")
        
        # Use configured concurrency limit or default to 50
        max_concurrent = getattr(self.settings, 'DEFAULT_SCRAPER_CONCURRENT_LIMIT', 50)
        semaphore = asyncio.Semaphore(max_concurrent)
        logger.info(f"Content scraping using {max_concurrent} concurrent connections")
        
        async def scrape_url(url: str):
            nonlocal scraped_count
            async with semaphore:
                try:
                    result = await self.web_scraper.scrape(url)
                    # Always attach pipeline_execution_id and store outcome
                    if result is None:
                        result = {'url': url, 'content': '', 'title': '', 'html': '', 'meta_description': '', 'word_count': 0}
                    try:
                        result['pipeline_execution_id'] = str(self.current_pipeline_id) if hasattr(self, 'current_pipeline_id') else None
                    except Exception:
                        result['pipeline_execution_id'] = None
                    await self._store_scraped_content(result)
                    if result.get('content'):
                        scraped_count += 1
                        scraped_results.append(result)
                    return result
                except Exception as e:
                    # Persist failed attempt as failed row
                    try:
                        await self._store_scraped_content({'url': url, 'content': '', 'title': '', 'html': '', 'meta_description': f'error: {str(e)}', 'word_count': 0, 'pipeline_execution_id': str(self.current_pipeline_id) if hasattr(self, 'current_pipeline_id') else None})
                    except Exception:
                        pass
                    errors.append(f"Failed to scrape {url}: {str(e)}")
                    return None
        
        tasks = [scrape_url(url) for url in urls_to_scrape]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'urls_total': len(urls),
            'urls_candidates': len(urls_to_scrape),
            'urls_scraped': scraped_count,
            'scraped_results': scraped_results,
            'errors': errors
        }

    async def _attach_pipeline_id_to_existing_scraped(self, urls: List[str]) -> None:
        """Attach current pipeline_execution_id to existing scraped_content rows for given URLs."""
        if not urls:
            return
        pipeline_id_str = None
        try:
            pipeline_id_str = str(self.current_pipeline_id)
        except Exception:
            pipeline_id_str = None
        if not pipeline_id_str:
            return
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE scraped_content
                SET pipeline_execution_id = $2
                WHERE url = ANY($1::text[])
                  AND (pipeline_execution_id IS NULL OR pipeline_execution_id <> $2)
                """,
                urls,
                pipeline_id_str,
            )
    
    async def _execute_content_analysis_phase(self) -> Dict[str, Any]:
        """Execute content analysis phase (legacy - for non-concurrent mode)"""
        # Get all unanalyzed content
        unanalyzed_content = await self._get_unanalyzed_content()
        
        analyzed_count = 0
        errors = []
        
        semaphore = asyncio.Semaphore(30)  # OpenAI limits
        
        async def analyze_content(content_data: Dict):
            nonlocal analyzed_count
            async with semaphore:
                try:
                    result = await self.content_analyzer.analyze_content(
                        url=content_data['url'],
                        content=content_data['content'],
                        title=content_data.get('title', ''),
                        project_id=self.current_project_id if hasattr(self, 'current_project_id') else None
                    )
                    if result:
                        analyzed_count += 1
                    return result
                except Exception as e:
                    errors.append(f"Failed to analyze {content_data['url']}: {str(e)}")
                    return None
        
        tasks = [analyze_content(content) for content in unanalyzed_content]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'success': analyzed_count > 0 or len(unanalyzed_content) == 0,
            'content_processed': len(unanalyzed_content),
            'content_analyzed': analyzed_count,
            'errors': errors
        }
    
    async def _wait_for_content_analysis_completion(self, pipeline_id: UUID) -> Dict[str, Any]:
        """Wait until all scraped pages for this pipeline are analyzed and channels resolved."""
        max_wait_time = 1800  # 30 minutes max
        check_interval = 10
        start_time = datetime.utcnow()

        async def get_pipeline_stats() -> Dict[str, int]:
            try:
                pipeline_id_str = str(pipeline_id)
                async with db_pool.acquire() as conn:
                    total_scraped = await conn.fetchval(
                        """
                        SELECT COUNT(*)
                        FROM scraped_content
                        WHERE pipeline_execution_id = $1
                          AND status = 'completed'
                          AND content IS NOT NULL
                          AND LENGTH(content) > 100
                        """,
                        pipeline_id_str,
                    ) or 0

                    total_analyzed = await conn.fetchval(
                        """
                        SELECT COUNT(*)
                        FROM optimized_content_analysis oca
                        WHERE EXISTS (
                          SELECT 1 FROM scraped_content sc
                          WHERE sc.url = oca.url
                            AND sc.pipeline_execution_id = $1
                            AND sc.status = 'completed'
                            AND sc.content IS NOT NULL
                            AND LENGTH(sc.content) > 100
                        )
                        """,
                        pipeline_id_str,
                    ) or 0

                    # Count YouTube channels from video_snapshots (which tracks per-pipeline data)
                    total_channels = await conn.fetchval(
                        """
                        SELECT COUNT(DISTINCT channel_id)
                        FROM video_snapshots vs
                        INNER JOIN serp_results sr ON sr.url = vs.video_url
                        WHERE sr.pipeline_execution_id = $1
                          AND vs.channel_id IS NOT NULL
                        """,
                        pipeline_id_str,
                    ) or 0

                    # Count resolved channels
                    channels_resolved = await conn.fetchval(
                        """
                        SELECT COUNT(DISTINCT ycc.channel_id)
                        FROM youtube_channel_companies ycc
                        WHERE ycc.channel_id IN (
                            SELECT DISTINCT channel_id 
                            FROM video_snapshots vs
                            INNER JOIN serp_results sr ON sr.url = vs.video_url
                            WHERE sr.pipeline_execution_id = $1
                              AND vs.channel_id IS NOT NULL
                        )
                        AND ycc.company_domain IS NOT NULL
                        """,
                        pipeline_id_str,
                    ) or 0

                return {
                    'total_scraped': int(total_scraped),
                    'total_analyzed': int(total_analyzed),
                    'pending_analysis': max(0, int(total_scraped) - int(total_analyzed)),
                    'total_channels': int(total_channels),
                    'channels_resolved': int(channels_resolved),
                    'channels_pending': max(0, int(total_channels) - int(channels_resolved)),
                }
            except Exception as e:
                logger.warning(f"Failed to get pipeline analysis stats: {e}")
                return {
                    'total_scraped': 0,
                    'total_analyzed': 0,
                    'pending_analysis': 0,
                    'total_channels': 0,
                    'channels_resolved': 0,
                    'channels_pending': 0,
                }

        while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
            stats = await get_pipeline_stats()

            all_analyzed = stats['pending_analysis'] == 0 and stats['total_scraped'] > 0
            channels_done = stats['channels_pending'] == 0

            # Check if we should use flexible completion
            if stats['total_scraped'] > 0 and stats['total_analyzed'] > 0:
                completion_pct = (stats['total_analyzed'] / stats['total_scraped']) * 100
                runtime_minutes = (datetime.utcnow() - start_time).total_seconds() / 60
                
                # Use flexible completion if we're at high completion % or long runtime
                if completion_pct >= 95.0 or runtime_minutes >= 15.0:
                    flexible_completion = FlexiblePhaseCompletion(db_pool)
                    is_complete = await flexible_completion.check_and_complete_content_analysis(pipeline_id)
                    if is_complete:
                        logger.info(f"Content analysis marked complete via flexible completion: {stats['total_analyzed']}/{stats['total_scraped']} ({completion_pct:.1f}%)")
                        return {
                            'success': True,
                            'content_processed': stats['total_scraped'],
                            'content_analyzed': stats['total_analyzed'],
                            'channels_total': stats['total_channels'],
                            'channels_resolved': stats['channels_resolved'],
                            'errors': [],
                            'flexible_completion': True
                        }

            if all_analyzed and channels_done:
                logger.info(f"Content analysis complete: {stats['total_analyzed']} items; channels resolved: {stats['channels_resolved']}")
                return {
                    'success': True,
                    'content_processed': stats['total_scraped'],
                    'content_analyzed': stats['total_analyzed'],
                    'channels_total': stats['total_channels'],
                    'channels_resolved': stats['channels_resolved'],
                    'errors': []
                }

            progress_pct = (stats['total_analyzed'] / max(stats['total_scraped'], 1)) * 100 if stats['total_scraped'] else 0.0
            await self._broadcast_status(
                pipeline_id,
                (
                    f"Analyzing content: {stats['total_analyzed']}/{stats['total_scraped']} ({progress_pct:.1f}%) "
                    f"- pending {stats['pending_analysis']}; channels {stats['channels_resolved']}/{stats['total_channels']}"
                )
            )
            logger.info(
                f"Content analysis progress: {stats['total_analyzed']}/{stats['total_scraped']} ({progress_pct:.1f}%) - "
                f"{stats['pending_analysis']} pending; channels {stats['channels_resolved']}/{stats['total_channels']}"
            )

            await asyncio.sleep(check_interval)

        # Timeout
        stats = await get_pipeline_stats()
        logger.warning(
            f"Content analysis timeout. analyzed={stats['total_analyzed']}/{stats['total_scraped']}, "
            f"channels_resolved={stats['channels_resolved']}/{stats['total_channels']}"
        )
        return {
            'success': False,
            'content_processed': stats['total_scraped'],
            'content_analyzed': stats['total_analyzed'],
            'channels_total': stats['total_channels'],
            'channels_resolved': stats['channels_resolved'],
            'errors': [f"Analysis/channel resolution timeout after {max_wait_time} seconds"]
        }
    
    async def _execute_dsi_calculation_phase(self) -> Dict[str, Any]:
        """Execute DSI calculation phase for ALL 24 digital landscapes"""
        try:
            # Get all active landscapes
            landscapes = await self._get_active_landscapes()
            
            if not landscapes:
                return {
                    'success': False,
                    'message': 'No active landscapes found'
                }
            
            total_companies_ranked = 0
            total_pages_ranked = 0
            landscape_results = {}
            errors = []
            
            logger.info(f"Calculating DSI for {len(landscapes)} digital landscapes")
            
            # Use the enhanced SimplifiedDSICalculator for comprehensive DSI calculation
            # This includes both company and page DSI with consistent formulas
            logger.info(f"Calculating comprehensive DSI for all search types using enhanced calculator")
            
            # Calculate overall DSI (includes company and page level with enhanced data)
            dsi_result = await self.dsi_calculator.calculate_dsi_rankings(str(self.pipeline_execution_id))
            
            total_companies_ranked = dsi_result.get('companies_ranked', 0)
            total_pages_ranked = dsi_result.get('pages_ranked', 0)
            
            # Also calculate landscape-specific metrics for each of the 24 landscapes
            for landscape in landscapes:
                try:
                    logger.info(f"Processing landscape-specific DSI for: {landscape['name']} ({landscape['id']})")
                    
                    # Calculate landscape-specific company DSI using ProductionLandscapeCalculator
                    landscape_result = await self.landscape_calculator.calculate_and_store_landscape_dsi(
                        landscape['id'], 
                        'default'  # Use default client_id for pipeline calculations
                    )
                    
                    landscape_results[landscape['name']] = {
                        'landscape_id': landscape['id'],
                        'companies': landscape_result.total_companies,
                        'keywords': landscape_result.total_keywords,
                        'calculation_duration': landscape_result.calculation_duration_seconds
                    }
                    
                    logger.info(f"  Completed {landscape['name']}: {landscape_result.total_companies} companies, {landscape_result.total_keywords} keywords")
                    
                except Exception as e:
                    error_msg = f"Failed to calculate landscape '{landscape['name']}': {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            return {
                'success': True,
                'dsi_calculated': True,
                'landscapes_processed': len(landscapes),
                'companies_ranked': total_companies_ranked,
                'pages_ranked': total_pages_ranked,
                'landscape_results': landscape_results,
                'errors': errors,
                'success_rate': (len(landscapes) - len(errors)) / len(landscapes) if landscapes else 0
            }
            
        except Exception as e:
            logger.error(f"DSI calculation phase failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'dsi_calculated': False,
                'error': str(e)
            }
    
    async def _execute_historical_snapshot_phase(self) -> Dict[str, Any]:
        """Execute historical snapshot creation"""
        try:
            snapshot_date = date.today().replace(day=1)  # First of month
            result = await self.historical_service.create_monthly_snapshot(
                snapshot_date=snapshot_date
            )
            return {
                'snapshot_created': True,
                'snapshot_date': snapshot_date.isoformat(),
                'snapshots_created': result.get('snapshots_created', {})
            }
        except Exception as e:
            return {
                'snapshot_created': False,
                'error': str(e)
            }
    
    async def _execute_keyword_metrics_enrichment_phase(self, config: PipelineConfig, pipeline_id: UUID) -> Dict[str, Any]:
        """Execute keyword metrics enrichment using Google Ads Historical Metrics API"""
        try:
            logger.info(f"🔍 PHASE START: Keyword metrics enrichment for pipeline {pipeline_id}")
            
            # Get keywords to process
            if config.keywords:
                logger.info(f"🔍 Getting specific keywords: {config.keywords}")
                keywords = await self._get_keywords_by_text(config.keywords)
            else:
                logger.info(f"🔍 Getting all ACTIVE keywords from database")
                keywords = await self._get_all_keywords(active_only=True)
            
            logger.info(f"🔍 Found {len(keywords) if keywords else 0} keywords in database")
            
            # Apply testing mode batch size limit
            if config.testing_mode and config.testing_batch_size and len(keywords) > config.testing_batch_size:
                logger.info(f"🧪 Testing mode: Limiting keywords from {len(keywords)} to {config.testing_batch_size}")
                keywords = keywords[:config.testing_batch_size]
            
            if not keywords:
                logger.warning(f"🔍 No keywords found - returning early")
                return {
                    'keywords_with_metrics': 0,
                    'message': 'No keywords found to process'
                }
            
            keyword_texts = [kw['keyword'] for kw in keywords]
            # Create mapping of keyword text to ID for database storage
            keyword_id_map = {kw['keyword']: kw['id'] for kw in keywords}
            
            # Ensure regions come from active schedule when UI sends generic defaults
            regions = config.regions or []
            try:
                if regions == ["US", "UK", "DE", "SA", "VN"]:
                    async with db_pool.acquire() as conn:
                        row = await conn.fetchrow("SELECT regions FROM pipeline_schedules WHERE is_active = true LIMIT 1")
                        if row and row.get('regions'):
                            regions = row['regions']
            except Exception:
                pass

            logger.info(f"Enriching {len(keyword_texts)} keywords with Google Ads historical metrics across {len(regions)} countries")
            
            # Debug logging for Google Ads service availability
            logger.info(f"Checking Google Ads service availability...")
            logger.info(f"Has google_ads_service attribute: {hasattr(self, 'google_ads_service')}")
            
            # Use Enhanced Google Ads service for batch processing (if available)
            if hasattr(self, 'google_ads_service'):
                logger.info(f"Google Ads service found! Calling get_historical_metrics_batch...")
                logger.info(f"Keywords to process: {keyword_texts}")
                logger.info(f"Countries: {regions}")
                
                try:
                    logger.info(f"🚀 Using SimplifiedGoogleAdsService with proper batching")
                    
                    # Initialize the Google Ads service with batching support
                    from app.services.keywords.simplified_google_ads_service import SimplifiedGoogleAdsService
                    google_ads_service = SimplifiedGoogleAdsService()
                    await google_ads_service.initialize()
                    
                    # Use the service's batch processing which handles up to 1000 keywords per batch
                    logger.info(f"📊 Processing {len(keyword_texts)} keywords across {len(regions)} regions with proper batching")
                    
                    # Add keyword IDs to the keywords for mapping
                    keyword_texts_with_ids = []
                    for kw in keywords:
                        keyword_texts_with_ids.append(kw['keyword'])
                    
                    # Call the batch processing method
                    country_metrics_raw = await google_ads_service.get_historical_metrics_batch(
                    keywords=keyword_texts,
                        countries=regions,
                        pipeline_execution_id=str(pipeline_id)
                    )
                    
                    # Convert KeywordMetric objects to dicts and map keyword IDs
                    country_metrics = {}
                    total_metrics_collected = 0
                    
                    for country, metrics in country_metrics_raw.items():
                        country_metrics[country] = []
                        for metric in metrics:
                            keyword_metric = {
                                'keyword': metric.keyword,
                                'keyword_id': keyword_id_map.get(metric.keyword),  # Map to keyword ID
                                'avg_monthly_searches': metric.avg_monthly_searches,
                                'competition_level': metric.competition_level
                            }
                            country_metrics[country].append(keyword_metric)
                            total_metrics_collected += 1
                        
                        logger.info(f"✅ {country}: Collected {len(country_metrics[country])} keyword metrics")
                    
                    logger.info(f"🎉 Google Ads batch processing completed!")
                    logger.info(f"📊 Total metrics collected: {total_metrics_collected} across {len(regions)} regions")
                    
                except Exception as e:
                    logger.error(f"💥 Google Ads direct pattern failed: {str(e)}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    country_metrics = {country: [] for country in config.regions}
            else:
                logger.warning("Google Ads service not available - skipping keyword metrics enrichment")
                country_metrics = {country: [] for country in config.regions}
            
            # DataForSEO Fallback: If Google Ads returned no metrics, try DataForSEO
            if total_metrics_collected == 0 and hasattr(self.settings, 'DATAFORSEO_LOGIN') and self.settings.DATAFORSEO_LOGIN:
                logger.info(f"🔄 Google Ads returned no metrics, falling back to DataForSEO...")
                
                try:
                    from app.services.keywords.dataforseo_service import DataForSEOService
                    dataforseo_service = DataForSEOService()
                    await dataforseo_service.initialize()
                    
                    # Process each country
                    for country in regions:
                        logger.info(f"🔍 DataForSEO: Processing {len(keyword_texts)} keywords for {country}")
                        
                        try:
                            metrics = await dataforseo_service.get_keyword_metrics_by_country(
                                keywords=keyword_texts,
                                country_code=country,
                                pipeline_execution_id=str(pipeline_id)
                            )
                            
                            # Map metrics to keyword IDs
                            mapped_metrics = []
                            for metric in metrics:
                                keyword_metric = {
                                    'keyword': metric['keyword'],
                                    'keyword_id': keyword_id_map.get(metric['keyword']),
                                    'avg_monthly_searches': metric['avg_monthly_searches'],
                                    'competition_level': metric['competition_level']
                                }
                                mapped_metrics.append(keyword_metric)
                                total_metrics_collected += 1
                            
                            country_metrics[country] = mapped_metrics
                            logger.info(f"✅ DataForSEO {country}: Collected {len(mapped_metrics)} keyword metrics")
                            
                        except Exception as e:
                            logger.error(f"❌ DataForSEO failed for {country}: {str(e)}")
                            country_metrics[country] = []
                    
                    await dataforseo_service.close()
                    logger.info(f"🎉 DataForSEO fallback completed! Total metrics: {total_metrics_collected}")
                    
                except Exception as e:
                    logger.error(f"❌ DataForSEO fallback failed: {str(e)}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Calculate results
            total_keywords_with_metrics = 0
            country_results = {}
            
            for country, metrics in country_metrics.items():
                country_results[country] = {
                    'keywords_processed': len(metrics),
                    'avg_monthly_searches': sum(m['avg_monthly_searches'] for m in metrics) // len(metrics) if metrics else 0,
                    'high_competition_count': len([m for m in metrics if m['competition_level'] == 'HIGH'])
                }
                total_keywords_with_metrics += len(metrics)
            
            return {
                'keywords_with_metrics': total_keywords_with_metrics,
                'country_results': country_results,
                'total_countries': len(config.regions),
                'total_keywords': len(keyword_texts),
                'api_calls_made': len(config.regions)  # One batch call per country
            }
            
        except Exception as e:
            logger.error(f"💥 CRITICAL: Keyword metrics enrichment phase failed: {str(e)}")
            import traceback
            logger.error(f"💥 Full traceback: {traceback.format_exc()}")
            return {
                'keywords_with_metrics': 0,
                'error': str(e)
            }
    
    async def _execute_landscape_dsi_calculation_phase(self, config: PipelineConfig) -> Dict[str, Any]:
        """Execute Digital Landscape DSI calculations for all active landscapes"""
        try:
            # Get all active landscapes
            landscapes = await self._get_active_landscapes()
            
            if not landscapes:
                return {
                    'landscapes_calculated': 0,
                    'message': 'No active landscapes found'
                }
            
            landscapes_calculated = 0
            landscape_results = {}
            errors = []
            
            # Calculate DSI for each landscape
            for landscape in landscapes:
                try:
                    logger.info(f"Calculating DSI for landscape: {landscape['name']}")
                    
                    result = await self.landscape_calculator.calculate_and_store_landscape_dsi(
                        landscape['id'], config.client_id
                    )
                    
                    landscape_results[landscape['name']] = {
                        'companies': result.total_companies,
                        'keywords': result.total_keywords,
                        'calculation_duration': result.calculation_duration_seconds
                    }
                    landscapes_calculated += 1
                    
                except Exception as e:
                    error_msg = f"Failed to calculate landscape '{landscape['name']}': {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            return {
                'landscapes_calculated': landscapes_calculated,
                'landscape_results': landscape_results,
                'total_landscapes': len(landscapes),
                'errors': errors,
                'success_rate': landscapes_calculated / len(landscapes) if landscapes else 0
            }
            
        except Exception as e:
            logger.error(f"Landscape DSI calculation phase failed: {str(e)}")
            return {
                'landscapes_calculated': 0,
                'error': str(e)
            }
    
    async def _get_keywords_by_text(self, keyword_texts: List[str]) -> List[Dict]:
        """Get keyword records by text"""
        async with db_pool.acquire() as conn:
            placeholders = ','.join(f'${i+1}' for i in range(len(keyword_texts)))
            results = await conn.fetch(
                f"""
                SELECT id, keyword, category, jtbd_stage
                FROM keywords 
                WHERE keyword = ANY($1::text[])
                """,
                keyword_texts
            )
            return [dict(row) for row in results]
    
    async def _get_all_keywords(self, active_only: bool = False) -> List[Dict]:
        """Get all keyword records, optionally filtering to active-only."""
        async with db_pool.acquire() as conn:
            if active_only:
                results = await conn.fetch(
                    """
                    SELECT id, keyword, category, jtbd_stage
                    FROM keywords 
                    WHERE is_active IS DISTINCT FROM false
                    ORDER BY keyword
                    """
                )
            else:
                results = await conn.fetch(
                    """
                    SELECT id, keyword, category, jtbd_stage
                    FROM keywords 
                    ORDER BY keyword
                    """
                )
            return [dict(row) for row in results]
    
    async def _get_unique_serp_domains(self) -> List[str]:
        """Get unique domains from SERP results prioritized by traffic and frequency"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetch(
                    """
                    SELECT 
                        domain,
                        COUNT(*) as serp_count,
                        COUNT(DISTINCT keyword_id) as keyword_count,
                        SUM(COALESCE(estimated_traffic, 0)) as total_traffic,
                        AVG(position) as avg_position
                    FROM serp_results 
                    WHERE domain IS NOT NULL 
                    AND domain != ''
                    AND pipeline_execution_id = $1
                    GROUP BY domain
                    ORDER BY 
                        serp_count DESC,      -- Most SERP appearances first
                        keyword_count DESC,   -- Most keywords second  
                        total_traffic DESC,   -- Most traffic third
                        avg_position ASC      -- Best positions fourth
                    """
                , self.current_pipeline_id)
                
                domains = [row['domain'] for row in result]
                logger.info(f"🎯 Prioritized {len(domains)} domains for enrichment by traffic/frequency")
                if result:
                    top_domain = result[0]
                    logger.info(f"Top priority: {top_domain['domain']} ({top_domain['serp_count']} SERP, {top_domain['keyword_count']} keywords)")
                
                return domains
        except Exception as e:
            logger.error(f"Error getting unique SERP domains: {e}")
            return []
    
    async def _get_video_urls_from_serp(self) -> List[str]:
        """Get video URLs from SERP results"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetch(
                    """
                    SELECT DISTINCT url 
                    FROM serp_results 
                    WHERE serp_type = 'video'
                    AND url IS NOT NULL 
                    AND url != ''
                    AND pipeline_execution_id = $1
                    ORDER BY url
                    """
                , self.current_pipeline_id)
                return [row['url'] for row in result]
        except Exception as e:
            logger.error(f"Error getting video URLs: {e}")
            return []
    
    async def _get_content_urls_from_serp(self) -> List[str]:
        """Get content URLs from SERP results for scraping"""
        try:
            async with self.db.acquire() as conn:
                # Get all URLs from this pipeline's SERP results
                # The _filter_unscraped_urls method will handle filtering out already scraped URLs
                result = await conn.fetch(
                    """
                    SELECT DISTINCT url, MIN(position) as min_position
                    FROM serp_results 
                    WHERE serp_type IN ('organic', 'news')
                    AND url IS NOT NULL 
                    AND url != ''
                    AND pipeline_execution_id = $1
                    GROUP BY url
                    ORDER BY min_position, url
                    """,
                    self.current_pipeline_id
                )
                logger.info(f"Found {len(result)} total URLs from SERP results")
                return [row['url'] for row in result]
        except Exception as e:
            logger.error(f"Error getting content URLs: {e}")
            return []
    
    async def _get_youtube_channel_domains(self) -> List[str]:
        """Get newly discovered domains from YouTube channel enrichments"""
        try:
            async with self.db.acquire() as conn:
                # First get channel custom URLs that might contain domains
                result = await conn.fetch(
                    """
                    SELECT DISTINCT yv.channel_custom_url, yv.channel_description
                    FROM youtube_videos yv
                    WHERE yv.channel_custom_url IS NOT NULL
                    AND yv.channel_custom_url != ''
                    """
                )
                
                domains = []
                for row in result:
                    # Extract potential domains from channel descriptions or custom URLs
                    # This is a simplified version - real implementation would parse for actual domains
                    description = row.get('channel_description', '')
                    # Parse description for website URLs
                    import re
                    url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
                    matches = re.findall(url_pattern, description)
                    domains.extend(matches)
                
                # Filter out already enriched domains
                if domains:
                    existing_result = await conn.fetch(
                        """
                        SELECT DISTINCT domain FROM companies 
                        WHERE domain = ANY($1::text[])
                        """,
                        domains
                    )
                    existing_domains = {row['domain'] for row in existing_result}
                    domains = [d for d in domains if d not in existing_domains]
                
                return list(set(domains))  # Remove duplicates
        except Exception as e:
            logger.error(f"Error getting YouTube channel domains: {e}")
            return []
    
    async def _filter_unscraped_urls(self, urls: List[str]) -> List[str]:
        """Filter out already scraped URLs"""
        if not urls:
            return []
        
        # Normalize URLs to maximize cache hits and skip previously scraped variants
        try:
            normalize = getattr(self.web_scraper, '_normalize_url', None)
            normalized_map = {u: (normalize(u) if normalize else u) for u in urls}
            lookup_urls = list({*urls, *normalized_map.values()})
        except Exception:
            normalized_map = {u: u for u in urls}
            lookup_urls = urls
        
        async with db_pool.acquire() as conn:
            scraped = await conn.fetch(
                """
                SELECT url FROM scraped_content 
                WHERE url = ANY($1::text[]) AND status = 'completed'
                """,
                lookup_urls
            )
            scraped_urls = {row['url'] for row in scraped}
            return [u for u in urls if u not in scraped_urls and normalized_map.get(u) not in scraped_urls]
    
    async def _store_scraped_content(self, result: Dict) -> None:
        """Store scraped content in database"""
        from urllib.parse import urlparse
        
        if not result or not result.get('url'):
            return
        
        # Extract domain from URL
        parsed_url = urlparse(result['url'])
        domain = parsed_url.netloc
        # Normalize status based on content quality
        content_text = result.get('content') or ''
        has_quality_content = isinstance(content_text, str) and len(content_text.strip()) >= 100
        status_value = 'completed' if has_quality_content else 'failed'
        # Map error string to error_message column
        error_message = None
        try:
            raw_error = result.get('error')
            if isinstance(raw_error, str) and raw_error:
                error_message = raw_error
            elif isinstance(result.get('meta_description'), str) and result.get('meta_description', '').startswith('error:'):
                error_message = result.get('meta_description')
        except Exception:
            error_message = None
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO scraped_content (
                    url, domain, title, content, html, meta_description,
                    word_count, content_type, scraped_at, status, pipeline_execution_id, error_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    html = EXCLUDED.html,
                    meta_description = EXCLUDED.meta_description,
                    word_count = EXCLUDED.word_count,
                    content_type = EXCLUDED.content_type,
                    scraped_at = EXCLUDED.scraped_at,
                    status = EXCLUDED.status,
                    pipeline_execution_id = COALESCE(EXCLUDED.pipeline_execution_id, scraped_content.pipeline_execution_id),
                    error_message = COALESCE(EXCLUDED.error_message, scraped_content.error_message)
                """,
                result.get('url'),
                domain,
                result.get('title', ''),
                result.get('content', ''),
                result.get('html', ''),
                result.get('meta_description', ''),
                result.get('word_count', 0),
                result.get('content_type', 'text/html'),
                datetime.utcnow(),
                status_value,
                result.get('pipeline_execution_id'),
                error_message
            )
    
    async def _get_unanalyzed_content(self) -> List[Dict]:
        """Get content that hasn't been analyzed"""
        async with db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT sc.url, sc.title, sc.content
                FROM scraped_content sc
                LEFT JOIN content_analysis ca ON sc.url = ca.url
                WHERE sc.status = 'completed' 
                AND sc.content IS NOT NULL 
                AND ca.id IS NULL
                ORDER BY sc.scraped_at DESC
                """
            )
            return [dict(row) for row in results]
    
    async def _get_active_landscapes(self) -> List[Dict]:
        """Get all active digital landscapes"""
        async with db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT l.id, l.name, l.description,
                       COUNT(lk.keyword_id) as keyword_count
                FROM digital_landscapes l
                LEFT JOIN landscape_keywords lk ON l.id = lk.landscape_id
                WHERE l.is_active = true
                GROUP BY l.id, l.name, l.description
                HAVING COUNT(lk.keyword_id) > 0
                ORDER BY l.name
                """
            )
            return [dict(row) for row in results]
    
    async def _save_pipeline_state(self, result: PipelineResult):
        """Save pipeline state to database"""
        # Slim down phase_results before persisting to avoid huge JSONB payloads
        def _summarize_list(values, sample_size: int = 50):
            if not isinstance(values, list):
                return values
            total = len(values)
            sample = values[:sample_size]
            return {
                "total": total,
                "sample": sample,
            }

        def _truncate_phase_results(phase_results: Dict[str, Any]) -> Dict[str, Any]:
            try:
                if not isinstance(phase_results, dict):
                    return phase_results

                slim: Dict[str, Any] = {}
                # Per‑phase slimming rules
                for phase_key, phase_val in phase_results.items():
                    if not isinstance(phase_val, dict):
                        slim[phase_key] = phase_val
                        continue

                    slim_phase = dict(phase_val)

                    # Known large arrays from SERP collection
                    for heavy_key in ("unique_domains", "video_urls", "content_urls"):
                        if heavy_key in slim_phase:
                            slim_phase[heavy_key] = _summarize_list(slim_phase.get(heavy_key) or [], 50)

                    # Generic trimming for any unexpected large lists
                    for k, v in list(slim_phase.items()):
                        if isinstance(v, list) and len(v) > 200:
                            slim_phase[k] = _summarize_list(v, 50)

                    # Errors/warnings: cap to first 200 entries
                    for log_key in ("errors", "warnings"):
                        if isinstance(slim_phase.get(log_key), list) and len(slim_phase[log_key]) > 200:
                            slim_phase[log_key] = slim_phase[log_key][:200]

                    slim[phase_key] = slim_phase

                return slim
            except Exception:
                # On any failure, fallback to minimal counts only
                try:
                    return {k: {"success": bool(v.get("success"))} if isinstance(v, dict) else v for k, v in phase_results.items()}
                except Exception:
                    return {}

        # Build slim payload and measure sizes for observability
        slim_phase_results = _truncate_phase_results(result.phase_results)
        phase_results_json = json.dumps(slim_phase_results, cls=DecimalEncoder)
        try:
            original_size = len(json.dumps(result.phase_results, cls=DecimalEncoder).encode("utf-8")) if isinstance(result.phase_results, dict) else 0
            slim_size = len(phase_results_json.encode("utf-8"))
            logger.info(f"_save_pipeline_state: phase_results size original={original_size/1024/1024:.2f}MB slim={slim_size/1024/1024:.2f}MB")
        except Exception:
            pass

        # Cap phase_results_json if still huge: replace with high‑level summary only
        MAX_BYTES = 5 * 1024 * 1024  # 5MB safety cap
        if len(phase_results_json.encode("utf-8")) > MAX_BYTES:
            summary = {}
            try:
                # Derive a minimal summary with per‑phase success and counts if present
                for phase_key, phase_val in slim_phase_results.items() if isinstance(slim_phase_results, dict) else []:
                    if isinstance(phase_val, dict):
                        summary[phase_key] = {
                            "success": bool(phase_val.get("success", False)),
                            "results_stored": phase_val.get("total_results") or phase_val.get("results_stored") or phase_val.get("companies_enriched") or phase_val.get("content_analyzed") or 0,
                        }
                phase_results_json = json.dumps({"summary": summary})
                logger.warning("_save_pipeline_state: phase_results exceeded cap; stored summary only")
            except Exception:
                phase_results_json = json.dumps({"summary": "trimmed"})
                logger.warning("_save_pipeline_state: trimming fallback applied")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pipeline_executions (
                    id, status, mode, started_at, completed_at,
                    phase_results, keywords_processed, keywords_with_metrics, serp_results_collected,
                    companies_enriched, videos_enriched, content_analyzed, landscapes_calculated,
                    errors, warnings, api_calls_made, estimated_cost
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = EXCLUDED.completed_at,
                    phase_results = EXCLUDED.phase_results,
                    keywords_processed = EXCLUDED.keywords_processed,
                    keywords_with_metrics = EXCLUDED.keywords_with_metrics,
                    serp_results_collected = EXCLUDED.serp_results_collected,
                    companies_enriched = EXCLUDED.companies_enriched,
                    videos_enriched = EXCLUDED.videos_enriched,
                    content_analyzed = EXCLUDED.content_analyzed,
                    landscapes_calculated = EXCLUDED.landscapes_calculated,
                    errors = EXCLUDED.errors,
                    warnings = EXCLUDED.warnings,
                    api_calls_made = EXCLUDED.api_calls_made,
                    estimated_cost = EXCLUDED.estimated_cost
                """,
                result.pipeline_id,
                result.status.value,
                result.mode.value,
                result.started_at,
                result.completed_at,
                phase_results_json,
                result.keywords_processed,
                result.keywords_with_metrics,
                result.serp_results_collected,
                result.companies_enriched,
                result.videos_enriched,
                result.content_analyzed,
                result.landscapes_calculated,
                json.dumps(result.errors),
                json.dumps(result.warnings),
                json.dumps(result.api_calls_made),
                result.estimated_cost
            )
    
    async def _load_pipeline_state(self, pipeline_id: UUID) -> Optional[PipelineResult]:
        """Load pipeline state from database"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pipeline_executions WHERE id = $1",
                pipeline_id
            )
            
            if not row:
                return None
            
            data = dict(row)
            # Map database field to model field
            if 'id' in data:
                data['pipeline_id'] = data.pop('id')
            # Parse JSON fields
            data['phase_results'] = json.loads(data['phase_results'] or '{}')
            data['errors'] = json.loads(data['errors'] or '[]')
            data['warnings'] = json.loads(data['warnings'] or '[]')
            data['api_calls_made'] = json.loads(data['api_calls_made'] or '{}')
            
            # Ensure required fields have defaults
            data.setdefault('current_phase', None)
            data.setdefault('phases_completed', [])
            data.setdefault('content_types', [])
            data.setdefault('regions', [])
            data.setdefault('mode', 'batch_optimized')
            
            return PipelineResult(**data)
    
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
    
    async def _store_google_ads_metrics(self, keyword_metrics: List[Dict], country: str, pipeline_id: str):
        """Store Google Ads metrics in database"""
        try:
            snapshot_date = date.today()
            
            async with db_pool.acquire() as conn:
                stored_count = 0
                
                for metric in keyword_metrics:
                    try:
                        # Resolve keyword_id if missing by normalized lookup
                        kw_id = metric.get('keyword_id')
                        if not kw_id:
                            kw_text = (metric.get('keyword') or '').strip()
                            if kw_text:
                                row = await conn.fetchrow(
                                    """
                                    SELECT id FROM keywords 
                                    WHERE lower(keyword) = lower($1)
                                    LIMIT 1
                                    """,
                                    kw_text
                                )
                                if row:
                                    kw_id = row['id']
                                    metric['keyword_id'] = kw_id
                        # Skip insert if keyword_id still missing
                        if not kw_id:
                            logger.warning(f"Skipping Google Ads metric without keyword_id: {metric.get('keyword')}")
                            continue
                        await conn.execute("""
                            INSERT INTO historical_keyword_metrics (
                                snapshot_date, keyword_id, keyword_text, country_code, source,
                                pipeline_execution_id, avg_monthly_searches, 
                                competition_level
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT DO NOTHING
                        """,
                            snapshot_date,
                            kw_id,
                            metric['keyword'], 
                            country,
                            'GOOGLE_ADS',
                            pipeline_id,
                            metric['avg_monthly_searches'],
                            metric['competition_level']
                        )
                        stored_count += 1
                        
                    except Exception as store_error:
                        logger.error(f"❌ Failed to store {metric['keyword']}: {store_error}")
                        
                logger.info(f"💾 Successfully stored {stored_count} Google Ads metrics for {country}")
                
        except Exception as e:
            logger.error(f"❌ Database storage error for {country}: {e}")
    
    async def _cleanup_pipeline_after_delay(self, pipeline_id: UUID, delay_seconds: int):
        """Remove pipeline from memory after delay"""
        await asyncio.sleep(delay_seconds)
        async with self._lock:
            if pipeline_id in self._active_pipelines:
                del self._active_pipelines[pipeline_id]
                logger.info(f"Pipeline {pipeline_id} removed from memory")
    
    async def _get_content_type_schedule_config(self, content_type: str, config: Optional[PipelineConfig] = None) -> Dict[str, Any]:
        """Get content-type specific scheduling configuration
        
        If this is a scheduled run, use the schedule's configuration.
        Otherwise, use the default configuration from the database.
        """
        try:
            # If this is a scheduled run, get the schedule configuration
            if config and config.schedule_id:
                async with db_pool.acquire() as conn:
                    schedule_data = await conn.fetchrow(
                        """
                        SELECT content_schedules 
                        FROM pipeline_schedules 
                        WHERE id = $1
                        """,
                        config.schedule_id
                    )
                    
                    if schedule_data and schedule_data['content_schedules']:
                        content_schedules = json.loads(schedule_data['content_schedules'])
                        
                        # Find the schedule for this content type
                        for cs in content_schedules:
                            if cs.get('content_type') == content_type and cs.get('enabled', True):
                                frequency = cs.get('frequency', 'immediate')
                                
                                # Map schedule frequency enum values to simple strings
                                frequency_map = {
                                    'daily': 'daily',
                                    'weekly': 'weekly',
                                    'monthly': 'monthly',
                                    'quarterly': 'quarterly',
                                    'custom_cron': 'custom'
                                }
                                
                                result = {
                                    'frequency': frequency_map.get(frequency, frequency),
                                    'priority': 'normal',
                                    'scheduled': True,
                                    'is_initial_run': config.is_initial_run
                                }
                                logger.info(f"📅 {content_type} schedule from pipeline_schedules: {result}")
                                return result
            
            # Otherwise, get default config from database
            async with db_pool.acquire() as conn:
                # Get scheduling config from analysis_config or dedicated table
                config_data = await conn.fetchrow(
                    """
                    SELECT 
                        serp_scheduling_config,
                        batch_configuration
                    FROM analysis_config 
                    LIMIT 1
                    """
                )
                
                if config_data and config_data['serp_scheduling_config']:
                    scheduling_config = json.loads(config_data['serp_scheduling_config'])
                    
                    # Get content-type specific config
                    content_config = scheduling_config.get(content_type, {})
                    logger.info(f"📅 Loaded {content_type} schedule from database: {content_config}")
                    
                    return content_config
                else:
                    # Default scheduling based on content type
                    defaults = {
                        'organic': {'frequency': 'immediate', 'priority': 'normal'},
                        'news': {'frequency': 'immediate', 'priority': 'high'}, 
                        'video': {'frequency': 'immediate', 'priority': 'low'}
                    }
                    
                    default_config = defaults.get(content_type, {'frequency': 'immediate', 'priority': 'normal'})
                    logger.info(f"📅 Using default {content_type} schedule: {default_config}")
                    
                    return default_config
                    
        except Exception as e:
            logger.warning(f"Failed to load schedule config for {content_type}: {e}")
            return {'frequency': 'immediate', 'priority': 'normal'}
    
    async def clear_all_pipelines(self) -> int:
        """Clear all pipeline execution history"""
        async with db_pool.acquire() as conn:
            # Get count before deletion
            count_result = await conn.fetchval("SELECT COUNT(*) FROM pipeline_executions")
            
            # Delete all pipeline executions
            await conn.execute("DELETE FROM pipeline_executions")
            
            # Also clear related phase status if exists
            try:
                await conn.execute("DELETE FROM pipeline_phase_status")
            except Exception:
                # Table might not exist yet
                pass
            
            logger.info(f"🧹 Cleared {count_result} pipeline executions")
            return count_result
    
    async def check_and_trigger_pending_phases(self, pipeline_id: UUID) -> bool:
        """Check if any phases are pending and can be triggered"""
        try:
            async with db_pool.acquire() as conn:
                # Get pipeline status and phases
                pipeline = await conn.fetchrow(
                    "SELECT * FROM pipeline_executions WHERE id = $1",
                    str(pipeline_id)
                )
                
                if not pipeline or pipeline['status'] != 'running':
                    return False
                
                # Check for pending DSI calculation
                dsi_phase = await conn.fetchrow(
                    """
                    SELECT * FROM pipeline_phase_status 
                    WHERE pipeline_execution_id = $1 AND phase_name = 'dsi_calculation'
                    """,
                    str(pipeline_id)
                )
                
                if dsi_phase and dsi_phase['status'] == 'pending':
                    # Check if content analysis is complete
                    content_phase = await conn.fetchrow(
                        """
                        SELECT * FROM pipeline_phase_status 
                        WHERE pipeline_execution_id = $1 AND phase_name = 'content_analysis'
                        """,
                        str(pipeline_id)
                    )
                    
                    if content_phase and content_phase['status'] == 'completed':
                        logger.info(f"Auto-triggering DSI calculation for pipeline {pipeline_id}")
                        # Update phase to running
                        await conn.execute(
                            """
                            UPDATE pipeline_phase_status 
                            SET status = 'running', started_at = NOW()
                            WHERE pipeline_execution_id = $1 AND phase_name = 'dsi_calculation'
                            """,
                            str(pipeline_id)
                        )
                        
                        # Execute DSI calculation
                        result = await self.dsi_calculator.calculate_dsi_rankings(str(pipeline_id))
                        
                        # Update phase to completed
                        await conn.execute(
                            """
                            UPDATE pipeline_phase_status 
                            SET status = 'completed', completed_at = NOW()
                            WHERE pipeline_execution_id = $1 AND phase_name = 'dsi_calculation'
                            """,
                            str(pipeline_id)
                        )
                        
                        # Mark pipeline as complete
                        await conn.execute(
                            """
                            UPDATE pipeline_executions 
                            SET status = 'completed', completed_at = NOW()
                            WHERE id = $1
                            """,
                            str(pipeline_id)
                        )
                        
                        logger.info(f"DSI calculation completed for pipeline {pipeline_id}")
                        return True
                        
        except Exception as e:
            logger.error(f"Error checking/triggering pending phases: {e}")
            
        return False
    
    async def get_recent_pipelines(self, limit: int = 10) -> List[PipelineResult]:
        """Get recent pipeline executions"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM pipeline_executions 
                ORDER BY started_at DESC 
                LIMIT $1
                """,
                limit
            )
            
            results = []
            for row in rows:
                data = dict(row)
                # Map database field to model field
                if 'id' in data:
                    data['pipeline_id'] = data.pop('id')
                data['phase_results'] = json.loads(data['phase_results'] or '{}')
                data['errors'] = json.loads(data['errors'] or '[]')
                data['warnings'] = json.loads(data['warnings'] or '[]')
                data['api_calls_made'] = json.loads(data['api_calls_made'] or '{}')
                # Convert mode from uppercase to lowercase
                if 'mode' in data and isinstance(data['mode'], str):
                    data['mode'] = data['mode'].lower()
                results.append(PipelineResult(**data))
            
            return results

