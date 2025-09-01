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

from loguru import logger
from pydantic import BaseModel

from app.core.database import db_pool
from app.services.serp.serp_collector import SerpCollector
from app.services.enrichment.company_enricher import CompanyEnricher
from app.services.enrichment.video_enricher import VideoEnricher
from app.services.scraping.web_scraper import WebScraper
from app.services.analysis.content_analyzer import ContentAnalyzer
from app.services.metrics.dsi_calculator import DSICalculator
from app.services.historical_data_service import HistoricalDataService
from app.services.websocket_service import WebSocketService


class PipelineMode(str, Enum):
    BATCH_OPTIMIZED = "batch_optimized"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class PipelinePhase(str, Enum):
    SERP_COLLECTION = "serp_collection"
    COMPANY_ENRICHMENT = "company_enrichment"
    VIDEO_ENRICHMENT = "video_enrichment"
    CONTENT_SCRAPING = "content_scraping"
    CONTENT_ANALYSIS = "content_analysis"
    DSI_CALCULATION = "dsi_calculation"
    HISTORICAL_SNAPSHOT = "historical_snapshot"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineConfig(BaseModel):
    """Pipeline execution configuration"""
    keywords: Optional[List[str]] = None  # If None, uses all keywords
    regions: List[str] = ["US", "UK"]
    content_types: List[str] = ["organic", "news", "video"]
    
    # Execution settings
    max_concurrent_serp: int = 10
    max_concurrent_enrichment: int = 15
    max_concurrent_analysis: int = 20
    
    # Feature flags
    enable_company_enrichment: bool = True
    enable_video_enrichment: bool = True
    enable_content_analysis: bool = True
    enable_historical_tracking: bool = True
    force_refresh: bool = False
    
    # Scheduling (if applicable)
    schedule_id: Optional[UUID] = None
    scheduled_for: Optional[datetime] = None


class PipelineResult(BaseModel):
    """Pipeline execution result"""
    pipeline_id: UUID
    status: PipelineStatus
    mode: PipelineMode
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Phase results
    phase_results: Dict[str, Dict[str, Any]] = {}
    
    # Summary statistics
    keywords_processed: int = 0
    serp_results_collected: int = 0
    companies_enriched: int = 0
    videos_enriched: int = 0
    content_analyzed: int = 0
    
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
        
        # Initialize service dependencies
        self.serp_collector = SerpCollector(settings, db)
        self.company_enricher = CompanyEnricher(settings, db)
        self.video_enricher = VideoEnricher(settings, db)
        self.web_scraper = WebScraper(settings, db)
        self.content_analyzer = ContentAnalyzer(settings, db)
        self.dsi_calculator = DSICalculator(settings, db)
        self.historical_service = HistoricalDataService(db, settings)
        self.websocket_service = WebSocketService()
        
        # Pipeline state
        self._active_pipelines: Dict[UUID, PipelineResult] = {}
        self._lock = asyncio.Lock()
    
    async def start_pipeline(
        self,
        config: PipelineConfig,
        mode: PipelineMode = PipelineMode.BATCH_OPTIMIZED
    ) -> UUID:
        """Start a new pipeline execution"""
        pipeline_id = uuid4()
        
        # Create pipeline result
        result = PipelineResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.PENDING,
            mode=mode,
            started_at=datetime.utcnow()
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
    
    async def _execute_pipeline(self, pipeline_id: UUID, config: PipelineConfig):
        """Execute pipeline phases in sequence"""
        result = self._active_pipelines[pipeline_id]
        
        try:
            result.status = PipelineStatus.RUNNING
            await self._save_pipeline_state(result)
            await self._broadcast_status(pipeline_id, "Pipeline started")
            
            # Phase 1: SERP Collection
            logger.info(f"Pipeline {pipeline_id}: Starting SERP collection")
            await self._broadcast_status(pipeline_id, "Collecting SERP data...")
            
            serp_result = await self._execute_serp_collection_phase(config)
            result.phase_results[PipelinePhase.SERP_COLLECTION] = serp_result
            result.serp_results_collected = serp_result.get('total_results', 0)
            result.keywords_processed = serp_result.get('keywords_processed', 0)
            
            # Check for cancellation
            if result.status == PipelineStatus.CANCELLED:
                return
            
            # Phase 2: Company Enrichment
            if config.enable_company_enrichment and serp_result.get('unique_domains'):
                logger.info(f"Pipeline {pipeline_id}: Starting company enrichment")
                await self._broadcast_status(pipeline_id, "Enriching company data...")
                
                enrichment_result = await self._execute_company_enrichment_phase(
                    serp_result['unique_domains']
                )
                result.phase_results[PipelinePhase.COMPANY_ENRICHMENT] = enrichment_result
                result.companies_enriched = enrichment_result.get('companies_enriched', 0)
            
            # Phase 3: Video Enrichment
            if config.enable_video_enrichment and serp_result.get('video_urls'):
                logger.info(f"Pipeline {pipeline_id}: Starting video enrichment")
                await self._broadcast_status(pipeline_id, "Enriching video content...")
                
                video_result = await self._execute_video_enrichment_phase(
                    serp_result['video_urls']
                )
                result.phase_results[PipelinePhase.VIDEO_ENRICHMENT] = video_result
                result.videos_enriched = video_result.get('videos_enriched', 0)
            
            # Phase 4: Content Scraping
            if serp_result.get('content_urls'):
                logger.info(f"Pipeline {pipeline_id}: Starting content scraping")
                await self._broadcast_status(pipeline_id, "Scraping web content...")
                
                scraping_result = await self._execute_content_scraping_phase(
                    serp_result['content_urls']
                )
                result.phase_results[PipelinePhase.CONTENT_SCRAPING] = scraping_result
            
            # Phase 5: Content Analysis
            if config.enable_content_analysis:
                logger.info(f"Pipeline {pipeline_id}: Starting content analysis")
                await self._broadcast_status(pipeline_id, "Analyzing content with AI...")
                
                analysis_result = await self._execute_content_analysis_phase()
                result.phase_results[PipelinePhase.CONTENT_ANALYSIS] = analysis_result
                result.content_analyzed = analysis_result.get('content_analyzed', 0)
            
            # Phase 6: DSI Calculation
            logger.info(f"Pipeline {pipeline_id}: Calculating DSI metrics")
            await self._broadcast_status(pipeline_id, "Calculating DSI rankings...")
            
            dsi_result = await self._execute_dsi_calculation_phase()
            result.phase_results[PipelinePhase.DSI_CALCULATION] = dsi_result
            
            # Phase 7: Historical Snapshot (if enabled)
            if config.enable_historical_tracking:
                logger.info(f"Pipeline {pipeline_id}: Creating historical snapshot")
                await self._broadcast_status(pipeline_id, "Creating historical snapshot...")
                
                snapshot_result = await self._execute_historical_snapshot_phase()
                result.phase_results[PipelinePhase.HISTORICAL_SNAPSHOT] = snapshot_result
            
            # Complete pipeline
            result.status = PipelineStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            
            await self._broadcast_status(pipeline_id, "Pipeline completed successfully!")
            logger.info(f"Pipeline {pipeline_id} completed successfully")
            
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
    
    async def _execute_serp_collection_phase(self, config: PipelineConfig) -> Dict[str, Any]:
        """Execute SERP collection phase"""
        # Get keywords to process
        if config.keywords:
            keywords = await self._get_keywords_by_text(config.keywords)
        else:
            keywords = await self._get_all_keywords()
        
        # Collect SERP results for all keyword-region-type combinations
        total_results = 0
        unique_domains = set()
        video_urls = set()
        content_urls = set()
        
        semaphore = asyncio.Semaphore(config.max_concurrent_serp)
        
        async def collect_serp(keyword: Dict, region: str, content_type: str):
            nonlocal total_results
            async with semaphore:
                results = await self.serp_collector.collect_serp_results(
                    keyword['keyword'],
                    keyword['id'],
                    region,
                    content_type,
                    force_refresh=config.force_refresh
                )
                
                for result in results:
                    total_results += 1
                    unique_domains.add(result['domain'])
                    
                    if content_type == 'video' and 'youtube.com' in result['url']:
                        video_urls.add(result['url'])
                    elif content_type in ['organic', 'news']:
                        content_urls.add(result['url'])
                
                return len(results)
        
        # Create tasks for all combinations
        tasks = []
        for keyword in keywords:
            for region in config.regions:
                for content_type in config.content_types:
                    tasks.append(collect_serp(keyword, region, content_type))
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'keywords_processed': len(keywords),
            'total_results': total_results,
            'unique_domains': list(unique_domains),
            'video_urls': list(video_urls),
            'content_urls': list(content_urls),
            'regions': config.regions,
            'content_types': config.content_types
        }
    
    async def _execute_company_enrichment_phase(self, domains: List[str]) -> Dict[str, Any]:
        """Execute company enrichment phase"""
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
            'domains_processed': len(domains),
            'companies_enriched': companies_enriched,
            'errors': errors
        }
    
    async def _execute_video_enrichment_phase(self, video_urls: List[str]) -> Dict[str, Any]:
        """Execute video enrichment phase"""
        videos_enriched = 0
        errors = []
        
        semaphore = asyncio.Semaphore(5)  # YouTube API limits
        
        async def enrich_video(url: str):
            nonlocal videos_enriched
            async with semaphore:
                try:
                    result = await self.video_enricher.enrich_video(url)
                    if result:
                        videos_enriched += 1
                    return result
                except Exception as e:
                    errors.append(f"Failed to enrich video {url}: {str(e)}")
                    return None
        
        tasks = [enrich_video(url) for url in video_urls]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'videos_processed': len(video_urls),
            'videos_enriched': videos_enriched,
            'errors': errors
        }
    
    async def _execute_content_scraping_phase(self, urls: List[str]) -> Dict[str, Any]:
        """Execute content scraping phase"""
        scraped_count = 0
        errors = []
        
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
                    return result
                except Exception as e:
                    errors.append(f"Failed to scrape {url}: {str(e)}")
                    return None
        
        tasks = [scrape_url(url) for url in urls_to_scrape]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'urls_total': len(urls),
            'urls_scraped': scraped_count,
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
                        title=content_data.get('title')
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
            'content_processed': len(unanalyzed_content),
            'content_analyzed': analyzed_count,
            'errors': errors
        }
    
    async def _execute_dsi_calculation_phase(self) -> Dict[str, Any]:
        """Execute DSI calculation phase"""
        try:
            result = await self.dsi_calculator.calculate_dsi_rankings()
            return {
                'dsi_calculated': True,
                'companies_ranked': result.get('companies_ranked', 0),
                'pages_ranked': result.get('pages_ranked', 0)
            }
        except Exception as e:
            return {
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
    
    async def _save_pipeline_state(self, result: PipelineResult):
        """Save pipeline state to database"""
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pipeline_executions (
                    id, status, mode, started_at, completed_at,
                    phase_results, keywords_processed, serp_results_collected,
                    companies_enriched, videos_enriched, content_analyzed,
                    errors, warnings, api_calls_made, estimated_cost
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = EXCLUDED.completed_at,
                    phase_results = EXCLUDED.phase_results,
                    keywords_processed = EXCLUDED.keywords_processed,
                    serp_results_collected = EXCLUDED.serp_results_collected,
                    companies_enriched = EXCLUDED.companies_enriched,
                    videos_enriched = EXCLUDED.videos_enriched,
                    content_analyzed = EXCLUDED.content_analyzed,
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
                json.dumps(result.phase_results),
                result.keywords_processed,
                result.serp_results_collected,
                result.companies_enriched,
                result.videos_enriched,
                result.content_analyzed,
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
    
    async def _cleanup_pipeline_after_delay(self, pipeline_id: UUID, delay_seconds: int):
        """Remove pipeline from memory after delay"""
        await asyncio.sleep(delay_seconds)
        async with self._lock:
            if pipeline_id in self._active_pipelines:
                del self._active_pipelines[pipeline_id]
                logger.info(f"Pipeline {pipeline_id} removed from memory")
    
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
                data['phase_results'] = json.loads(data['phase_results'] or '{}')
                data['errors'] = json.loads(data['errors'] or '[]')
                data['warnings'] = json.loads(data['warnings'] or '[]')
                data['api_calls_made'] = json.loads(data['api_calls_made'] or '{}')
                results.append(PipelineResult(**data))
            
            return results
