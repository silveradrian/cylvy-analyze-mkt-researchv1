"""
Enhanced YouTube Quota Management for Pipeline Processing
"""

import asyncio
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import asyncpg
from loguru import logger
import redis.asyncio as redis

from app.core.config import Settings


class PersistentQuotaManager:
    """Manages YouTube API quota with persistence and smart scheduling"""
    
    # YouTube API quota costs (in units)
    QUOTA_COSTS = {
        'videos.list': 1,  # Per request (up to 50 videos)
        'channels.list': 1,  # Per request (up to 50 channels)
        'search.list': 100,  # Per request
        'comments.list': 1,  # Per request
        'commentThreads.list': 1,  # Per request
    }
    
    def __init__(self, redis_client: redis.Redis, daily_limit: int = 10000):
        self.redis = redis_client
        self.daily_limit = daily_limit
        self.cache_prefix = "youtube_quota:"
        
    async def get_current_usage(self) -> Dict:
        """Get current quota usage from Redis"""
        today = datetime.utcnow().date().isoformat()
        key = f"{self.cache_prefix}{today}"
        
        # Get usage data
        usage_data = await self.redis.get(key)
        if usage_data:
            return json.loads(usage_data)
        
        # Initialize for new day
        return {
            'date': today,
            'total_used': 0,
            'operations': {},
            'last_updated': datetime.utcnow().isoformat()
        }
    
    async def update_usage(self, operation: str, units: int) -> bool:
        """Update quota usage and return True if successful"""
        usage = await self.get_current_usage()
        
        # Check if we have enough quota
        if usage['total_used'] + units > self.daily_limit:
            logger.warning(f"YouTube quota limit would be exceeded. Current: {usage['total_used']}, Requested: {units}")
            return False
        
        # Update usage
        usage['total_used'] += units
        usage['operations'][operation] = usage['operations'].get(operation, 0) + units
        usage['last_updated'] = datetime.utcnow().isoformat()
        
        # Save to Redis with 48 hour expiry (in case of timezone issues)
        today = datetime.utcnow().date().isoformat()
        key = f"{self.cache_prefix}{today}"
        await self.redis.setex(key, 48 * 3600, json.dumps(usage))
        
        logger.info(f"YouTube quota updated: {usage['total_used']}/{self.daily_limit} "
                   f"(+{units} for {operation})")
        
        return True
    
    async def get_remaining_quota(self) -> int:
        """Get remaining quota for today"""
        usage = await self.get_current_usage()
        return max(0, self.daily_limit - usage['total_used'])
    
    async def estimate_video_batch_size(self) -> int:
        """Estimate how many videos we can process with remaining quota"""
        remaining = await self.get_remaining_quota()
        
        # Each videos.list request can handle 50 videos for 1 unit
        # Reserve 10% for other operations
        usable_quota = int(remaining * 0.9)
        
        # Calculate max videos (50 videos per unit)
        max_videos = usable_quota * 50
        
        return max_videos
    
    async def wait_for_quota_reset(self) -> datetime:
        """Calculate when quota will reset (Pacific Time)"""
        # YouTube quota resets at midnight Pacific Time
        from zoneinfo import ZoneInfo
        
        now_utc = datetime.now(ZoneInfo('UTC'))
        now_pacific = now_utc.astimezone(ZoneInfo('America/Los_Angeles'))
        
        # Next reset is tomorrow at midnight Pacific
        tomorrow = now_pacific.date() + timedelta(days=1)
        reset_time_pacific = datetime.combine(tomorrow, datetime.min.time())
        reset_time_pacific = reset_time_pacific.replace(tzinfo=ZoneInfo('America/Los_Angeles'))
        
        # Convert back to UTC
        reset_time_utc = reset_time_pacific.astimezone(ZoneInfo('UTC'))
        
        return reset_time_utc
    
    async def get_quota_status(self) -> Dict:
        """Get detailed quota status"""
        usage = await self.get_current_usage()
        remaining = await self.get_remaining_quota()
        reset_time = await self.wait_for_quota_reset()
        max_batch = await self.estimate_video_batch_size()
        
        return {
            'date': usage['date'],
            'used': usage['total_used'],
            'limit': self.daily_limit,
            'remaining': remaining,
            'percentage_used': round((usage['total_used'] / self.daily_limit) * 100, 2),
            'operations': usage['operations'],
            'reset_time_utc': reset_time.isoformat(),
            'hours_until_reset': (reset_time - datetime.now(reset_time.tzinfo)).total_seconds() / 3600,
            'estimated_videos_available': max_batch
        }


class SmartVideoProcessor:
    """Processes videos with intelligent quota management"""
    
    def __init__(self, db_pool: asyncpg.Pool, redis_client: redis.Redis, settings: Settings):
        self.db_pool = db_pool
        self.redis = redis_client
        self.settings = settings
        self.quota_manager = PersistentQuotaManager(redis_client)
        
    async def process_videos_with_quota(self, limit: Optional[int] = None) -> Dict:
        """Process videos while respecting quota limits"""
        start_time = datetime.utcnow()
        results = {
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'quota_exhausted': False,
            'next_batch_time': None
        }
        
        # Check current quota
        quota_status = await self.quota_manager.get_quota_status()
        logger.info(f"YouTube Quota Status: {quota_status['used']}/{quota_status['limit']} "
                   f"({quota_status['percentage_used']}% used)")
        
        if quota_status['remaining'] < 10:
            logger.warning("Insufficient YouTube quota remaining. Waiting for reset.")
            results['quota_exhausted'] = True
            results['next_batch_time'] = quota_status['reset_time_utc']
            return results
        
        # Get batch size based on available quota
        max_videos = await self.quota_manager.estimate_video_batch_size()
        if limit:
            max_videos = min(max_videos, limit)
        
        logger.info(f"Processing up to {max_videos} videos based on quota availability")
        
        # Get unenriched videos
        async with self.db_pool.acquire() as conn:
            videos = await conn.fetch("""
                SELECT DISTINCT v.url, v.video_id
                FROM serp_results sr
                JOIN video_content v ON sr.url = v.url
                LEFT JOIN video_snapshots vs ON v.video_id = vs.video_id AND vs.client_id = 'ncino'
                WHERE sr.client_id = 'ncino'
                AND sr.serp_type = 'video'
                AND vs.video_id IS NULL
                AND v.video_id IS NOT NULL
                LIMIT $1
            """, max_videos)
            
            if not videos:
                logger.info("No unenriched videos found")
                return results
            
            logger.info(f"Found {len(videos)} videos to process")
            
            # Process in batches of 50 (YouTube API limit per request)
            from app.services.video_enricher import VideoEnricher
            
            enricher = VideoEnricher(conn, self.settings, self.redis)
            batch_size = 50
            
            for i in range(0, len(videos), batch_size):
                batch = videos[i:i+batch_size]
                video_urls = [v['url'] for v in batch]
                
                # Check quota before each batch
                required_units = 1  # 1 unit per videos.list request
                if not await self.quota_manager.update_usage('videos.list', required_units):
                    logger.warning("Quota limit reached during processing")
                    results['quota_exhausted'] = True
                    results['next_batch_time'] = (await self.quota_manager.wait_for_quota_reset()).isoformat()
                    break
                
                try:
                    # Process batch
                    result = await enricher.enrich_videos(
                        video_urls=video_urls,
                        client_id='ncino'
                    )
                    
                    results['processed'] += result.enriched_count
                    results['failed'] += result.failed_count
                    
                    logger.info(f"Batch {i//batch_size + 1}: Enriched {result.enriched_count} videos")
                    
                except Exception as e:
                    logger.error(f"Error processing video batch: {e}")
                    results['failed'] += len(batch)
                
                # Small delay between batches
                await asyncio.sleep(1)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Video processing completed in {processing_time:.2f}s - "
                   f"Processed: {results['processed']}, Failed: {results['failed']}")
        
        return results
    
    async def schedule_video_processing(self) -> Dict:
        """Schedule video processing based on quota availability"""
        quota_status = await self.quota_manager.get_quota_status()
        
        # Calculate optimal batch sizes for remaining videos
        async with self.db_pool.acquire() as conn:
            total_unenriched = await conn.fetchval("""
                SELECT COUNT(DISTINCT v.url)
                FROM serp_results sr
                JOIN video_content v ON sr.url = v.url
                LEFT JOIN video_snapshots vs ON v.video_id = vs.video_id AND vs.client_id = 'ncino'
                WHERE sr.client_id = 'ncino'
                AND sr.serp_type = 'video'
                AND vs.video_id IS NULL
                AND v.video_id IS NOT NULL
            """)
        
        if not total_unenriched:
            return {
                'status': 'complete',
                'total_videos': 0,
                'message': 'All videos have been enriched'
            }
        
        # Calculate processing schedule
        videos_per_unit = 50  # YouTube allows 50 videos per API call
        units_needed = (total_unenriched + videos_per_unit - 1) // videos_per_unit
        days_needed = (units_needed + int(self.quota_manager.daily_limit * 0.9) - 1) // int(self.quota_manager.daily_limit * 0.9)
        
        today_capacity = quota_status['estimated_videos_available']
        
        return {
            'status': 'scheduled',
            'total_videos': total_unenriched,
            'units_required': units_needed,
            'days_required': days_needed,
            'today_capacity': today_capacity,
            'quota_status': quota_status,
            'recommendation': f"Can process {today_capacity} videos today. "
                            f"Full processing will take approximately {days_needed} days."
        }