"""Keyword processing logic with multi-location support."""

import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import structlog

from .config import Settings
from .models import (
    KeywordMetricsRequest, KeywordMetricsJob, KeywordMetrics,
    KeywordIdea, JobStatus, KeywordMetricsEvent
)
from .google_ads_client import GoogleAdsClient
from .database import Database
from .bigquery_client import BigQueryClient
from .cache import CacheManager
from .pubsub import PubSubClient

logger = structlog.get_logger()


class KeywordProcessor:
    """Processes keyword metrics requests with multi-location support."""
    
    def __init__(
        self,
        settings: Settings,
        google_ads_client: GoogleAdsClient,
        database: Database,
        bigquery_client: BigQueryClient,
        cache_manager: CacheManager,
        pubsub_client: PubSubClient
    ):
        self.settings = settings
        self.google_ads = google_ads_client
        self.db = database
        self.bigquery = bigquery_client
        self.cache = cache_manager
        self.pubsub = pubsub_client
        
        # Location name mapping (could be loaded from config)
        self.location_names = {
            "2840": "United States",
            "2826": "United Kingdom", 
            "2124": "Canada",
            "2036": "Australia",
            "2276": "Germany",
            "2250": "France",
            # Add more as needed
        }
    
    async def process_keywords(
        self,
        request: KeywordMetricsRequest,
        job: KeywordMetricsJob
    ) -> Tuple[int, int]:
        """Process keywords for all specified locations."""
        total_metrics = 0
        total_ideas = 0
        
        try:
            # Update job status
            job.status = JobStatus.RUNNING
            await self._update_job(job)
            
            # Process each location
            for location in request.locations:
                logger.info(
                    "processing_location",
                    job_id=job.job_id,
                    location=location,
                    location_name=self.location_names.get(location, location)
                )
                
                location_metrics, location_ideas = await self._process_location(
                    request, job, location
                )
                
                total_metrics += location_metrics
                total_ideas += location_ideas
                
                # Update job progress
                job.update_progress(location, len(request.keywords), location_metrics)
                await self._update_job(job)
            
            # Mark job as completed
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await self._update_job(job)
            
            # Publish completion event
            await self._publish_completion_event(job, request.locations)
            
            logger.info(
                "job_completed",
                job_id=job.job_id,
                total_metrics=total_metrics,
                total_ideas=total_ideas,
                locations_processed=len(request.locations)
            )
            
        except Exception as e:
            logger.error(
                "job_failed",
                job_id=job.job_id,
                error=str(e),
                exc_info=True
            )
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            await self._update_job(job)
            raise
        
        return total_metrics, total_ideas
    
    async def _process_location(
        self,
        request: KeywordMetricsRequest,
        job: KeywordMetricsJob,
        location: str
    ) -> Tuple[int, int]:
        """Process keywords for a single location."""
        metrics_count = 0
        ideas_count = 0
        
        # Check cache first (unless force refresh)
        cached_keywords = set()
        if not request.force_refresh:
            for keyword in request.keywords:
                cached = await self.cache.get_keyword_metrics(
                    request.client_id,
                    keyword,
                    location
                )
                if cached:
                    cached_keywords.add(keyword)
        
        # Keywords to fetch from API
        keywords_to_fetch = [
            kw for kw in request.keywords 
            if kw not in cached_keywords
        ]
        
        logger.info(
            "cache_status",
            location=location,
            total_keywords=len(request.keywords),
            cached=len(cached_keywords),
            to_fetch=len(keywords_to_fetch)
        )
        
        # Fetch from Google Ads API if needed
        if keywords_to_fetch:
            # Batch process keywords
            batch_size = self.settings.batch_size
            for i in range(0, len(keywords_to_fetch), batch_size):
                batch = keywords_to_fetch[i:i + batch_size]
                
                try:
                    # Get metrics from Google Ads
                    metrics, ideas = await self.google_ads.get_keyword_metrics(
                        keywords=batch,
                        language=request.language,
                        location=location,
                        include_ideas=request.include_ideas,
                        ideas_limit=request.ideas_limit
                    )
                    
                    # Process and store metrics
                    for metric_data in metrics:
                        if metric_data.get('keyword'):
                            keyword_metric = KeywordMetrics(
                                keyword=metric_data['keyword'],
                                location=location,
                                location_name=self.location_names.get(location),
                                keyword_category=request.keyword_category,
                                avg_monthly_searches=metric_data.get('avg_monthly_searches'),
                                competition=metric_data.get('competition'),
                                competition_index=metric_data.get('competition_index'),
                                low_top_of_page_bid_micros=metric_data.get('low_top_of_page_bid_micros'),
                                high_top_of_page_bid_micros=metric_data.get('high_top_of_page_bid_micros'),
                                cpc_low=metric_data.get('cpc_low'),
                                cpc_high=metric_data.get('cpc_high')
                            )
                            
                            # Store in database and cache
                            await self._store_keyword_metrics(
                                request.client_id,
                                keyword_metric
                            )
                            
                            if keyword_metric.has_data:
                                metrics_count += 1
                    
                    # Process ideas if any
                    ideas_count += len(ideas)
                    if ideas and request.project_id:
                        await self._store_keyword_ideas(
                            request.client_id,
                            request.project_id,
                            ideas,
                            location
                        )
                    
                except Exception as e:
                    logger.error(
                        "batch_processing_error",
                        location=location,
                        batch_start=i,
                        batch_size=len(batch),
                        error=str(e)
                    )
                    # Continue with next batch
                    continue
                
                # Update progress
                job.update_progress(
                    location,
                    min(i + batch_size, len(keywords_to_fetch)),
                    metrics_count
                )
                await self._update_job(job)
        
        # Count cached keywords as found
        metrics_count += len(cached_keywords)
        
        return metrics_count, ideas_count
    
    async def _store_keyword_metrics(
        self,
        client_id: str,
        metrics: KeywordMetrics
    ):
        """Store keyword metrics in database and cache."""
        # Store in Cloud SQL
        await self.db.store_keyword_metrics(
            client_id=client_id,
            keyword=metrics.keyword,
            location=metrics.location,
            metrics=metrics.model_dump()
        )
        
        # Store in BigQuery
        await self.bigquery.insert_keyword_metrics(
            client_id=client_id,
            metrics=[metrics.model_dump()]
        )
        
        # Update cache
        await self.cache.set_keyword_metrics(
            client_id=client_id,
            keyword=metrics.keyword,
            location=metrics.location,
            metrics=metrics
        )
    
    async def _store_keyword_ideas(
        self,
        client_id: str,
        project_id: str,
        ideas: List[Dict],
        location: str
    ):
        """Store keyword ideas."""
        idea_models = []
        for idea in ideas:
            idea_model = KeywordIdea(**idea)
            idea_models.append({
                **idea_model.model_dump(),
                "client_id": client_id,
                "project_id": project_id,
                "location": location,
                "created_at": datetime.utcnow()
            })
        
        if idea_models:
            await self.bigquery.insert_keyword_ideas(idea_models)
    
    async def _update_job(self, job: KeywordMetricsJob):
        """Update job in cache."""
        await self.cache.set_job(job.job_id, job)
    
    async def _publish_completion_event(
        self,
        job: KeywordMetricsJob,
        locations: List[str]
    ):
        """Publish job completion event."""
        event = KeywordMetricsEvent(
            client_id=job.client_id,
            project_id=job.project_id,
            job_id=job.job_id,
            keywords_processed=job.processed_keywords,
            metrics_found=job.metrics_found,
            ideas_found=job.ideas_found,
            locations_processed=locations
        )
        
        await self.pubsub.publish_metrics_ready(event) 