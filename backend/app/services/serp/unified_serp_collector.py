"""
Unified SERP Collection Service with Batch Support and Robustness Features
Combines functionality from both serp_collector.py and enhanced_serp_collector.py
"""

import httpx
import asyncio
import os
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, date, timedelta, timezone
import json
from urllib.parse import urlparse
from loguru import logger
import re

from app.core.config import settings as get_settings, Settings
from app.models.serp import SERPType
from app.core.database import get_db
from app.core.robustness_logging import get_logger, log_performance


class UnifiedSERPCollector:
    """
    Unified Scale SERP API client with:
    - Batch API support
    - Circuit breaker integration
    - Retry management
    - Enhanced logging
    - State tracking
    """
    
    def __init__(
        self, 
        settings=None, 
        db=None, 
        redis=None, 
        circuit_breaker=None, 
        retry_manager=None
    ):
        if settings is None:
            settings = get_settings()
        self.settings = settings
        self.api_key = settings.SCALE_SERP_API_KEY
        self.base_url = getattr(settings, 'SCALE_SERP_BASE_URL', 'https://api.scaleserp.com/search')
        self.batch_base_url = 'https://api.scaleserp.com/batches'
        self.monthly_limit = getattr(settings, 'SCALE_SERP_MONTHLY_LIMIT', 10000)
        self.overusage_limit = getattr(settings, 'SCALE_SERP_OVERUSAGE_LIMIT', 15000)
        self.db = db
        self.redis = redis
        self.circuit_breaker = circuit_breaker
        self.retry_manager = retry_manager
        self.logger = get_logger("unified_serp_collector")
        self.client = None  # Will be created when needed
        
        # Batch-specific settings
        self.batch_size_limit = 15000  # Scale SERP batch limit
        self.monitor_interval = 120  # Check every 2 minutes (reduced from 60s since we have webhooks)
        self.batch_timeout = 30 * 60  # 30 minutes max wait
        self.use_webhooks = bool(os.getenv("SCALESERP_WEBHOOK_URL"))  # Whether webhooks are configured
    
    async def _scale_serp_request(self, method: str, path: str, **kwargs):
        """Make an async request to Scale SERP API"""
        if not self.client:
            self.client = httpx.AsyncClient(timeout=30.0)
        
        url = f"https://api.scaleserp.com{path}"
        params = kwargs.get('params', {})
        params['api_key'] = self.api_key
        kwargs['params'] = params
        
        # Check if we want CSV format
        return_raw = params.get('format') == 'csv'
        
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        
        if return_raw:
            return response  # Return raw response for CSV
        return response.json()
    
    @log_performance("serp_collector", "search")
    async def search(self, keyword: str, result_type: str = "organic", **kwargs) -> Dict:
        """
        Perform a single search using Scale SERP API with robustness features
        
        Args:
            keyword: Search query
            result_type: Type of results to fetch ('organic', 'news', 'videos')
            **kwargs: Additional parameters (location, device, num_results, gl, hl, etc.)
            
        Returns:
            Dict containing flattened search results
        """
        # Extract parameters with defaults
        location = kwargs.get('location', 'United States')
        device = kwargs.get('device', 'desktop')
        # Enforce per-type caps to avoid gigantic result sets
        max_per_type = getattr(self.settings, 'SERP_MAX_RESULTS_PER_TYPE', 50)
        requested = kwargs.get('num_results', max_per_type)
        num_results = min(int(requested), int(max_per_type))
        gl = kwargs.get('gl', 'us')
        hl = kwargs.get('hl', 'en')
        
        params = {
            "api_key": self.api_key,
            "q": keyword,
            "location": location,
            "device": device,
            "num": num_results,
            "gl": gl,
            "hl": hl,
            "output": "json"
        }
        
        # Add search type specific parameters
        if result_type == "news":
            params["search_type"] = "news"
            # Add time period for news searches
            time_period = kwargs.get('time_period', 'last_day')
            params["time_period"] = time_period
            
            # If custom time period, add min/max parameters
            if time_period == 'custom':
                if kwargs.get('time_period_min'):
                    params["time_period_min"] = kwargs['time_period_min']
                if kwargs.get('time_period_max'):
                    params["time_period_max"] = kwargs['time_period_max']
                    
        elif result_type in ["videos", "video"]:
            params["search_type"] = "videos"
            
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in ['location', 'device', 'num_results', 'gl', 'hl', 'result_type']:
                params[key] = value
        
        # If circuit breaker is available, use it
        if self.circuit_breaker:
            return await self.circuit_breaker.call(
                self._perform_search,
                keyword,
                result_type,
                params,
                fallback=lambda *args: self._fallback_response(keyword, result_type, "Circuit breaker open")
            )
        else:
            return await self._perform_search(keyword, result_type, params)
    
    async def _perform_search(self, keyword: str, result_type: str, params: Dict) -> Dict:
        """Internal method to perform the actual search"""
        start_time = datetime.utcnow()
        
        async def make_request():
            if not self.client:
                self.client = httpx.AsyncClient(timeout=30.0)
                
            self.logger.api_call(
                service="scale_serp",
                method="GET",
                url=self.base_url,
                keyword=keyword,
                result_type=result_type
            )
            
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            
            # Log successful API call
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.logger.api_call(
                service="scale_serp",
                method="GET",
                url=self.base_url,
                status=response.status_code,
                duration_ms=duration_ms,
                keyword=keyword,
                result_type=result_type
            )
            
            return response
        
        try:
            # Use retry manager if available
            if self.retry_manager:
                response = await self.retry_manager.retry_with_backoff(
                    make_request,
                    entity_type='serp_search',
                    entity_id=f"{keyword}_{result_type}"
                )
            else:
                response = await make_request()
            
            data = response.json()
            
            # Log API usage
            await self._log_api_usage(keyword, response.headers)
            
            # Extract and flatten results based on type
            flattened_results = self._extract_results(data, result_type)
            
            # Log performance metrics
            self.logger.performance(
                "serp_extraction",
                len(flattened_results),
                unit="results",
                keyword=keyword,
                result_type=result_type
            )
            
            return {
                "success": True,
                "keyword": keyword,
                "result_type": result_type,
                "total_results": len(flattened_results),
                "results": flattened_results,
                "search_metadata": {
                    "created_at": datetime.utcnow().isoformat(),
                    "device": params.get("device"),
                    "location": params.get("location"),
                    "query": keyword,
                    "num_results": params.get("num"),
                    "api_response_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
                }
            }
            
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"Scale SERP API HTTP error",
                error=e,
                status_code=e.response.status_code,
                keyword=keyword,
                result_type=result_type
            )
            
            # Check if rate limited
            if e.response.status_code == 429:
                self.logger.warning("Rate limit hit for Scale SERP API")
            
            return {
                "success": False,
                "keyword": keyword,
                "result_type": result_type,
                "error": str(e),
                "status_code": e.response.status_code,
                "error_category": "http_error"
            }
            
        except Exception as e:
            self.logger.error(
                f"Unexpected error in SERP search",
                error=e,
                keyword=keyword,
                result_type=result_type
            )
            
            return {
                "success": False,
                "keyword": keyword,
                "result_type": result_type,
                "error": str(e),
                "error_category": "unknown_error"
            }
    
    def _extract_results(self, data: Dict, result_type: str) -> List[Dict]:
        """Extract and flatten results based on type"""
        flattened_results = []
        
        # Look for results with the appropriate key (e.g., "organic_results", "news_results", "video_results")
        results_key = f"{result_type}_results"
        results = data.get(results_key, [])
        
        # If results are already in the correct format (from CSV processing), return them
        if results and isinstance(results[0], dict) and 'position' in results[0]:
            return results
        
        # Otherwise, process legacy JSON format
        if result_type == "organic":
            results = data.get("organic_results", [])
            for idx, result in enumerate(results):
                flattened_results.append({
                    "position": result.get("position", idx + 1),
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "domain": result.get("domain", ""),
                    "snippet": result.get("snippet", ""),
                    "displayed_link": result.get("displayed_link", ""),
                    "type": "organic"
                })
        
        elif result_type == "news":
            results = data.get("news_results", [])
            for idx, result in enumerate(results):
                # Extract domain from URL if not provided
                url = result.get("link", "")
                domain = result.get("domain", "") or self._extract_domain(url)
                
                flattened_results.append({
                    "position": result.get("position", idx + 1),
                    "title": result.get("title", ""),
                    "link": url,
                    "domain": domain,
                    "source": result.get("source", ""),
                    "snippet": result.get("snippet", ""),
                    "date": result.get("date", ""),
                    "type": "news"
                })
        
        elif result_type in ["videos", "video"]:
            results = data.get("video_results", [])
            for idx, result in enumerate(results):
                # Extract domain from URL if not provided
                url = result.get("link", "")
                domain = result.get("domain", "") or self._extract_domain(url)
                
                flattened_results.append({
                    "position": result.get("position", idx + 1),
                    "title": result.get("title", ""),
                    "link": url,
                    "domain": domain,
                    "displayed_link": result.get("displayed_link", ""),
                    "thumbnail": result.get("thumbnail", ""),
                    "duration": result.get("duration", ""),
                    "length": result.get("length", result.get("duration", "")),  # Map length/duration
                    "platform": result.get("platform", ""),
                    "date": result.get("date", ""),
                    "snippet": result.get("snippet", ""),
                    "key_moments": result.get("key_moments", []),
                    "type": "video"
                })
        
        return flattened_results
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Clean domain - remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain.lower()
        except:
            return ""
    
    def _fallback_response(self, keyword: str, result_type: str, reason: str) -> Dict:
        """Fallback response when circuit is open"""
        self.logger.warning(
            f"Using fallback response",
            keyword=keyword,
            result_type=result_type,
            reason=reason
        )
        
        return {
            "success": False,
            "keyword": keyword,
            "result_type": result_type,
            "error": reason,
            "error_category": "circuit_breaker",
            "results": [],
            "total_results": 0
        }
    
    @log_performance("serp_collector", "create_and_run_batch")
    async def create_and_run_batch(
        self,
        keywords: List[str],
        keyword_ids: List[str],
        regions: List[str],
        content_types: List[str],
        batch_frequency: str = "immediate",
        scheduler_config: Optional[Dict] = None,
        include_html: bool = False,
        pipeline_execution_id: Optional[str] = None,
        state_tracker=None,
        progress_callback=None,
        news_time_period: Optional[str] = None,
        news_time_period_min: Optional[str] = None,
        news_time_period_max: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create and run a Scale SERP batch for multiple keywords with robustness features
        
        Args:
            keywords: List of keyword strings
            keyword_ids: List of database keyword IDs
            regions: List of region codes (e.g., ['US', 'UK'])
            content_types: List of content types (e.g., ['organic', 'news', 'video'])
            batch_frequency: Scheduling frequency for the batch ('immediate', 'daily', 'weekly', 'monthly')
            scheduler_config: Additional scheduling configuration
            include_html: Whether to include HTML in results
            pipeline_execution_id: ID of the pipeline execution
            state_tracker: State tracking instance for monitoring
            progress_callback: Async callback for progress updates
            news_time_period: Time period for news searches (last_hour, last_day, last_week, last_month, last_year, custom)
            news_time_period_min: Minimum date for custom news time period (when news_time_period='custom')
            news_time_period_max: Maximum date for custom news time period (when news_time_period='custom')
        
        Returns:
            Dict with batch results
        """
        start_time = datetime.utcnow()
        logger.info(f"🚀 SERP PROJECT BATCH: Creating batch for ALL {len(keywords)} project keywords across {len(regions)} regions")
        
        # Calculate total searches
        total_searches = len(keywords) * len(regions) * len(content_types)
        logger.info(f"📊 Total searches: {total_searches} | Batch limit: {self.batch_size_limit} | HTML: {include_html}")
        logger.info(f"💡 EFFICIENCY: Using single batch vs {total_searches} individual API calls (10-100x faster!)")
        
        # Initialize robustness services if not provided
        if not state_tracker and pipeline_execution_id:
            from app.core.database import db_pool
            from app.services.robustness import StateTracker
            state_tracker = StateTracker(db_pool)
        
        # Create checkpoint
        if state_tracker and pipeline_execution_id:
            await state_tracker.create_checkpoint(
                pipeline_execution_id,
                "serp_collection",
                "batch_init",
                {
                    'total_searches': total_searches,
                    'batch_size_limit': self.batch_size_limit,
                    'include_html': include_html,
                    'keywords': keywords,
                    'regions': regions,
                    'content_types': content_types,
                    'batch_strategy': 'content_type_separated'
                }
            )
        
        # Progress callback
        if progress_callback:
            await progress_callback("serp_batch_started", {
                'phase': 'serp_collection',
                'total_searches': total_searches,
                'status': 'initializing'
            })
        
        # Build batch requests
        batch_requests = []
        for i, keyword in enumerate(keywords):
            keyword_id = keyword_ids[i] if i < len(keyword_ids) else None
            for region in regions:
                for content_type in content_types:
                    batch_requests.append({
                        'keyword': keyword,
                        'keyword_id': keyword_id,
                        'region': region,
                        'content_type': content_type,
                        'location': self._get_location_name(region),
                        'gl': region.lower(),
                        'search_type': self._get_search_type(content_type)
                    })
        
        logger.info(f"📊 SERP BATCH: Created {len(batch_requests)} search requests")
        
        try:
            # Create Scale SERP batch
            # Extract content type from batch requests (should be same for all)
            content_type = content_types[0] if content_types else None
            
            batch_id = await self._create_scale_serp_batch(
                batch_requests, 
                include_html,
                news_time_period=news_time_period,
                news_time_period_min=news_time_period_min,
                news_time_period_max=news_time_period_max,
                content_type=content_type,
                schedule_config=scheduler_config
            )
            logger.info(f"✅ SERP BATCH: Created Scale SERP batch ID: {batch_id}")
            
            # Progress callback
            if progress_callback:
                await progress_callback("serp_batch_created", {
                    'batch_id': batch_id,
                    'searches_added': len(batch_requests),
                    'status': 'created'
                })
            
            # Start batch execution
            success = await self._start_batch(batch_id)
            if success:
                logger.info(f"🚀 SERP BATCH: Started batch execution for {batch_id}")
                
                if progress_callback:
                    await progress_callback("serp_batch_started", {
                        'batch_id': batch_id,
                        'status': 'running'
                    })
            else:
                logger.error(f"❌ Failed to start batch {batch_id}")
                if progress_callback:
                    await progress_callback("serp_batch_failed", {
                        'batch_id': batch_id,
                        'error': 'Failed to start'
                    })
                return {'success': False, 'error': 'Failed to start batch'}
            
            # Monitor batch completion
            results = await self._monitor_batch_completion(
                batch_id, 
                batch_requests,
                state_tracker,
                pipeline_execution_id,
                progress_callback
            )
            
            logger.info(f"✅ SERP BATCH: Completed with {results.get('stored_count', 0)} results stored")
            
            return {
                'success': results.get('stored_count', 0) > 0,
                'batch_id': batch_id,
                'results_stored': results.get('stored_count', 0),
                'results_failed': results.get('failed_count', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ SERP BATCH failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            if progress_callback:
                await progress_callback("serp_batch_failed", {
                    'error': str(e)
                })
            
            return {
                'success': False,
                'error': str(e)
            }

    async def create_batch_only(
        self,
        keywords: List[str],
        keyword_ids: List[str],
        regions: List[str],
        content_type: str,
        batch_frequency: str = "immediate",
        scheduler_config: Optional[Dict] = None,
        include_html: bool = False,
        progress_callback=None,
        news_time_period: Optional[str] = None,
        news_time_period_min: Optional[str] = None,
        news_time_period_max: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create and start a Scale SERP batch WITHOUT waiting for completion.
        Returns immediately with batch_id.
        """
        if not keywords:
            logger.warning("No keywords provided for SERP batch")
            return {'success': True, 'batch_id': None, 'content_type': content_type}
        
        # Log batch configuration
        logger.info(f"🚀 CREATING {content_type.upper()} BATCH: {len(keywords)} keywords × {len(regions)} regions")
        logger.info(f"📊 Total searches: {len(keywords) * len(regions)}")
        
        if content_type == 'news' and news_time_period:
            logger.info(f"📰 News time filtering: {news_time_period}")
        
        # Prepare batch requests
        batch_requests = []
        for i, keyword in enumerate(keywords):
            keyword_id = keyword_ids[i] if i < len(keyword_ids) else None
            for region in regions:
                request = {
                    'keyword': keyword,
                    'keyword_id': keyword_id,
                    'region': region,
                    'content_type': content_type,
                    'location': self._get_location_name(region),
                    'gl': region.lower(),
                    'search_type': self._get_search_type(content_type)
                }
                batch_requests.append(request)
        
        try:
            # Create Scale SERP batch
            batch_id = await self._create_scale_serp_batch(
                batch_requests, 
                include_html,
                news_time_period=news_time_period,
                news_time_period_min=news_time_period_min,
                news_time_period_max=news_time_period_max,
                content_type=content_type,
                schedule_config=scheduler_config
            )
            logger.info(f"✅ Created {content_type.upper()} batch: {batch_id}")
            
            # Progress callback
            if progress_callback:
                await progress_callback("serp_batch_created", {
                    'batch_id': batch_id,
                    'content_type': content_type,
                    'searches_added': len(batch_requests),
                    'status': 'created'
                })
            
            # Start batch execution
            success = await self._start_batch(batch_id)
            if success:
                logger.info(f"🚀 Started {content_type.upper()} batch: {batch_id}")
                
                if progress_callback:
                    await progress_callback("serp_batch_started", {
                        'batch_id': batch_id,
                        'content_type': content_type,
                        'status': 'running'
                    })
                
                return {
                    'success': True,
                    'batch_id': batch_id,
                    'content_type': content_type,
                    'batch_requests': batch_requests
                }
            else:
                logger.error(f"❌ Failed to start {content_type} batch {batch_id}")
                return {
                    'success': False,
                    'error': f'Failed to start {content_type} batch',
                    'batch_id': batch_id,
                    'content_type': content_type
                }
            
        except Exception as e:
            logger.error(f"❌ {content_type.upper()} batch creation error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'batch_id': None,
                'content_type': content_type
            }

    async def process_webhook_batch(
        self,
        batch_id: str,
        pipeline_id: str,
        content_type: str = "organic",
        result_set_id: Optional[int] = None,
        download_links: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process results from a completed ScaleSERP batch (webhook-triggered)"""
        try:
            logger.info(f"📥 Processing webhook batch {batch_id} for pipeline {pipeline_id}")
            
            # Get batch info
            batch_response = await self._scale_serp_request('GET', f'/batches/{batch_id}')
            if not batch_response or not batch_response.get('request_info', {}).get('success'):
                raise Exception(f"Failed to get batch info: {batch_response}")
            
            batch_info = batch_response.get('batch', {})
            total_searches = batch_info.get('searches_total_count', 0)
            results_count = batch_info.get('results_count', 0)
            
            logger.info(f"📊 Batch {batch_id}: {results_count}/{total_searches} results available")
            
            # Check if all results are ready
            if results_count < total_searches:
                logger.warning(f"⚠️ Not all results are ready yet ({results_count}/{total_searches}). The webhook may have fired too early.")
                # For now, proceed anyway as we might get partial results
            
            # Use provided result_set_id or get from batch info
            if result_set_id:
                # Use the result set ID from webhook
                result_sets = [{'id': result_set_id}]
            else:
                # Try to get result sets from batch info
                result_sets = batch_info.get('result_sets', [])
                if not result_sets:
                    # Default to first result set
                    result_sets = [{'id': 1}]
            
            total_stored = 0
            unique_domains = set()
            video_urls = []
            keywords_processed = set()
            
            for result_set in result_sets:
                result_set_id = result_set.get('id')
                logger.info(f"📥 Fetching result set {result_set_id}")
                
                # Try to use download link if provided
                csv_url = None
                json_url = None
                if download_links:
                    # Try CSV first
                    csv_links = download_links.get('csv', {})
                    if csv_links and 'pages' in csv_links:
                        pages = csv_links['pages']
                        if pages and len(pages) > 0:
                            csv_url = pages[0]
                            logger.info(f"📥 Found CSV download URL: {csv_url}")
                    
                    # If no CSV, try JSON
                    if not csv_url:
                        json_links = download_links.get('json', {})
                        if json_links and 'pages' in json_links:
                            pages = json_links['pages']
                            if pages and len(pages) > 0:
                                json_url = pages[0]
                                logger.info(f"📥 Found JSON download URL (no CSV available): {json_url}")
                
                if csv_url:
                    logger.info(f"📥 Using CSV download link: {csv_url}")
                    # Download directly from the provided URL
                    results_response = await self.client.get(csv_url)
                    results_response.raise_for_status()
                    # The response will be the raw CSV text
                    logger.info(f"📊 CSV content length: {len(results_response.text)} characters")
                elif json_url:
                    logger.info(f"📥 Using JSON download link (CSV not available for video searches): {json_url}")
                    # Download JSON and convert to our format
                    json_response = await self.client.get(json_url)
                    json_response.raise_for_status()
                    # Process JSON response
                    import json
                    json_data = json_response.json()
                    
                    # Skip CSV processing for JSON data
                    results_response = None
                    
                    # Process JSON data directly
                    if 'searches' in json_data:
                        for search in json_data['searches']:
                            keyword = search.get('search_metadata', {}).get('q', '').replace(' site:youtube.com', '')
                            if keyword:
                                keywords_processed.add(keyword)
                            
                            # Process video results
                            for video in search.get('video_results', []):
                                video_url = video.get('link', '')
                                if video_url:
                                    video_urls.append(video_url)
                                    stored += 1
                                    
                                    # Extract channel domain if possible
                                    channel_link = video.get('channel', {}).get('link', '')
                                    if channel_link:
                                        from urllib.parse import urlparse
                                        domain = urlparse(channel_link).netloc
                                        if domain:
                                            unique_domains.add(domain)
                else:
                    # Fallback to API endpoint
                    logger.info(f"📥 No download link, using API endpoint")
                    results_response = await self._scale_serp_request(
                        'GET',
                        f'/batches/{batch_id}/result_sets/{result_set_id}/results',
                        params={'format': 'csv'}
                    )
                
                if results_response:
                    # Process CSV results directly
                    # The CSV contains the raw SERP data that we need to parse and store
                    csv_content = results_response.text
                    stored = 0
                    failed = 0
                    domains = set()
                    videos = []
                    
                    # Parse CSV and store results
                    import csv
                    from io import StringIO
                    csv_reader = csv.DictReader(StringIO(csv_content))
                    
                    logger.info(f"📝 Processing CSV for batch {batch_id}, content_type: {content_type}")
                    
                    # Get database connection
                    from app.core.database import db_pool
                    async with db_pool.acquire() as conn:
                        row_count = 0

                        def _safe_int(value: Any) -> Optional[int]:
                            try:
                                if value is None:
                                    return None
                                if isinstance(value, int):
                                    return value
                                s = str(value).strip()
                                if s == "":
                                    return None
                                return int(float(s))
                            except Exception:
                                return None

                        def _parse_relative_date(text: str) -> Optional[datetime]:
                            if not text or not isinstance(text, str):
                                return None
                            # Patterns like '2 days ago', '11 hours ago', '1 day ago'
                            m = re.match(r"^(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago$", text.strip(), re.IGNORECASE)
                            if not m:
                                return None
                            qty = int(m.group(1))
                            unit = m.group(2).lower()
                            now = datetime.now(timezone.utc)
                            if unit.startswith('minute'):
                                return now - timedelta(minutes=qty)
                            if unit.startswith('hour'):
                                return now - timedelta(hours=qty)
                            if unit.startswith('day'):
                                return now - timedelta(days=qty)
                            if unit.startswith('week'):
                                return now - timedelta(weeks=qty)
                            if unit.startswith('month'):
                                return now - timedelta(days=qty * 30)
                            if unit.startswith('year'):
                                return now - timedelta(days=qty * 365)
                            return None
                        for row in csv_reader:
                            row_count += 1
                            try:
                                # Extract keyword from search query
                                keyword = row.get('search.q', row.get('search_query', ''))
                                if not keyword and row_count == 1:
                                    logger.warning(f"🔍 CSV headers: {list(row.keys())}")
                                if not keyword:
                                    logger.warning(f"🔍 Row {row_count}: No keyword found, skipping")
                                    continue
                                    
                                keywords_processed.add(keyword)
                                
                                # Get keyword ID
                                keyword_data = await conn.fetchrow(
                                    "SELECT id FROM keywords WHERE keyword = $1",
                                    keyword
                                )
                                if not keyword_data:
                                    logger.warning(f"🔍 Keyword '{keyword}' not found in database, skipping row {row_count}")
                                    failed += 1
                                    continue
                                
                                keyword_id = keyword_data['id']
                                
                                # Extract URL based on content type
                                if content_type == 'organic':
                                    url = row.get('result.organic_results.link', row.get('link', ''))
                                elif content_type == 'news':
                                    url = row.get('result.news_results.link', row.get('link', ''))
                                elif content_type == 'video':
                                    url = row.get('result.video_results.link', row.get('link', ''))
                                else:
                                    url = row.get('link', '')
                                
                                if url:
                                    from urllib.parse import urlparse
                                    domain = urlparse(url).netloc
                                    if domain:
                                        unique_domains.add(domain)
                                    
                                    # Check for video URLs
                                    if 'youtube.com' in url or 'youtu.be' in url:
                                        video_urls.append(url)
                                
                                # Prepare typed fields with normalization
                                # Position
                                raw_position = row.get(f'result.{content_type}_results.position', row.get('position', None))
                                position_val = _safe_int(raw_position)

                                # Published date: handle absolute or relative strings (always make UTC-aware)
                                raw_published = row.get(f'result.{content_type}_results.date', row.get('date', None))
                                published_dt: Optional[datetime] = None
                                if raw_published:
                                    # Try relative first
                                    published_dt = _parse_relative_date(str(raw_published))
                                    if not published_dt:
                                        try:
                                            from dateutil import parser as dtparser
                                            parsed = dtparser.parse(str(raw_published))
                                            if parsed.tzinfo is None:
                                                published_dt = parsed.replace(tzinfo=timezone.utc)
                                            else:
                                                published_dt = parsed.astimezone(timezone.utc)
                                        except Exception:
                                            published_dt = None

                                # total_results numeric
                                total_results_val = _safe_int(row.get('total_results', None))

                                # Store SERP result in database
                                await conn.execute(
                                    """
                                    INSERT INTO serp_results (
                                        keyword_id, search_date, location, serp_type,
                                        position, url, title, snippet, domain,
                                        source, published_date, video_length, total_results,
                                        device, google_domain, language_code, time_period,
                                        news_type, query_displayed, time_taken_displayed,
                                        pipeline_execution_id
                                    ) VALUES ($1, $2::date, $3, $4, $5, $6, $7, $8, $9, $10, $11::date, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                                    ON CONFLICT (keyword_id, location, serp_type, url, search_date) DO NOTHING
                                    """,
                                    keyword_id,  # keyword_id
                                    date.today(),  # search_date as DATE
                                    row.get('gl', row.get('location', 'US')),  # location
                                    content_type,  # serp_type
                                    position_val,  # position
                                    url,  # url
                                    row.get(f'result.{content_type}_results.title', row.get('title', '')),  # title
                                    row.get(f'result.{content_type}_results.snippet', row.get('snippet', '')),  # snippet
                                    domain,  # domain
                                    row.get(f'result.{content_type}_results.source', row.get('source', '')),  # source
                                    (published_dt.date() if isinstance(published_dt, datetime) else published_dt),  # published_date as DATE
                                    row.get('video_length', None),  # video_length
                                    total_results_val,  # total_results
                                    row.get('device', 'desktop'),  # device
                                    row.get('google_domain', 'google.com'),  # google_domain
                                    row.get('hl', 'en'),  # language_code
                                    row.get('time_period', None),  # time_period
                                    row.get('type', None),  # news_type
                                    row.get('query_displayed', keyword),  # query_displayed
                                    row.get('time_taken_displayed', None),  # time_taken_displayed
                                    pipeline_id  # pipeline_execution_id
                                )
                                stored += 1
                                
                            except Exception as e:
                                logger.warning(f"Failed to process/store row: {e}")
                                failed += 1
                    
                    logger.info(f"✅ CSV processing complete: {row_count} rows, {stored} stored, {failed} failed")
                    total_stored += stored
                    unique_domains.update(domains)
                    video_urls.extend(videos)
                    
                    # Extract keywords from results
                    import csv
                    from io import StringIO
                    csv_reader = csv.DictReader(StringIO(results_response.text))
                    for row in csv_reader:
                        if 'search_query' in row:
                            keywords_processed.add(row['search_query'])
            
            return {
                'success': True,
                'batch_id': batch_id,
                'content_type': content_type,
                'total_results': total_stored,
                'results_stored': total_stored,
                'results_failed': 0,
                'keywords_processed': len(keywords_processed),
                'unique_domains': list(unique_domains),
                'video_urls': video_urls
            }
            
        except Exception as e:
            logger.error(f"Failed to process webhook batch {batch_id}: {str(e)}")
            return {
                'success': False,
                'batch_id': batch_id,
                'error': str(e),
                'total_results': 0,
                'results_stored': 0,
                'keywords_processed': 0,
                'unique_domains': [],
                'video_urls': []
            }
    
    async def monitor_batch(
        self,
        batch_id: str,
        batch_requests: List[Dict],
        content_type: str,
        pipeline_execution_id: Optional[str] = None,
        state_tracker=None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Monitor an existing batch until completion.
        Separate from batch creation to allow concurrent processing.
        """
        logger.info(f"👀 Monitoring {content_type.upper()} batch: {batch_id}")
        
        try:
            results = await self._monitor_batch_completion(
                batch_id, 
                batch_requests,
                state_tracker,
                pipeline_execution_id,
                progress_callback
            )
            
            logger.info(f"✅ {content_type.upper()} batch {batch_id} completed: {results.get('stored_count', 0)} results")
            return {
                'success': results.get('stored_count', 0) > 0,
                'batch_id': batch_id,
                'content_type': content_type,
                'results_stored': results.get('stored_count', 0),
                'results_failed': results.get('failed_count', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Error monitoring {content_type} batch {batch_id}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'batch_id': batch_id,
                'content_type': content_type,
                'results_stored': 0
            }
    
    async def _create_scale_serp_batch(
        self, 
        batch_requests: List[Dict],
        include_html: bool = False,
        news_time_period: Optional[str] = None,
        news_time_period_min: Optional[str] = None,
        news_time_period_max: Optional[str] = None,
        content_type: Optional[str] = None,
        schedule_config: Optional[Dict] = None
    ) -> str:
        """Create a Scale SERP batch with all search requests"""
        if not self.client:
            self.client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"🚀 Creating Scale SERP batch for content type: {content_type} (Step 1/3)")
        
        # Determine scheduling parameters from config
        schedule_type = "manual"  # Default
        schedule_params = {}
        
        if schedule_config and schedule_config.get('frequency') != 'immediate':
            frequency = schedule_config.get('frequency', 'manual')
            
            # Map our frequency to ScaleSERP schedule types
            if frequency == 'daily':
                schedule_type = 'daily'
                # Add schedule hours if provided
                if 'time_of_day' in schedule_config:
                    hour = schedule_config['time_of_day'].hour if hasattr(schedule_config['time_of_day'], 'hour') else 9
                    schedule_params['schedule_hours'] = [hour]
                else:
                    schedule_params['schedule_hours'] = [9]  # Default to 9 AM
                    
            elif frequency == 'weekly':
                schedule_type = 'weekly'
                # Add schedule days of week if provided
                if 'days_of_week' in schedule_config and schedule_config['days_of_week']:
                    schedule_params['schedule_days_of_week'] = schedule_config['days_of_week']
                else:
                    schedule_params['schedule_days_of_week'] = [1]  # Default to Monday
                
                # Add hours
                if 'time_of_day' in schedule_config:
                    hour = schedule_config['time_of_day'].hour if hasattr(schedule_config['time_of_day'], 'hour') else 9
                    schedule_params['schedule_hours'] = [hour]
                else:
                    schedule_params['schedule_hours'] = [9]
                    
            elif frequency == 'monthly':
                schedule_type = 'monthly'
                # Add schedule days of month if provided
                if 'day_of_month' in schedule_config and schedule_config['day_of_month']:
                    schedule_params['schedule_days_of_month'] = [schedule_config['day_of_month']]
                else:
                    schedule_params['schedule_days_of_month'] = [1]  # Default to 1st of month
                
                # Add hours
                if 'time_of_day' in schedule_config:
                    hour = schedule_config['time_of_day'].hour if hasattr(schedule_config['time_of_day'], 'hour') else 9
                    schedule_params['schedule_hours'] = [hour]
                else:
                    schedule_params['schedule_hours'] = [9]
        
        logger.info(f"📅 Using schedule_type: {schedule_type} with params: {schedule_params}")
        
        try:
            # Step 1: Create empty batch
            batch_name = f"Cylvy {content_type.upper() if content_type else 'Pipeline'} Batch {datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            batch_config = {
                "name": batch_name,
                "enabled": True,
                "schedule_type": schedule_type,
                "priority": "normal",
                "notification_email": os.getenv("SCALESERP_NOTIFICATION_EMAIL"),
                # Configure webhook for batch completion notifications
                "notification_webhook": os.getenv("SCALESERP_WEBHOOK_URL"),
                "notification_as_json": True,
                "notification_as_csv": True,
                # Add ngrok header if using ngrok URL
                "notification_webhook_headers": {
                    "ngrok-skip-browser-warning": "true"
                } if os.getenv("SCALESERP_WEBHOOK_URL", "").startswith("https://") and ".ngrok" in os.getenv("SCALESERP_WEBHOOK_URL", "") else None
            }
            
            # Merge in schedule parameters
            batch_config.update(schedule_params)
            
            create_response = await self.client.post(
                self.batch_base_url,
                params={"api_key": self.api_key},
                json=batch_config
            )
            create_response.raise_for_status()
            
            batch_data = create_response.json()
            logger.info(f"🔍 Batch creation response: {batch_data}")
            
            # Handle different response formats - Scale SERP nests the batch data
            if 'batch' in batch_data and isinstance(batch_data['batch'], dict) and 'id' in batch_data['batch']:
                batch_id = batch_data['batch']['id']
            elif 'id' in batch_data:
                batch_id = batch_data['id']
            elif 'batch_id' in batch_data:
                batch_id = batch_data['batch_id']
            elif 'data' in batch_data and isinstance(batch_data['data'], dict) and 'id' in batch_data['data']:
                batch_id = batch_data['data']['id']
            else:
                logger.error(f"❌ Unexpected batch response format: {batch_data}")
                logger.error(f"❌ Response status: {create_response.status_code}")
                logger.error(f"❌ Response headers: {dict(create_response.headers)}")
                raise ValueError(f"No batch ID found in response. Keys: {list(batch_data.keys())}")
                
            logger.info(f"✅ Scale SERP batch created: {batch_id}")
            
            # Step 2: Add searches to batch
            logger.info(f"📝 Adding {len(batch_requests)} searches to batch (Step 2/3)")
            
            searches = []
            for req in batch_requests:
                search_params = {
                    "q": req['keyword'],
                    "location": req['location'],
                    "gl": req['gl'],
                    "hl": "en",
                    "device": "desktop",
                    "num": 50,
                    "output": "json",
                    "custom_id": f"{req['keyword']}_{req['region']}_{req['content_type']}"
                }
                
                # Add search type and time period for news
                if req['content_type'] == 'news':
                    search_params["search_type"] = "news"
                    # Add time period for news searches based on schedule or default
                    if news_time_period:
                        search_params["time_period"] = news_time_period
                    else:
                        # Fallback to request-specific or default
                        time_period = req.get('time_period', 'last_day')
                        search_params["time_period"] = time_period
                    
                    # If custom time period, add min/max parameters
                    if search_params.get("time_period") == 'custom':
                        if news_time_period_min:
                            search_params["time_period_min"] = news_time_period_min
                        if news_time_period_max:
                            search_params["time_period_max"] = news_time_period_max
                        elif req.get('time_period_min') or req.get('time_period_max'):
                            if req.get('time_period_min'):
                                search_params["time_period_min"] = req['time_period_min']
                            if req.get('time_period_max'):
                                search_params["time_period_max"] = req['time_period_max']
                            
                elif req['content_type'] == 'video':
                    search_params["search_type"] = "videos"
                    # Append site:youtube.com for video searches
                    search_params["q"] = f"{req['keyword']} site:youtube.com"
                
                if include_html:
                    search_params["include_html"] = True
                    
                searches.append(search_params)
            
            # Update batch with searches - Scale SERP has a limit of 1000 searches per request
            SCALE_SERP_CHUNK_SIZE = 1000
            total_searches_added = 0
            
            # Chunk searches if necessary
            if len(searches) > SCALE_SERP_CHUNK_SIZE:
                logger.info(f"🔧 Chunking {len(searches)} searches into batches of {SCALE_SERP_CHUNK_SIZE}")
                
                for i in range(0, len(searches), SCALE_SERP_CHUNK_SIZE):
                    chunk = searches[i:i + SCALE_SERP_CHUNK_SIZE]
                    logger.info(f"🔧 Adding chunk {i//SCALE_SERP_CHUNK_SIZE + 1}: {len(chunk)} searches")
                    
                    update_response = await self.client.put(
                        f"{self.batch_base_url}/{batch_id}",
                        params={"api_key": self.api_key},
                        json={"searches": chunk}
                    )
                    
                    if update_response.status_code != 200:
                        error_content = update_response.text
                        logger.error(f"🔧 Batch update error response: {error_content}")
                        update_response.raise_for_status()
                    
                    total_searches_added += len(chunk)
                    logger.info(f"✅ Added chunk successfully. Total so far: {total_searches_added}")
                
                logger.info(f"✅ Successfully added all {total_searches_added} searches to batch {batch_id}")
            else:
                # Single request for small batches
                logger.info(f"🔧 CORRECT API: PUT /batches/{batch_id} with {len(searches)} searches")
                update_response = await self.client.put(
                    f"{self.batch_base_url}/{batch_id}",
                    params={"api_key": self.api_key},
                    json={"searches": searches}
                )
                logger.info(f"🔧 Batch update response: {update_response.status_code}")
                if update_response.status_code != 200:
                    error_content = update_response.text
                    logger.error(f"🔧 Batch update error response: {error_content}")
                update_response.raise_for_status()
                
                logger.info(f"✅ Successfully added {len(searches)} searches to batch {batch_id}")
                update_data = update_response.json()
                logger.info(f"🔧 PUT Response debug: {update_data}")
                
                # Verify searches were added
                if 'batch' in update_data:
                    actual_count = update_data['batch'].get('searches_total_count', 0)
                    logger.info(f"✅ Batch update complete: {actual_count} searches in batch {batch_id}")
            
            return batch_id
            
        except Exception as e:
            logger.error(f"❌ Error creating Scale SERP batch: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    async def _start_batch(self, batch_id: str) -> bool:
        """Start batch execution for manual batches"""
        try:
            if not self.client:
                self.client = httpx.AsyncClient(timeout=30.0)
            
            # Scale SERP requires GET request to start manual batches
            response = await self.client.get(
                f"{self.batch_base_url}/{batch_id}/start",
                params={"api_key": self.api_key}
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"✅ Started batch execution: {batch_id}")
            logger.info(f"✅ Start response: {result}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting batch: {e}")
            return False
    
    @log_performance("serp_collector", "monitor_batch_completion")
    async def _monitor_batch_completion(
        self,
        batch_id: str,
        batch_requests: List[Dict],
        state_tracker=None,
        pipeline_execution_id: str = None,
        progress_callback=None
    ) -> Dict:
        """Monitor batch until completion with robustness features"""
        if not self.client:
            self.client = httpx.AsyncClient(timeout=30.0)
        
        if self.use_webhooks:
            logger.info(f"📊 Monitoring batch {batch_id} with webhooks enabled (fallback polling every {self.monitor_interval}s, timeout: {self.batch_timeout//60}m)")
        else:
            logger.info(f"📊 Monitoring batch {batch_id} completion (polling every {self.monitor_interval}s, timeout: {self.batch_timeout//60}m)")
        start_time = datetime.utcnow()
        
        # Create monitoring checkpoint
        if state_tracker and pipeline_execution_id:
            await state_tracker.create_checkpoint(
                pipeline_execution_id,
                "serp_collection",
                "monitoring_start",
                {
                    'batch_id': batch_id,
                    'total_requests': len(batch_requests),
                    'monitoring_started_at': datetime.utcnow().isoformat()
                }
            )
        
        error_count = 0
        while (datetime.utcnow() - start_time).total_seconds() < self.batch_timeout:
            try:
                # Use List Result Sets endpoint
                response = await self.client.get(
                    f"{self.batch_base_url}/{batch_id}/results",
                    params={"api_key": self.api_key}
                )
                response.raise_for_status()
                
                result_data = response.json()
                results_count = result_data.get('results_count', 0)
                batch_info = result_data.get('batch', {})
                status = batch_info.get('status', 'unknown')
                
                logger.info(f"📊 Result Sets Check: {batch_id} | Result sets available: {results_count} | Batch status: {status}")
                logger.info(f"📊 Progress: {batch_info.get('searches_completed', 0)}/{batch_info.get('searches_total_count', 0)} searches completed")
                
                # Progress callback
                minute = int((datetime.utcnow() - start_time).total_seconds() / 60) + 1
                if progress_callback:
                    await progress_callback("serp_batch_progress", {
                        'batch_id': batch_id,
                        'status': status,
                        'results_count': results_count,
                        'search_total': batch_info.get('searches_total_count', 0),
                        'result_sets_available': results_count,
                        'completion_percentage': (batch_info.get('searches_completed', 0) / max(batch_info.get('searches_total_count', 1), 1)) * 100,
                        'minute': minute
                    })
                
                # Check if results are available
                if results_count > 0 and status == 'idle':
                    logger.info(f"✅ Batch {batch_id} has {results_count} result set(s) available!")
                    
                    # Get latest result set
                    results_list = result_data.get('results', [])
                    if results_list:
                        latest_result = results_list[0]  # Most recent first
                        result_set_id = latest_result.get('id')
                        started_at = latest_result.get('started_at')
                        ended_at = latest_result.get('ended_at')
                        searches_completed = latest_result.get('searches_completed', 0)
                        searches_failed = latest_result.get('searches_failed', 0)
                        
                        logger.info(f"📊 Latest result set: {result_set_id}")
                        logger.info(f"📅 Result timing: Started: {started_at} | Ended: {ended_at}")
                        logger.info(f"📊 Results: Completed: {searches_completed} | Failed: {searches_failed}")
                        
                        if progress_callback:
                            await progress_callback("serp_batch_completed", {
                                'batch_id': batch_id,
                                'result_set_id': result_set_id,
                                'searches_completed': searches_completed,
                                'searches_failed': searches_failed
                            })
                        
                        # Get result set details in CSV format
                        logger.info(f"🔍 Getting result set {result_set_id} for batch {batch_id} in CSV format...")
                        
                        # Determine content type from batch_requests
                        content_type = 'organic'  # default
                        if batch_requests:
                            content_type = batch_requests[0].get('content_type', 'organic')
                        
                        # Define CSV fields based on content type
                        csv_fields_map = {
                            'organic': 'search_parameters.q,search_parameters.device,search_parameters.location,search_parameters.google_domain,search_parameters.gl,search_parameters.hl,search_information.total_results,search_information.query_displayed,organic_results.position,organic_results.title,organic_results.link,organic_results.domain,organic_results.snippet,organic_results.date',
                            'news': 'search_parameters.q,search_parameters.device,search_parameters.location,search_parameters.google_domain,search_parameters.gl,search_parameters.hl,search_parameters.time_period,search_parameters.news_type,search_information.total_results,search_information.time_taken_displayed,search_information.query_displayed,news_results.position,news_results.title,news_results.link,news_results.domain,news_results.source,news_results.date,news_results.date_utc,news_results.snippet',
                            'video': 'search_parameters.q,search_parameters.device,search_parameters.location,search_parameters.google_domain,search_parameters.gl,search_parameters.hl,search_information.total_results,search_information.query_displayed,video_results.position,video_results.title,video_results.link,video_results.domain,video_results.snippet,video_results.date,video_results.length'
                        }
                        
                        csv_fields = csv_fields_map.get(content_type, csv_fields_map['organic'])
                        
                        # Try JSON endpoint instead of CSV for now due to 400 errors
                        result_response = await self.client.get(
                            f"{self.batch_base_url}/{batch_id}/results/{result_set_id}",
                            params={
                                "api_key": self.api_key
                            }
                        )
                        result_response.raise_for_status()
                        
                        result_set_data = result_response.json()
                        download_links = result_set_data.get('result', {}).get('download_links', {})
                        pages = download_links.get('pages', [])
                        
                        logger.info(f"📥 Found {len(pages)} result pages to download")
                        
                        # Download and process results
                        all_results = {}
                        for page_url in pages:
                            logger.info(f"📥 Downloading results from: {page_url}")
                            
                            # Download the actual SERP results CSV file
                            download_response = await self.client.get(page_url)
                            
                            if download_response.status_code == 200:
                                try:
                                    # Parse JSON data
                                    page_results = download_response.json()
                                    
                                    # Log the results
                                    logger.info(f"📥 Downloaded {len(page_results)} search results")
                                    
                                    # Log the structure of the first result for debugging
                                    if page_results:
                                        logger.info(f"📥 First result structure: {list(page_results[0].keys())}")
                                        if 'search_parameters' in page_results[0]:
                                            logger.info(f"📥 Search parameters: {page_results[0]['search_parameters']}")
                                    
                                    # Process JSON results
                                    for result_data in page_results:
                                        # Extract the actual result from the Scale SERP response structure
                                        if 'result' in result_data and result_data['result']:
                                            actual_result = result_data['result']
                                            
                                            # Get search parameters from the actual result
                                            search_params = actual_result.get('search_parameters', {})
                                            
                                            # Create a search key from query and location
                                            query = search_params.get('q', '')
                                            # For video searches, remove site:youtube.com from the query for key matching
                                            if content_type == 'video' and ' site:youtube.com' in query:
                                                query = query.replace(' site:youtube.com', '')
                                            location = search_params.get('gl', search_params.get('location', ''))
                                            search_key = f"{query}_{location}_{content_type}"
                                            
                                            if query:  # Only process if we have a query
                                                all_results[search_key] = actual_result
                                                logger.info(f"📥 Added result for key: {search_key}")
                                    
                                    logger.info(f"✅ Processed {len(page_results)} search results into {len(all_results)} keyed results")
                                except Exception as parse_error:
                                    logger.error(f"❌ Error parsing downloaded results: {parse_error}")
                                    import traceback
                                    logger.error(f"Traceback: {traceback.format_exc()}")
                            else:
                                logger.error(f"❌ Failed to download results page: {download_response.status_code}")
                        
                        # Process the downloaded results
                        logger.info(f"💾 Processing {len(all_results)} total results from batch")
                        
                        # Convert to expected format for _process_batch_results
                        batch_results = {
                            'results': all_results,
                            'ended_at': ended_at,
                            'started_at': started_at
                        }
                        
                        # Process and store results
                        results = await self._process_batch_results(
                            batch_results,
                            batch_requests,
                            state_tracker,
                            pipeline_execution_id,
                            progress_callback
                        )
                        
                        return results
                    else:
                        logger.error(f"❌ No result sets found in response")
                        return {'stored_count': 0, 'failed_count': 0}
                
                elif status == 'failed':
                    logger.error(f"❌ Batch {batch_id} failed")
                    return {'stored_count': 0, 'failed_count': len(batch_requests)}
                elif status in ['pending', 'running', 'queued']:
                    # Wait before checking again
                    if status == 'queued':
                        logger.info(f"📊 Batch {batch_id} is queued - waiting for execution...")
                    elif status == 'running':
                        logger.info(f"📊 Batch {batch_id} is running - no result sets available yet...")
                    await asyncio.sleep(self.monitor_interval)
                else:
                    logger.warning(f"⚠️ Batch {batch_id} status: {status} - no result sets yet, waiting...")
                    await asyncio.sleep(self.monitor_interval)
                    
            except Exception as e:
                logger.error(f"❌ Error monitoring batch {batch_id}: {e}")
                # Track errors and give up after too many
                error_count += 1
                
                if error_count >= 3:
                    logger.error(f"❌ Batch {batch_id} failed after {error_count} attempts - giving up")
                    return {'stored_count': 0, 'failed_count': len(batch_requests), 'error': str(e)}
                
                logger.info(f"⏳ Retrying batch {batch_id} monitoring (attempt {error_count}/3)...")
                await asyncio.sleep(self.monitor_interval)
        
        # Timeout reached
        logger.error(f"❌ Batch {batch_id} monitoring timeout after {self.batch_timeout//60} minutes")
        return {'stored_count': 0, 'failed_count': len(batch_requests)}
    
    async def _process_batch_results(
        self,
        batch_results: Dict,
        batch_requests: List[Dict],
        state_tracker=None,
        pipeline_execution_id: str = None,
        progress_callback=None
    ) -> Dict:
        """Process and store batch results with robustness features"""
        logger.info(f"💾 Processing batch results for storage")
        
        # Extract batch timing for scheduling
        batch_ended_at = batch_results.get('ended_at')
        logger.info(f"📅 Using batch collection date: {batch_ended_at}")
        
        if progress_callback:
            await progress_callback("serp_results_processing", {
                'phase': 'result_processing',
                'total_results': len(batch_results.get('results', {})),
                'status': 'processing'
            })
        
        stored_count = 0
        failed_count = 0
        
        async def process_with_retry(search_key: str, result_data: Dict, request: Dict):
            """Process a single result with retry logic"""
            try:
                serp_results = self._extract_results(
                    result_data,
                    request['content_type']
                )
                
                # Store results in database
                if self.db:
                    async with self.db.acquire() as conn:
                        for idx, serp_result in enumerate(serp_results):
                            try:
                                # Ensure all values are not None
                                keyword_id = request['keyword_id']
                                location = request['region']
                                serp_type = request['content_type']
                                position = serp_result.get('position', idx + 1)
                                url = serp_result.get('link', '') or ''
                                title = (serp_result.get('title', '') or '')[:500]
                                snippet = serp_result.get('snippet', '') or ''
                                domain = serp_result.get('domain', '') or ''
                                
                                # Validate required fields
                                if not keyword_id or not url:
                                    logger.warning(f"⚠️ Skipping result with missing keyword_id or url")
                                    continue
                                
                                # Use batch ended_at date if available
                                if batch_ended_at:
                                    # Ensure UTC-aware then convert to date
                                    dt = datetime.fromisoformat(batch_ended_at.replace('Z', '+00:00'))
                                    if dt.tzinfo is None:
                                        dt = dt.replace(tzinfo=timezone.utc)
                                    else:
                                        dt = dt.astimezone(timezone.utc)
                                    search_date = dt.date()
                                else:
                                    search_date = date.today()
                                
                                # Parse published date if available
                                published_date = None
                                if serp_result.get('date'):
                                    try:
                                        from dateutil import parser
                                        parsed = parser.parse(serp_result['date'])
                                        if parsed.tzinfo is None:
                                            published_date = parsed.replace(tzinfo=timezone.utc)
                                        else:
                                            published_date = parsed.astimezone(timezone.utc)
                                    except:
                                        pass
                                
                                # Get additional fields based on content type
                                source = serp_result.get('source', '') if serp_type == 'news' else None
                                video_length = serp_result.get('length', '') if serp_type == 'video' else None
                                
                                # Get search metadata from parent result data
                                search_params = result_data.get('search_parameters', {})
                                search_info = result_data.get('search_information', {})
                                
                                # Extract search parameters
                                device = search_params.get('device')
                                google_domain = search_params.get('google_domain')
                                language_code = search_params.get('hl')
                                time_period = search_params.get('time_period')
                                news_type = search_params.get('news_type') if serp_type == 'news' else None
                                
                                # Extract search information
                                total_results = None
                                if search_info.get('total_results'):
                                    try:
                                        total_results = int(search_info.get('total_results', 0))
                                    except:
                                        pass
                                query_displayed = search_info.get('query_displayed')
                                time_taken_displayed = search_info.get('time_taken_displayed')
                                
                                await conn.execute(
                                    """
                                    INSERT INTO serp_results (
                                        keyword_id, search_date, location, serp_type,
                                        position, url, title, snippet, domain,
                                        source, published_date, video_length, total_results,
                                        device, google_domain, language_code, time_period, 
                                        news_type, query_displayed, time_taken_displayed,
                                        pipeline_execution_id
                                    ) VALUES ($1, $2::date, $3, $4, $5, $6, $7, $8, $9, $10, $11::date, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                                    ON CONFLICT (keyword_id, search_date, location, serp_type, url) 
                                    DO UPDATE SET
                                        position = EXCLUDED.position,
                                        title = EXCLUDED.title,
                                        snippet = EXCLUDED.snippet,
                                        source = EXCLUDED.source,
                                        published_date = EXCLUDED.published_date,
                                        video_length = EXCLUDED.video_length,
                                        total_results = EXCLUDED.total_results,
                                        device = EXCLUDED.device,
                                        google_domain = EXCLUDED.google_domain,
                                        language_code = EXCLUDED.language_code,
                                        time_period = EXCLUDED.time_period,
                                        news_type = EXCLUDED.news_type,
                                        query_displayed = EXCLUDED.query_displayed,
                                        time_taken_displayed = EXCLUDED.time_taken_displayed,
                                        pipeline_execution_id = EXCLUDED.pipeline_execution_id
                                    """,
                                    keyword_id,
                                    search_date,
                                    location,
                                    serp_type,
                                    position,
                                    url,
                                    title,
                                    snippet,
                                    domain,
                                    source,
                                    published_date,
                                    video_length,
                                    total_results,
                                    device,
                                    google_domain,
                                    language_code,
                                    time_period,
                                    news_type,
                                    query_displayed,
                                    time_taken_displayed,
                                    pipeline_execution_id
                                )
                                
                            except Exception as store_error:
                                logger.error(f"❌ Failed to store SERP result: {store_error}")
                    
                    logger.info(f"💾 Stored {len(serp_results)} SERP results for {request['keyword']} ({request['region']}, {request['content_type']})")
                    return len(serp_results)
                
            except Exception as e:
                logger.error(f"❌ Error processing result {search_id}: {e}")
                raise
        
        # Process results with retry logic
        for search_id, result_data in batch_results.get('results', {}).items():
            try:
                # Find corresponding request by matching search key
                request = None
                for req in batch_requests:
                    # Match the key format used when processing JSON results
                    expected_key = f"{req['keyword']}_{req['gl']}_{req['content_type']}"
                    if search_id == expected_key:
                        request = req
                        break
                
                if not request:
                    logger.warning(f"⚠️ Could not find request for result: {search_id}")
                    failed_count += 1
                    continue
                
                # Process with retry if retry manager available
                if self.retry_manager:
                    # retry_with_backoff expects a callable, so we wrap the async function
                    async def retry_wrapper():
                        return await process_with_retry(search_id, result_data, request)
                    
                    count = await self.retry_manager.retry_with_backoff(
                        retry_wrapper,
                        entity_type='serp_result_processing',
                        entity_id=search_id
                    )
                else:
                    count = await process_with_retry(search_id, result_data, request)
                
                stored_count += count
                
            except Exception as e:
                logger.error(f"❌ Failed to process result {search_id}: {e}")
                failed_count += 1
        
        logger.info(f"💾 BATCH STORAGE COMPLETE: {stored_count} stored, {failed_count} failed")
        
        if progress_callback:
            await progress_callback("serp_storage_completed", {
                'stored_count': stored_count,
                'failed_count': failed_count,
                'success_rate': (stored_count / max(stored_count + failed_count, 1)) * 100
            })
        
        # Create storage checkpoint
        if state_tracker and pipeline_execution_id:
            await state_tracker.create_checkpoint(
                pipeline_execution_id,
                "serp_collection",
                "storage_complete",
                {
                    'stored_count': stored_count,
                    'failed_count': failed_count,
                    'completed_at': datetime.utcnow().isoformat()
                }
            )
        
        return {'stored_count': stored_count, 'failed_count': failed_count}
    
    def _get_location_name(self, region_code: str) -> str:
        """Convert region code to location name"""
        location_map = {
            'US': 'United States',
            'UK': 'United Kingdom',
            'CA': 'Canada',
            'AU': 'Australia',
            'DE': 'Germany',
            'FR': 'France',
            'IT': 'Italy',
            'ES': 'Spain',
            'NL': 'Netherlands',
            'SE': 'Sweden'
        }
        return location_map.get(region_code, region_code)
    
    def _get_search_type(self, content_type: str) -> str:
        """Convert content type to search type"""
        search_type_map = {
            'organic': 'web',
            'news': 'news',
            'video': 'videos'
        }
        return search_type_map.get(content_type, 'web')
    
    async def _log_api_usage(self, keyword: str, headers: Dict) -> None:
        """Log API usage for tracking with enhanced metrics"""
        if not self.db:
            return
            
        try:
            # Extract quota info from headers
            quota_remaining = headers.get("X-API-Quota-Remaining")
            quota_limit = headers.get("X-API-Quota-Limit")
            
            # Calculate usage percentage
            usage_percentage = 0
            if quota_limit and quota_remaining:
                try:
                    usage_percentage = ((int(quota_limit) - int(quota_remaining)) / int(quota_limit)) * 100
                except:
                    pass
            
            await self.db.execute(
                """
                INSERT INTO api_usage (
                    id, api_name, service, endpoint, request_params, 
                    response_status, usage_date, created_at
                )
                VALUES (
                    gen_random_uuid(), 'scale_serp', 'scale_serp', '/search', 
                    $1, 200, CURRENT_DATE, NOW()
                )
                """,
                json.dumps({
                    "keyword": keyword,
                    "quota_remaining": quota_remaining,
                    "quota_limit": quota_limit,
                    "usage_percentage": usage_percentage
                })
            )
            
            # Log quota metrics
            if quota_remaining:
                self.logger.performance(
                    "api_quota",
                    int(quota_remaining),
                    unit="requests",
                    service="scale_serp",
                    quota_limit=quota_limit,
                    usage_percentage=usage_percentage
                )
                
        except Exception as e:
            logger.warning(f"Failed to log API usage: {e}")
    
    async def check_quota(self) -> Dict[str, Any]:
        """Check API quota status with detailed metrics"""
        quota_info = {
            "monthly_limit": self.monthly_limit,
            "overusage_limit": self.overusage_limit,
            "current_usage": 0,
            "remaining": self.monthly_limit,
            "usage_percentage": 0,
            "status": "healthy"
        }
        
        if not self.db:
            return quota_info
            
        try:
            async with self.db.acquire() as conn:
                # Get current month's usage
                result = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as usage_count
                    FROM api_usage
                    WHERE api_name = 'scale_serp'
                    AND usage_date >= date_trunc('month', CURRENT_DATE)
                    """
                )
                
                if result:
                    usage = result['usage_count']
                    quota_info['current_usage'] = usage
                    quota_info['remaining'] = max(0, self.monthly_limit - usage)
                    quota_info['usage_percentage'] = (usage / self.monthly_limit) * 100
                    
                    # Determine status
                    if usage >= self.monthly_limit + self.overusage_limit:
                        quota_info['status'] = 'exceeded'
                    elif usage >= self.monthly_limit:
                        quota_info['status'] = 'overusage'
                    elif usage >= self.monthly_limit * 0.9:
                        quota_info['status'] = 'warning'
                    
                    # Log quota status
                    self.logger.info(
                        f"API quota status",
                        service="scale_serp",
                        **quota_info
                    )
                    
        except Exception as e:
            logger.error(f"Failed to check quota: {e}")
            
        return quota_info
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources"""
        if self.client:
            await self.client.aclose()
            self.client = None
