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
from app.services.enrichment.company_enricher import CompanyEnricher
from app.services.enrichment.video_enricher import OptimizedVideoEnricher as VideoEnricher
from app.services.scraping.web_scraper import WebScraper
# from app.services.analysis.content_analyzer import ContentAnalyzer  # Moved to redundant
from app.services.metrics.simplified_dsi_calculator import SimplifiedDSICalculator as DSICalculator
from app.services.keywords.simplified_google_ads_service import SimplifiedGoogleAdsService
from app.services.historical_data_service import HistoricalDataService
from app.services.landscape.production_landscape_calculator import ProductionLandscapeCalculator
from app.services.websocket_service import WebSocketService
from app.services.pipeline.pipeline_phases import PipelinePhaseManager


class PipelineMode(str, Enum):
    BATCH_OPTIMIZED = "batch_optimized"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    TESTING = "testing"  # Force full pipeline run for testing


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
        self.company_enricher = CompanyEnricher(settings, db)
        self.video_enricher = VideoEnricher(db, settings)
        self.web_scraper = WebScraper(settings, db)
        # Use Optimized Unified Analyzer for reduced verbosity and better performance
        from app.services.analysis.optimized_unified_analyzer import OptimizedUnifiedAnalyzer
        self.content_analyzer = OptimizedUnifiedAnalyzer(settings, db)
        self.dsi_calculator = DSICalculator(settings, db)
        self.google_ads_service = SimplifiedGoogleAdsService()
        self.landscape_calculator = ProductionLandscapeCalculator(db)
        self.historical_service = HistoricalDataService(db, settings)
        self.websocket_service = WebSocketService()
        
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
    
    async def _get_existing_serp_results(self, config: PipelineConfig, pipeline_id: UUID) -> Dict[str, Any]:
        """Get count of existing SERP results for webhook-triggered pipelines"""
        try:
            async with self.db.acquire() as conn:
                # Get count of recent SERP results
                count_result = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as total_results,
                           COUNT(DISTINCT k.keyword) as keywords_processed,
                           COUNT(DISTINCT sr.domain) as unique_domains,
                           COUNT(DISTINCT CASE WHEN sr.url LIKE '%youtube.com%' THEN sr.url END) as video_urls
                    FROM serp_results sr
                    JOIN keywords k ON k.id = sr.keyword_id
                    WHERE sr.search_date > CURRENT_DATE - INTERVAL '24 hours'
                    """,
                )
                
                # Get unique domains and video URLs
                domains_result = await conn.fetch(
                    """
                    SELECT DISTINCT domain 
                    FROM serp_results 
                    WHERE search_date > CURRENT_DATE - INTERVAL '24 hours'
                    LIMIT 1000
                    """
                )
                
                videos_result = await conn.fetch(
                    """
                    SELECT DISTINCT url 
                    FROM serp_results 
                    WHERE url LIKE '%youtube.com%'
                    AND search_date > CURRENT_DATE - INTERVAL '24 hours'
                    LIMIT 1000
                    """
                )
                
                return {
                    'total_results': count_result['total_results'],
                    'keywords_processed': count_result['keywords_processed'],
                    'unique_domains': [row['domain'] for row in domains_result],
                    'video_urls': [row['url'] for row in videos_result]
                }
        except Exception as e:
            logger.error(f"Failed to get existing SERP results: {str(e)}")
            return {
                'total_results': 0,
                'keywords_processed': 0,
                'unique_domains': [],
                'video_urls': []
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
            result.status = PipelineStatus.RUNNING
            await self._save_pipeline_state(result)
            await self._broadcast_status(pipeline_id, "Pipeline started")
            
            # Phase 1: Keyword Metrics Enrichment (if enabled)
            if config.enable_keyword_metrics:
                logger.info(f"🎯 Pipeline {pipeline_id}: Starting keyword metrics enrichment")
                logger.info(f"🎯 Config.enable_keyword_metrics = {config.enable_keyword_metrics}")
                await self._broadcast_status(pipeline_id, "Enriching keyword metrics...")
                
                logger.info(f"🎯 About to call _execute_keyword_metrics_enrichment_phase...")
                keyword_metrics_result = await self._execute_keyword_metrics_enrichment_phase(config, pipeline_id)
                logger.info(f"🎯 Keyword metrics phase returned: {keyword_metrics_result}")
                
                result.phase_results[PipelinePhase.KEYWORD_METRICS_ENRICHMENT] = keyword_metrics_result
                result.keywords_with_metrics = keyword_metrics_result.get('keywords_with_metrics', 0)
                logger.info(f"🎯 Phase 1 complete, moving to Phase 2...")
            else:
                logger.info(f"🎯 Keyword metrics enrichment DISABLED in config")
            
            # Phase 2: SERP Collection
            if config.enable_serp_collection:
                logger.info(f"🔍 PIPELINE PHASE 2: Starting SERP collection for pipeline {pipeline_id}")
                logger.info(f"🔍 PIPELINE: About to call _execute_serp_collection_phase with config: {config}")
                await self._broadcast_status(pipeline_id, "Collecting SERP data...")
                
                logger.info(f"🔍 CALLING: _execute_serp_collection_phase(config, {pipeline_id})")
                serp_result = await self._execute_serp_collection_phase(config, pipeline_id)
                logger.info(f"🔍 SERP PHASE COMPLETED: {serp_result}")
                result.phase_results[PipelinePhase.SERP_COLLECTION] = serp_result
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
                    
                    result.phase_results[PipelinePhase.SERP_COLLECTION] = serp_result
                    result.serp_results_collected = serp_result.get('total_results', 0)
                    result.keywords_processed = serp_result.get('keywords_processed', 0)
                    
                    # Update metrics
                    await self._update_pipeline_metrics(
                        str(pipeline_id),
                        keywords_processed=result.keywords_processed,
                        serp_results_collected=result.serp_results_collected
                    )
                else:
                    logger.warning("⚠️ No batch_id provided for webhook pipeline, getting existing results")
                    serp_result = await self._get_existing_serp_results(config, pipeline_id)
                    result.phase_results[PipelinePhase.SERP_COLLECTION] = serp_result
                    result.serp_results_collected = serp_result.get('total_results', 0)
            
            # Check for cancellation
            if result.status == PipelineStatus.CANCELLED:
                return
            
            # Phase 3: Company Enrichment
            if config.enable_company_enrichment and serp_result.get('unique_domains'):
                logger.info(f"Pipeline {pipeline_id}: Starting company enrichment")
                await self._broadcast_status(pipeline_id, "Enriching company data...")
                
                enrichment_result = await self._execute_company_enrichment_phase(
                    serp_result['unique_domains']
                )
                result.phase_results[PipelinePhase.COMPANY_ENRICHMENT] = enrichment_result
                result.companies_enriched = enrichment_result.get('companies_enriched', 0)
                
                # Update metrics in real-time
                await self._update_pipeline_metrics(
                    str(pipeline_id),
                    companies_enriched=result.companies_enriched
                )
            
            # Phase 4: Video Enrichment
            if config.enable_video_enrichment and serp_result.get('video_urls'):
                logger.info(f"Pipeline {pipeline_id}: Starting video enrichment")
                await self._broadcast_status(pipeline_id, "Enriching video content...")
                
                try:
                    video_result = await self._execute_video_enrichment_phase(
                        serp_result['video_urls'],
                        pipeline_execution_id=str(pipeline_id)
                    )
                    result.phase_results[PipelinePhase.VIDEO_ENRICHMENT] = video_result
                    result.videos_enriched = video_result.get('videos_enriched', 0)
                except Exception as e:
                    logger.warning(f"Video enrichment failed (possibly due to network restrictions): {e}")
                    result.phase_results[PipelinePhase.VIDEO_ENRICHMENT] = {
                        'success': False,
                        'videos_enriched': 0,
                        'error': str(e),
                        'skipped_reason': 'Network restrictions may be blocking YouTube API'
                    }
            
            # Phase 5: Content Scraping
            if config.enable_content_scraping and serp_result.get('content_urls'):
                logger.info(f"Pipeline {pipeline_id}: Starting content scraping")
                await self._broadcast_status(pipeline_id, "Scraping web content...")
                
                scraping_result = await self._execute_content_scraping_phase(
                    serp_result['content_urls']
                )
                result.phase_results[PipelinePhase.CONTENT_SCRAPING] = scraping_result
            
            # Phase 6: Content Analysis
            if config.enable_content_analysis:
                logger.info(f"Pipeline {pipeline_id}: Starting content analysis")
                await self._broadcast_status(pipeline_id, "Analyzing content with AI...")
                
                analysis_result = await self._execute_content_analysis_phase()
                result.phase_results[PipelinePhase.CONTENT_ANALYSIS] = analysis_result
                result.content_analyzed = analysis_result.get('content_analyzed', 0)
            
            # Phase 7: DSI Calculation
            # Check all DSI dependencies using PhaseOrchestrator logic
            # DSI depends on: content_analysis, company_enrichment_youtube
            dsi_dependencies_met = True
            dsi_skip_reasons = []
            
            # Check if we have SERP results (foundation for everything)
            if result.serp_results_collected == 0:
                dsi_dependencies_met = False
                dsi_skip_reasons.append("No SERP results collected")
            
            # Check content_analysis dependency
            if config.enable_content_analysis:
                content_analysis_result = result.phase_results.get(PipelinePhase.CONTENT_ANALYSIS, {})
                if not content_analysis_result.get('success', False) or content_analysis_result.get('content_analyzed', 0) == 0:
                    dsi_dependencies_met = False
                    dsi_skip_reasons.append("Content analysis did not complete successfully")
            
            # Check company_enrichment dependency (both SERP and YouTube enrichment)
            if config.enable_company_enrichment:
                company_enrichment_result = result.phase_results.get(PipelinePhase.COMPANY_ENRICHMENT, {})
                if not company_enrichment_result.get('success', False):
                    dsi_dependencies_met = False
                    dsi_skip_reasons.append("Company enrichment (SERP) did not complete successfully")
            
            # Check video enrichment if enabled (for company_enrichment_youtube dependency)
            if config.enable_video_enrichment:
                video_enrichment_result = result.phase_results.get(PipelinePhase.VIDEO_ENRICHMENT, {})
                if not video_enrichment_result.get('success', False):
                    dsi_dependencies_met = False
                    dsi_skip_reasons.append("Video enrichment did not complete successfully")
            
            if dsi_dependencies_met:
                logger.info(f"Pipeline {pipeline_id}: Calculating DSI metrics")
                await self._broadcast_status(pipeline_id, "Calculating DSI rankings...")
                
                dsi_result = await self._execute_dsi_calculation_phase()
                result.phase_results[PipelinePhase.DSI_CALCULATION] = dsi_result
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
            
            # Complete pipeline
            result.status = PipelineStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            
            await self._broadcast_status(pipeline_id, "Pipeline completed successfully!")
            logger.info(f"Pipeline {pipeline_id} completed successfully")
            
            # Save final result
            await self._save_pipeline_state(result)
            
        except Exception as e:
            result.status = PipelineStatus.FAILED
            result.completed_at = datetime.utcnow()
            result.errors.append(str(e))
            
            await self._broadcast_status(pipeline_id, f"Pipeline failed: {str(e)}")
            logger.error(f"Pipeline {pipeline_id} failed: {e}")
        
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
            logger.info(f"🔍 No specific keywords provided - getting all project keywords")
            keywords = await self._get_all_keywords()
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
                # Initialize state tracking for SERP items
                await state_tracker.initialize_pipeline(
                    pipeline_id, 
                    ["serp_collection"], 
                    serp_items
                )
                logger.info(f"🔧 STATE TRACKING: Initialized {len(serp_items)} SERP items for tracking")
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
        if total_results > 0:
            # Since batch mode stores results directly, query the database
            unique_domains = await self._get_unique_serp_domains()
            video_urls = await self._get_video_urls_from_serp()
            logger.info(f"🔍 Found {len(unique_domains)} unique domains and {len(video_urls)} video URLs from batch results")
        
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
            'video_urls': video_urls
        }
    
    async def _execute_company_enrichment_phase(self, domains: List[str], phase_name: str = "default") -> Dict[str, Any]:
        """Execute company enrichment phase
        
        Args:
            domains: List of domains to enrich
            phase_name: Name of the phase for logging (e.g., 'serp_domains', 'youtube_domains')
        """
        logger.info(f"🏢 Starting company enrichment for {phase_name}: {len(domains)} domains")
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
                except Exception as e:
                    errors.append(f"Failed to enrich {domain}: {str(e)}")
                    return None
        
        tasks = [enrich_domain(domain) for domain in domains]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'success': companies_enriched > 0 or len(domains) == 0,
            'phase_name': phase_name,
            'domains_processed': len(domains),
            'companies_enriched': companies_enriched,
            'errors': errors
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
        
        logger.info(f"📹 Video enrichment complete: "
                   f"{total_enriched} enriched, {total_cached} cached, {total_failed} failed")
        
        return {
            'success': total_enriched > 0 or total_cached > 0 or len(video_urls) == 0,
            'videos_processed': len(video_urls),
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
        
        # Filter out already scraped URLs if not force refresh
        urls_to_scrape = await self._filter_unscraped_urls(urls)
        
        semaphore = asyncio.Semaphore(50)  # ScrapingBee limits
        
        async def scrape_url(url: str):
            nonlocal scraped_count
            async with semaphore:
                try:
                    result = await self.web_scraper.scrape(url)
                    if result and result.get('content'):
                        scraped_count += 1
                        # Store in database
                        await self._store_scraped_content(result)
                        scraped_results.append(result)
                    return result
                except Exception as e:
                    errors.append(f"Failed to scrape {url}: {str(e)}")
                    return None
        
        tasks = [scrape_url(url) for url in urls_to_scrape]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'urls_total': len(urls),
            'urls_scraped': scraped_count,
            'scraped_results': scraped_results,
            'errors': errors
        }
    
    async def _execute_content_analysis_phase(self) -> Dict[str, Any]:
        """Execute content analysis phase"""
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
    
    async def _execute_dsi_calculation_phase(self) -> Dict[str, Any]:
        """Execute DSI calculation phase"""
        try:
            result = await self.dsi_calculator.calculate_dsi_rankings()
            return {
                'success': True,
                'dsi_calculated': True,
                'companies_ranked': result.get('companies_ranked', 0),
                'pages_ranked': result.get('pages_ranked', 0)
            }
        except Exception as e:
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
                logger.info(f"🔍 Getting all keywords from database")
                keywords = await self._get_all_keywords()
            
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
            
            logger.info(f"Enriching {len(keyword_texts)} keywords with Google Ads historical metrics across {len(config.regions)} countries")
            
            # Debug logging for Google Ads service availability
            logger.info(f"Checking Google Ads service availability...")
            logger.info(f"Has google_ads_service attribute: {hasattr(self, 'google_ads_service')}")
            
            # Use Enhanced Google Ads service for batch processing (if available)
            if hasattr(self, 'google_ads_service'):
                logger.info(f"Google Ads service found! Calling get_historical_metrics_batch...")
                logger.info(f"Keywords to process: {keyword_texts}")
                logger.info(f"Countries: {config.regions}")
                
                try:
                    logger.info(f"🚀 HOT FIX: Using direct API call pattern that worked!")
                    
                    # Use the exact same direct API pattern that succeeded
                    country_metrics = {}
                    for country in config.regions:
                        try:
                            from google.ads.googleads.client import GoogleAdsClient
                            from app.core.config import settings
                            
                            # Exact same credentials as working direct test
                            credentials = {
                                'developer_token': settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                                'client_id': settings.GOOGLE_ADS_CLIENT_ID,
                                'client_secret': settings.GOOGLE_ADS_CLIENT_SECRET,
                                'refresh_token': settings.GOOGLE_ADS_REFRESH_TOKEN,
                                'login_customer_id': settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
                                'use_proto_plus': True
                            }
                            
                            client = GoogleAdsClient.load_from_dict(credentials)
                            
                            # 🔧 HOT FIX: Use EXACT same customer ID as working direct test
                            customer_id = settings.GOOGLE_ADS_CUSTOMER_ID or settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
                            logger.info(f"🔧 Using EXACT same customer_id as working direct test: {customer_id}")
                            logger.info(f"🔧 This customer ID returned 1,630 keyword ideas in direct test!")
                            
                            # Exact same API call as working test
                            keyword_service = client.get_service("KeywordPlanIdeaService")
                            request = client.get_type("GenerateKeywordIdeasRequest")
                            request.customer_id = customer_id
                            request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
                            request.language = client.get_service("GoogleAdsService").language_constant_path("1000")
                            
                            geo_map = {'US': '2840', 'UK': '2826', 'CA': '2124'}
                            geo_id = geo_map.get(country, '2840')
                            request.geo_target_constants.append(
                                client.get_service("GoogleAdsService").geo_target_constant_path(geo_id)
                            )
                            request.keyword_seed.keywords.extend(keyword_texts)
                            
                            logger.info(f"🎯 Direct API call for {country} with geo_id {geo_id}")
                            response = keyword_service.generate_keyword_ideas(request=request)
                            
                            # Process results - EXACT same pattern as working test
                            keyword_metrics = []
                            results = list(response.results)
                            logger.info(f"📊 API SUCCESS: {len(results)} keyword ideas for {country}")
                            
                            # Create metrics using working pattern
                            for result in results[:len(keyword_texts)]:  # Take first N results
                                idea_metrics = result.keyword_idea_metrics
                                keyword_metric = {
                                    'keyword': result.text,
                                    'keyword_id': keyword_id_map.get(result.text),  # Map to keyword ID
                                    'avg_monthly_searches': idea_metrics.avg_monthly_searches if idea_metrics else 0,
                                    'competition_level': idea_metrics.competition.name if idea_metrics and idea_metrics.competition else "UNKNOWN"
                                }
                                keyword_metrics.append(keyword_metric)
                                logger.info(f"✅ {result.text}: {keyword_metric['avg_monthly_searches']} searches, {keyword_metric['competition_level']} competition")
                            
                            country_metrics[country] = keyword_metrics
                            
                            # 💾 HOT FIX: Store Google Ads data in database  
                            if keyword_metrics:
                                logger.info(f"💾 Storing {len(keyword_metrics)} Google Ads metrics for {country}")
                                await self._store_google_ads_metrics(keyword_metrics, country, str(pipeline_id))
                            
                        except Exception as e:
                            logger.error(f"❌ Direct API call failed for {country}: {e}")
                            country_metrics[country] = []
                    
                    logger.info(f"🎉 Direct Google Ads API pattern completed!")
                    logger.info(f"📊 Total results: {sum(len(m) for m in country_metrics.values())} metrics")
                    
                except Exception as e:
                    logger.error(f"💥 Google Ads direct pattern failed: {str(e)}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    country_metrics = {country: [] for country in config.regions}
            else:
                logger.warning("Google Ads service not available - skipping keyword metrics enrichment")
                country_metrics = {country: [] for country in config.regions}
            
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
    
    async def _get_all_keywords(self) -> List[Dict]:
        """Get all keyword records"""
        async with db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT id, keyword, category, jtbd_stage
                FROM keywords 
                ORDER BY keyword
                """
            )
            return [dict(row) for row in results]
    
    async def _get_unique_serp_domains(self) -> List[str]:
        """Get unique domains from all SERP results"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetch(
                    """
                    SELECT DISTINCT domain 
                    FROM serp_results 
                    WHERE domain IS NOT NULL 
                    AND domain != ''
                    AND created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY domain
                    """
                )
                return [row['domain'] for row in result]
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
                    AND created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY url
                    """
                )
                return [row['url'] for row in result]
        except Exception as e:
            logger.error(f"Error getting video URLs: {e}")
            return []
    
    async def _get_content_urls_from_serp(self) -> List[str]:
        """Get content URLs from SERP results for scraping"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.fetch(
                    """
                    SELECT DISTINCT url, MIN(position) as min_position
                    FROM serp_results 
                    WHERE serp_type IN ('organic', 'news')
                    AND url IS NOT NULL 
                    AND url != ''
                    AND created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY url
                    ORDER BY min_position, url
                    """
                )
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
                    WHERE yv.created_at >= NOW() - INTERVAL '24 hours'
                    AND yv.channel_custom_url IS NOT NULL
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
        
        async with db_pool.acquire() as conn:
            scraped = await conn.fetch(
                """
                SELECT url FROM scraped_content 
                WHERE url = ANY($1::text[]) AND status = 'completed'
                """,
                urls
            )
            scraped_urls = {row['url'] for row in scraped}
            return [url for url in urls if url not in scraped_urls]
    
    async def _store_scraped_content(self, result: Dict) -> None:
        """Store scraped content in database"""
        from urllib.parse import urlparse
        
        if not result or not result.get('url'):
            return
        
        # Extract domain from URL
        parsed_url = urlparse(result['url'])
        domain = parsed_url.netloc
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO scraped_content (
                    url, domain, title, content, html, meta_description,
                    word_count, content_type, scraped_at, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    html = EXCLUDED.html,
                    meta_description = EXCLUDED.meta_description,
                    word_count = EXCLUDED.word_count,
                    content_type = EXCLUDED.content_type,
                    scraped_at = EXCLUDED.scraped_at,
                    status = EXCLUDED.status
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
                'completed' if result.get('content') else 'failed'
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
                json.dumps(result.phase_results, cls=DecimalEncoder),
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
                        await conn.execute("""
                            INSERT INTO historical_keyword_metrics (
                                snapshot_date, keyword_id, keyword_text, country_code, source,
                                pipeline_execution_id, avg_monthly_searches, 
                                competition_level
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT DO NOTHING
                        """,
                            snapshot_date,
                            metric.get('keyword_id'),  # Include keyword_id
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

