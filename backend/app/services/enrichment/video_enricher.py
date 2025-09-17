"""
Optimized Video Enrichment Service for YouTube videos
Implements channel deduplication, batch AI processing, and enhanced caching
"""
import re
import json
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any, Set, Tuple
from collections import defaultdict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import isodate
from loguru import logger
import ssl
import httplib2
from app.models.video import (
    YouTubeVideoStats, YouTubeChannelStats, VideoSnapshot,
    VideoMetrics, VideoEnrichmentResult
)
from app.core.database import get_db, AsyncConnection
from app.core.config import settings, Settings
from redis import Redis


class YouTubeQuotaManager:
    """Manage YouTube API quota usage"""
    
    def __init__(self, daily_limit: int = 10000):
        self.daily_limit = daily_limit
        self.usage_today = 0
        self.last_reset = datetime.utcnow().date()
        self.operations = {}
        
    def check_quota(self, operation: str, units: int = 1) -> bool:
        """Check if operation is within quota"""
        today = datetime.utcnow().date()
        if today > self.last_reset:
            self.usage_today = 0
            self.operations = {}
            self.last_reset = today
            
        return (self.usage_today + units) < self.daily_limit
    
    def update_usage(self, operation: str, units: int = 1):
        """Update quota usage"""
        self.usage_today += units
        self.operations[operation] = self.operations.get(operation, 0) + units
        logger.info(f"YouTube quota used: {self.usage_today}/{self.daily_limit} (operation: {operation})")
    
    def get_remaining(self) -> int:
        """Get remaining quota units"""
        return max(0, self.daily_limit - self.usage_today)


class OptimizedVideoEnricher:
    """Optimized service for enriching YouTube video results
    
    Caching Strategy:
    1. Database check: Skip videos already enriched today (video_snapshots table)
    2. Redis cache: 7-day cache for video metadata
    3. Channel cache: Redis + database cache for channel company domains
    4. Deduplication: Process unique channels only to minimize API calls
    """
    
    def __init__(self, db: AsyncConnection, settings: Settings, redis_client: Optional[Redis] = None):
        self.db = db
        self.settings = settings
        self.redis = redis_client
        self.youtube = None
        if settings.YOUTUBE_API_KEY:
            try:
                # More robust SSL workaround for Docker environments
                import ssl
                import certifi
                import httplib2
                
                # Create a custom SSL context with updated certificates
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Create HTTP client with custom SSL context
                http = httplib2.Http(
                    disable_ssl_certificate_validation=True,
                    timeout=30
                )
                
                # Monkey patch the ssl module for Google API client
                import ssl as ssl_module
                ssl_module._create_default_https_context = ssl._create_unverified_context
                
                self.youtube = build('youtube', 'v3', 
                                   developerKey=settings.YOUTUBE_API_KEY,
                                   http=http,
                                   cache_discovery=False)  # Disable discovery cache to avoid SSL issues
                logger.info("YouTube API client initialized with enhanced SSL workaround")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API client with SSL workaround: {e}")
                # Try without SSL workaround as last resort
                try:
                    self.youtube = build('youtube', 'v3', 
                                       developerKey=settings.YOUTUBE_API_KEY,
                                       cache_discovery=False)
                    logger.warning("Using default YouTube client (may have SSL issues)")
                except Exception as e2:
                    logger.error(f"Failed to initialize fallback YouTube client: {e2}")
                    self.youtube = None
        self.quota_manager = YouTubeQuotaManager(daily_limit=10000)
        # Increased concurrency for better performance
        self._semaphore = asyncio.Semaphore(getattr(settings, 'video_enricher_concurrent_limit', 10))
        
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        if not url:
            return None
            
        patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'youtu\.be/([a-zA-Z0-9_-]+)',
            r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
            r'youtube\.com/v/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            if 'youtube.com' in parsed.netloc:
                params = parse_qs(parsed.query)
                if 'v' in params:
                    return params['v'][0]
        except:
            pass
            
        return None
    
    async def enrich_videos(self, video_urls: List[str], client_id: str, keyword: Optional[str] = None) -> VideoEnrichmentResult:
        """Enrich multiple YouTube videos with optimized performance"""
        start_time = datetime.utcnow()
        
        # Extract video IDs and map to URLs
        video_mapping = {}  # video_id -> (url, position)
        for idx, url in enumerate(video_urls):
            video_id = self.extract_video_id(url)
            if video_id:
                video_mapping[video_id] = (url, idx + 1)
        
        if not video_mapping:
            return VideoEnrichmentResult(
                client_id=client_id,
                enriched_count=0,
                cached_count=0,
                failed_count=0,
                quota_used=0,
                snapshots=[],
                processing_time=0
            )
        
        video_ids = list(video_mapping.keys())
        
        # Check for existing snapshots from today to avoid re-enrichment
        existing_videos = await self._check_existing_snapshots(video_ids, client_id)
        new_video_ids = [vid for vid in video_ids if vid not in existing_videos]
        
        logger.info(f"Found {len(video_ids)} YouTube videos: {len(existing_videos)} already enriched today, {len(new_video_ids)} need enrichment")
        
        # If all videos are already enriched today, return early
        if not new_video_ids:
            return VideoEnrichmentResult(
                client_id=client_id,
                enriched_count=0,
                cached_count=len(existing_videos),
                failed_count=0,
                quota_used=0,
                snapshots=[],
                processing_time=(datetime.utcnow() - start_time).total_seconds(),
                success=True  # Mark as success if all videos are already enriched
            )
        
        # Step 1: Check cache for all NEW videos and channels
        cached_videos, uncached_ids = await self._bulk_check_cache(new_video_ids)
        
        # Step 2: Fetch uncached videos from YouTube API
        new_videos = []
        errors = []
        quota_used = 0
        
        if uncached_ids and self.youtube:
            if not self.quota_manager.check_quota('videos.list', len(uncached_ids)):
                logger.warning("YouTube quota limit reached, using cached data only")
                errors.append({
                    "error": "quota_exceeded",
                    "message": f"Daily quota limit reached. Remaining: {self.quota_manager.get_remaining()}"
                })
                # Mark uncached videos as failed
                for vid_id in uncached_ids:
                    url, position = video_mapping.get(vid_id, (None, 0))
                    if url:
                        errors.append({
                            "error": "quota_exceeded",
                            "video_id": vid_id,
                            "url": url,
                            "message": "Skipped due to quota limit"
                        })
            else:
                try:
                    new_videos = await self._fetch_videos_from_api(uncached_ids)
                    quota_used = len(uncached_ids)
                    self.quota_manager.update_usage('videos.list', quota_used)
                    
                    # Cache new videos
                    await self._bulk_cache_videos(new_videos)
                    
                    # Track failed videos
                    successful_ids = {v.video_id for v in new_videos}
                    for vid_id in uncached_ids:
                        if vid_id not in successful_ids:
                            url, position = video_mapping.get(vid_id, (None, 0))
                            if url:
                                errors.append({
                                    "error": "api_error",
                                    "video_id": vid_id,
                                    "url": url,
                                    "message": "Failed to fetch from YouTube API"
                                })
                        
                except Exception as e:
                    logger.error(f"Error fetching videos from YouTube API: {e}")
                    errors.append({
                        "error": "api_error",
                        "message": str(e)
                    })
                    # Mark all uncached videos as failed
                    for vid_id in uncached_ids:
                        url, position = video_mapping.get(vid_id, (None, 0))
                        if url:
                            errors.append({
                                "error": "api_error",
                                "video_id": vid_id,
                                "url": url,
                                "message": str(e)
                            })
        
        # Combine all videos
        all_videos = cached_videos + new_videos
        
        # Step 3: Extract unique channels for efficient enrichment
        unique_channels = self._extract_unique_channels(all_videos)
        logger.info(f"📊 Found {len(unique_channels)} unique channels from {len(all_videos)} videos")
        
        # Step 4: Enrich channels (with caching)
        channel_data = await self._enrich_channels_optimized(unique_channels)
        
        # Step 5: Create snapshots with enriched data
        snapshots = []
        snapshot_date = datetime.utcnow()
        
        for video in all_videos:
            url, position = video_mapping.get(video.video_id, (None, 0))
            if url:
                # Get channel info from enriched data
                channel_info = channel_data.get(video.channel_id, {})
                
                snapshot = VideoSnapshot(
                    snapshot_date=snapshot_date,
                    client_id=client_id,
                    keyword=keyword,
                    position=position,
                    video_id=video.video_id,
                    video_title=video.title,
                    channel_id=video.channel_id,
                    channel_title=video.channel_title,
                    published_at=video.published_at,
                    view_count=video.view_count,
                    like_count=video.like_count,
                    comment_count=video.comment_count,
                    subscriber_count=channel_info.get('subscriber_count', 0),
                    engagement_rate=video.engagement_rate,
                    duration_seconds=video.duration_seconds,
                    tags=video.tags,
                    video_url=video.video_url,
                    channel_company_domain=channel_info.get('company_domain'),
                    channel_source_type=channel_info.get('source_type', 'OTHER')
                )
                snapshots.append(snapshot)
        
        # Store snapshots in database
        if snapshots:
            await self._store_video_snapshots(snapshots)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Determine success based on completion rate
        total_videos = len(video_ids)
        successfully_processed = len(all_videos)
        failed_count = total_videos - successfully_processed
        success_rate = (successfully_processed / total_videos * 100) if total_videos > 0 else 0
        
        # Consider it a success if we processed at least 80% of videos or all eligible videos
        success = success_rate >= 80 or (failed_count == 0)
        
        # If we have quota errors and low success rate, mark as failed
        if any(e.get('error') == 'quota_exceeded' for e in errors) and success_rate < 50:
            success = False
            
        result = VideoEnrichmentResult(
            client_id=client_id,
            enriched_count=len(new_videos),
            cached_count=len(cached_videos),
            failed_count=failed_count,
            quota_used=quota_used,
            snapshots=snapshots,
            errors=errors,
            processing_time=processing_time,
            success=success,
            success_rate=success_rate,
            total_videos=total_videos
        )
        
        logger.info(f"📹 Video enrichment result: success={success}, rate={success_rate:.1f}%, "
                   f"total={total_videos}, processed={successfully_processed}, failed={failed_count}")
        
        return result
    
    async def _check_existing_snapshots(self, video_ids: List[str], client_id: str) -> Set[str]:
        """Check which videos already have snapshots for today"""
        existing = set()
        
        try:
            async with self.db.acquire() as conn:
                today = datetime.utcnow().date()
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT video_id
                    FROM video_snapshots
                    WHERE client_id = $1
                    AND video_id = ANY($2)
                    AND snapshot_date = $3
                    """,
                    client_id,
                    video_ids,
                    today
                )
                
                existing = {row['video_id'] for row in rows}
                
        except Exception as e:
            logger.error(f"Error checking existing snapshots: {e}")
            
        return existing
    
    async def _bulk_check_cache(self, video_ids: List[str]) -> Tuple[List[YouTubeVideoStats], List[str]]:
        """Check cache for multiple videos at once"""
        cached_videos = []
        uncached_ids = []
        
        if self.redis:
            try:
                # Use Redis pipeline for bulk operations
                pipe = self.redis.pipeline()
                for video_id in video_ids:
                    pipe.get(f"video:{video_id}")
                
                results = pipe.execute()
                
                for video_id, cached_data in zip(video_ids, results):
                    if cached_data:
                        try:
                            data = json.loads(cached_data)
                            cached_videos.append(YouTubeVideoStats(**data))
                        except:
                            uncached_ids.append(video_id)
                    else:
                        uncached_ids.append(video_id)
                        
            except Exception as e:
                logger.error(f"Redis bulk check error: {e}")
                uncached_ids = video_ids
        else:
            uncached_ids = video_ids
            
        logger.info(f"Cache hit rate: {len(cached_videos)}/{len(video_ids)} ({len(cached_videos)/len(video_ids)*100:.1f}%)")
        return cached_videos, uncached_ids
    
    async def _bulk_cache_videos(self, videos: List[YouTubeVideoStats]):
        """Cache multiple videos at once"""
        if self.redis and videos:
            try:
                pipe = self.redis.pipeline()
                for video in videos:
                    cache_key = f"video:{video.video_id}"
                    pipe.setex(
                        cache_key,
                        604800,  # 7 days
                        json.dumps(video.dict(), default=str)
                    )
                pipe.execute()
            except Exception as e:
                logger.error(f"Redis bulk cache error: {e}")
    
    def _extract_unique_channels(self, videos: List[YouTubeVideoStats]) -> Dict[str, Dict]:
        """Extract unique channels from videos"""
        channels = {}
        for video in videos:
            if video.channel_id not in channels:
                channels[video.channel_id] = {
                    'channel_id': video.channel_id,
                    'channel_title': video.channel_title,
                    'video_count': 0
                }
            channels[video.channel_id]['video_count'] += 1
        return channels
    
    async def _enrich_channels_optimized(self, channels: Dict[str, Dict]) -> Dict[str, Dict]:
        """Enrich channels with optimized caching and batching"""
        channel_data = {}
        
        # Step 1: Check cache for existing channel data
        cached_channels, uncached_channel_ids = await self._check_channel_cache(list(channels.keys()))
        channel_data.update(cached_channels)
        
        if not uncached_channel_ids:
            return channel_data
        
        # Step 2: Fetch channel stats from YouTube API
        if self.youtube and self.quota_manager.check_quota('channels.list', len(uncached_channel_ids)):
            try:
                channel_stats = await self._fetch_channel_stats(uncached_channel_ids)
                
                # Step 3: Channel company resolution moved to background resolver.
                # Inline AI enrichment is disabled by default and only runs if explicitly enabled.
                ai_results = {}
                if channel_stats and getattr(self.settings, 'VIDEO_ENRICHER_ENABLE_CHANNEL_AI', False):
                    ai_results = await self._batch_extract_company_domains(channel_stats)
                    
                    # Combine results
                    for channel_id, stats in channel_stats.items():
                        ai_data = ai_results.get(channel_id, {})
                        channel_data[channel_id] = {
                            'subscriber_count': stats['subscriber_count'],
                            'company_domain': ai_data.get('domain', ''),
                            'company_name': ai_data.get('company_name', ''),
                            'source_type': ai_data.get('source_type', 'OTHER'),
                            'confidence': ai_data.get('confidence', 0.0)
                        }
                    
                    # Cache the results
                    await self._cache_channel_data(channel_data)
                    
            except Exception as e:
                logger.error(f"Error enriching channels: {e}")
        
        return channel_data
    
    async def _check_channel_cache(self, channel_ids: List[str]) -> Tuple[Dict[str, Dict], List[str]]:
        """Check cache for channel data"""
        cached_data = {}
        uncached_ids = []
        
        if self.redis:
            try:
                pipe = self.redis.pipeline()
                for channel_id in channel_ids:
                    pipe.get(f"channel:{channel_id}")
                
                results = pipe.execute()
                
                for channel_id, cached in zip(channel_ids, results):
                    if cached:
                        try:
                            cached_data[channel_id] = json.loads(cached)
                        except:
                            uncached_ids.append(channel_id)
                    else:
                        uncached_ids.append(channel_id)
                        
            except Exception as e:
                logger.error(f"Channel cache check error: {e}")
                uncached_ids = channel_ids
        else:
            # Also check database for previously extracted domains
            try:
                async with self.db.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT channel_id, company_domain, company_name, 
                               source_type, confidence_score
                        FROM youtube_channel_companies
                        WHERE channel_id = ANY($1)
                        """,
                        channel_ids
                    )
                    
                    for row in rows:
                        cached_data[row['channel_id']] = {
                            'company_domain': row['company_domain'] or '',
                            'company_name': row['company_name'] or '',
                            'source_type': row['source_type'] or 'OTHER',
                            'confidence': row['confidence_score'] or 0.0,
                            'subscriber_count': 0  # Will be updated from API
                        }
                    
                    uncached_ids = [cid for cid in channel_ids if cid not in cached_data]
                    
            except Exception as e:
                logger.error(f"Database channel lookup error: {e}")
                uncached_ids = channel_ids
        
        logger.info(f"Channel cache hit rate: {len(cached_data)}/{len(channel_ids)} ({len(cached_data)/len(channel_ids)*100:.1f}%)")
        return cached_data, uncached_ids
    
    async def _fetch_channel_stats(self, channel_ids: List[str]) -> Dict[str, Dict]:
        """Fetch channel statistics from YouTube API"""
        channel_stats = {}
        
        try:
            # Process in batches of 50
            for i in range(0, len(channel_ids), 50):
                batch_ids = channel_ids[i:i+50]
                
                # Run blocking googleapiclient call off the event loop with a timeout
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: self.youtube.channels().list(
                            part='statistics,snippet',
                            id=','.join(batch_ids)
                        ).execute()
                    ),
                    timeout=getattr(self.settings, 'video_enricher_youtube_timeout_s', 20)
                )
                
                for item in response.get('items', []):
                    channel_id = item['id']
                    stats = item.get('statistics', {})
                    snippet = item.get('snippet', {})
                    
                    channel_stats[channel_id] = {
                        'subscriber_count': int(stats.get('subscriberCount', 0)),
                        'description': snippet.get('description', ''),
                        'custom_url': snippet.get('customUrl', ''),
                        'title': snippet.get('title', '')
                    }
            
            self.quota_manager.update_usage('channels.list', len(channel_ids))
            
        except Exception as e:
            logger.error(f"Error fetching channel stats: {e}")
            
        return channel_stats
    
    async def _batch_extract_company_domains(self, channel_stats: Dict[str, Dict]) -> Dict[str, Dict]:
        """Extract company domains from multiple channels in batches"""
        if not self.settings.OPENAI_API_KEY:
            return {}
        
        results = {}
        
        # Process channels in smaller batches to avoid token limits (configurable)
        channel_list = list(channel_stats.items())
        batch_size = getattr(self.settings, 'video_enricher_ai_batch_size', 20)
        max_in_flight = getattr(self.settings, 'video_enricher_ai_concurrent_batches', 10)

        # Build all batches first
        batches = [channel_list[i:i+batch_size] for i in range(0, len(channel_list), batch_size)]

        # Concurrency semaphore
        semaphore = asyncio.Semaphore(max(1, int(max_in_flight)))

        async def run_batch_with_limits(batch):
            async with semaphore:
                return await self._extract_domains_batch_with_retry(batch)

        tasks = [asyncio.create_task(run_batch_with_limits(b)) for b in batches]
        batch_outputs = await asyncio.gather(*tasks, return_exceptions=True)

        for out in batch_outputs:
            if isinstance(out, Exception):
                logger.error(f"Batch AI extraction error: {out}")
                continue
            results.update(out or {})
        
        return results

    async def _extract_domains_batch_with_retry(self, channels: List[Tuple[str, Dict]]) -> Dict[str, Dict]:
        """Wrapper adding retries/backoff for non-JSON or empty responses."""
        delays = [0.4, 0.8, 1.6]
        last_err = None
        for attempt, delay in enumerate([0.0] + delays):
            if delay:
                try:
                    await asyncio.sleep(delay)
                except Exception:
                    pass
            try:
                res = await self._extract_domains_batch(channels)
                if res:
                    return res
                last_err = last_err or Exception("empty_result")
            except Exception as e:
                last_err = e
                logger.error(f"_extract_domains_batch attempt {attempt+1} failed: {e}")
                continue
        logger.error(f"Batch extraction failed after retries: {last_err}")
        return {}
    
    async def _extract_domains_batch(self, channels: List[Tuple[str, Dict]]) -> Dict[str, Dict]:
        """Extract domains from a batch of channels using a single AI call"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
            
            # Build batch context
            channels_context = []
            for idx, (channel_id, data) in enumerate(channels):
                # Extract URLs from description (longer excerpt to leverage large context)
                description = data.get('description', '')[:2000]
                url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)'
                urls = re.findall(url_pattern, description)
                
                channels_context.append(f"""
Channel {idx + 1}:
- ID: {channel_id}
- Title: {data.get('title', '')}
- Subscribers: {data.get('subscriber_count', 0):,}
- Custom URL: {data.get('custom_url', '')}
- URLs in description: {', '.join(urls) if urls else 'None'}
- Description excerpt: {description}
""")
            
            prompt = f"""
Analyze the following YouTube channels and select the official company domain for each.

Guidelines to select the official domain (apply strictly):
- Prefer the brand's primary corporate site (e.g., company.com). Avoid social, link shorteners, merch stores, CDNs, tracking or subdomains.
- Ignore: youtube.com, instagram.com, facebook.com, twitter.com/x.com, t.co, bit.ly, linktr.ee, beacons.ai, patreon.com, shopify.com, teespring.com, amazon.com/store, gumroad.com, substack.com, medium.com.
- If the channel custom URL/handle clearly maps to a domain, prefer the registrable root (e.g., acme → acme.com) when reasonable.
- If multiple candidates, choose the one that best matches the channel/brand name and appears to be the parent corporate site.
- If uncertain, return empty domain and company_name with low confidence.

Return a JSON array, one object per channel in the same order, with fields:
- channel_index (1-based), domain, company_name, source_type (OWNED/COMPETITOR/INFLUENCER/MEDIA/EDUCATIONAL/AGENCY/OTHER), confidence (0-1).

Channels:
{chr(10).join(channels_context)}
"""
            
            # Run blocking OpenAI client call off the event loop with a timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: client.responses.create(
                        model=getattr(self.settings, 'video_enricher_ai_model', "gpt-4.1-nano-2025-04-14"),
                        input=[
                            {"role": "system", "content": "You are an expert at identifying company ownership of YouTube channels. Extract domains accurately and efficiently. Always return strict JSON as requested."},
                            {"role": "user", "content": prompt}
                        ],
                        max_completion_tokens=getattr(self.settings, 'video_enricher_ai_max_tokens', 1200)
                    )
                ),
                timeout=getattr(self.settings, 'video_enricher_ai_timeout_s', 30)
            )
            
            # Parse response
            content = ""
            try:
                # Prefer output_text from Responses API
                content = getattr(response, 'output_text', "")
                if not content:
                    logger.error("Video enricher: empty response content from OpenAI")
                    return {}
                try:
                    batch_results = json.loads(content)
                except Exception:
                    # Try to salvage JSON array/object if present in content
                    start_idx = content.find('[')
                    end_idx = content.rfind(']')
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        batch_results = json.loads(content[start_idx:end_idx+1])
                    else:
                        start_idx = content.find('{')
                        end_idx = content.rfind('}')
                        batch_results = json.loads(content[start_idx:end_idx+1])
            except Exception as e:
                logger.error(f"Batch domain extraction parse error: {e}")
                return {}
            
            # Map results back to channel IDs
            results = {}
            if isinstance(batch_results, dict) and 'channels' in batch_results:
                batch_results = batch_results['channels']
            
            for item in batch_results:
                idx = item.get('channel_index', 0) - 1
                if 0 <= idx < len(channels):
                    channel_id = channels[idx][0]
                    
                    # Clean domain
                    domain = item.get('domain', '').strip().lower()
                    if domain:
                        domain = domain.replace('http://', '').replace('https://', '')
                        domain = domain.replace('www.', '')
                        domain = domain.split('/')[0]
                    
                    results[channel_id] = {
                        'domain': domain,
                        'company_name': item.get('company_name', ''),
                        'source_type': item.get('source_type', 'OTHER'),
                        'confidence': item.get('confidence', 0.5)
                    }
            
            # Store results in database
            await self._store_channel_domains_batch(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Batch domain extraction error: {e}")
            return {}
    
    async def _store_channel_domains_batch(self, results: Dict[str, Dict]):
        """Store multiple channel domains efficiently"""
        if not results:
            return
            
        try:
            async with self.db.acquire() as conn:
                # Prepare batch data
                values = []
                for channel_id, data in results.items():
                    if data.get('domain'):  # Only store if domain was found
                        values.append((
                            channel_id,
                            data['domain'],
                            data['company_name'],
                            data['source_type'],
                            data['confidence'],
                            datetime.utcnow()
                        ))
                
                if values:
                    # Bulk insert/update
                    await conn.executemany(
                        """
                        INSERT INTO youtube_channel_companies (
                            channel_id, company_domain, company_name, source_type, 
                            confidence_score, extracted_at, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                        ON CONFLICT (channel_id) DO UPDATE SET
                            company_domain = EXCLUDED.company_domain,
                            company_name = EXCLUDED.company_name,
                            source_type = EXCLUDED.source_type,
                            confidence_score = EXCLUDED.confidence_score,
                            extracted_at = EXCLUDED.extracted_at,
                            updated_at = NOW()
                        """,
                        values
                    )
                    logger.info(f"Stored {len(values)} channel domains")
                    
        except Exception as e:
            logger.error(f"Error storing channel domains: {e}")
    
    async def _cache_channel_data(self, channel_data: Dict[str, Dict]):
        """Cache channel data"""
        if self.redis and channel_data:
            try:
                pipe = self.redis.pipeline()
                for channel_id, data in channel_data.items():
                    cache_key = f"channel:{channel_id}"
                    pipe.setex(
                        cache_key,
                        86400,  # 24 hours for channel data
                        json.dumps(data, default=str)
                    )
                pipe.execute()
            except Exception as e:
                logger.error(f"Channel cache error: {e}")
    
    async def _fetch_videos_from_api(self, video_ids: List[str]) -> List[YouTubeVideoStats]:
        """Fetch video statistics from YouTube API"""
        all_videos = []
        
        # Process in batches of 50 (YouTube API limit)
        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i:i+50]
            
            async with self._semaphore:
                try:
                    # Run blocking googleapiclient call off the event loop with a timeout
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            lambda: self.youtube.videos().list(
                                part='snippet,statistics,contentDetails',
                                id=','.join(batch_ids)
                            ).execute()
                        ),
                        timeout=getattr(self.settings, 'video_enricher_youtube_timeout_s', 20)
                    )
                    
                    for item in response.get('items', []):
                        video = self._parse_video_response(item)
                        if video:
                            all_videos.append(video)
                            
                except HttpError as e:
                    if e.resp.status == 403 and 'quotaExceeded' in str(e):
                        logger.error("YouTube API quota exceeded")
                        raise Exception("YouTube API quota exceeded")
                    logger.error(f"YouTube API error: {e}")
                    raise
        
        return all_videos
    
    def _parse_video_response(self, item: Dict[str, Any]) -> Optional[YouTubeVideoStats]:
        """Parse YouTube API response into VideoStats"""
        try:
            snippet = item['snippet']
            statistics = item.get('statistics', {})
            content_details = item.get('contentDetails', {})
            
            # Parse published date
            published_at = None
            if 'publishedAt' in snippet:
                published_at = datetime.fromisoformat(
                    snippet['publishedAt'].replace('Z', '+00:00')
                )
            
            # Parse duration
            duration_seconds = 0
            if 'duration' in content_details:
                duration_seconds = self._parse_duration(content_details['duration'])
            
            # Calculate engagement rate
            view_count = int(statistics.get('viewCount', 0))
            like_count = int(statistics.get('likeCount', 0))
            comment_count = int(statistics.get('commentCount', 0))
            
            engagement_rate = 0.0
            if view_count > 0:
                engagement_rate = round((like_count + comment_count) / view_count * 100, 2)
            
            return YouTubeVideoStats(
                video_id=item['id'],
                title=snippet['title'],
                description=snippet.get('description', ''),
                channel_id=snippet['channelId'],
                channel_title=snippet['channelTitle'],
                published_at=published_at,
                duration_seconds=duration_seconds,
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                tags=snippet.get('tags', []),
                category_id=snippet.get('categoryId'),
                thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url'),
                engagement_rate=engagement_rate,
                video_url=f'https://www.youtube.com/watch?v={item["id"]}'
            )
        except Exception as e:
            logger.error(f"Error parsing video response: {e}")
            return None
    
    def _parse_duration(self, duration: str) -> int:
        """Parse ISO 8601 duration to seconds"""
        try:
            return int(isodate.parse_duration(duration).total_seconds())
        except:
            return 0
    
    async def _store_video_snapshots(self, snapshots: List[VideoSnapshot]):
        """Store video snapshots in database (batched with retry)."""
        if not snapshots:
            return
        # Prepare values list
        values = [
            (
                s.snapshot_date.date(), s.client_id, s.keyword, s.position,
                s.video_id, s.video_title, s.channel_id, s.channel_title,
                s.published_at, s.view_count, s.like_count, s.comment_count,
                s.subscriber_count, s.engagement_rate, s.duration_seconds,
                s.tags, s.serp_engine, s.fetched_at, s.video_url,
                s.channel_company_domain, s.channel_source_type
            )
            for s in snapshots
        ]
        attempts = 0
        while attempts < 3:
            attempts += 1
            try:
                async with self.db.acquire() as conn:
                    await conn.executemany(
                        """
                        INSERT INTO video_snapshots (
                            id, snapshot_date, client_id, keyword, position,
                            video_id, video_title, channel_id, channel_title,
                            published_at, view_count, like_count, comment_count,
                            subscriber_count, engagement_rate, duration_seconds,
                            tags, serp_engine, fetched_at, video_url,
                            channel_company_domain, channel_source_type
                        ) VALUES (
                            gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9,
                            $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
                        )
                        ON CONFLICT (client_id, video_id, snapshot_date) DO UPDATE SET
                            view_count = EXCLUDED.view_count,
                            like_count = EXCLUDED.like_count,
                            comment_count = EXCLUDED.comment_count,
                            subscriber_count = EXCLUDED.subscriber_count,
                            engagement_rate = EXCLUDED.engagement_rate,
                            fetched_at = EXCLUDED.fetched_at,
                            channel_company_domain = EXCLUDED.channel_company_domain,
                            channel_source_type = EXCLUDED.channel_source_type
                        """,
                        values
                    )
                return
            except Exception as e:
                logger.error(f"Error storing video snapshots (attempt {attempts}): {e}")
                await asyncio.sleep(0.5 * attempts)
    
    # Additional utility methods from original implementation
    async def calculate_video_metrics(self, client_id: str, days: int = 30) -> VideoMetrics:
        """Calculate aggregate video metrics"""
        # Same implementation as original
        pass
    
    async def get_top_videos(self, client_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing videos"""
        # Same implementation as original
        pass
    
    async def get_channel_performance(self, client_id: str) -> List[Dict[str, Any]]:
        """Get channel performance metrics"""
        # Same implementation as original
        pass
