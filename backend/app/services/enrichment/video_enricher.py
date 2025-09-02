"""
Video Enrichment Service for YouTube videos
"""
import re
import json
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import isodate
import logging

logger = logging.getLogger(__name__)
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
        # Reset if new day
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


class VideoEnricher:
    """Service for enriching YouTube video results"""
    
    def __init__(self, db: AsyncConnection, settings: Settings, redis_client: Optional[Redis] = None):
        self.db = db
        self.settings = settings
        self.redis = redis_client
        self.youtube = None
        if settings.youtube_api_key:
            self.youtube = build('youtube', 'v3', developerKey=settings.youtube_api_key)
        self.quota_manager = YouTubeQuotaManager(daily_limit=10000)
        self._semaphore = asyncio.Semaphore(settings.video_enricher_concurrent_limit or 5)
        
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
        
        # Try URL parsing as fallback
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
        """Enrich multiple YouTube videos"""
        start_time = datetime.utcnow()
        
        # Extract video IDs
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
        logger.info(f"Found {len(video_ids)} YouTube videos to enrich")
        
        # Check cache first
        cached_videos = []
        uncached_ids = []
        
        for video_id in video_ids:
            cached = await self._get_cached_video(video_id)
            if cached:
                cached_videos.append(cached)
            else:
                uncached_ids.append(video_id)
        
        # Fetch uncached videos from YouTube API
        new_videos = []
        errors = []
        quota_used = 0
        
        if uncached_ids and self.youtube:
            # Check quota
            if not self.quota_manager.check_quota('videos.list', len(uncached_ids)):
                logger.warning("YouTube quota limit reached, using cached data only")
                errors.append({
                    "error": "quota_exceeded",
                    "message": f"Daily quota limit reached. Remaining: {self.quota_manager.get_remaining()}"
                })
            else:
                try:
                    new_videos = await self._fetch_videos_from_api(uncached_ids)
                    quota_used = len(uncached_ids)
                    self.quota_manager.update_usage('videos.list', quota_used)
                    
                    # Cache new videos
                    for video in new_videos:
                        await self._cache_video(video)
                        
                except Exception as e:
                    logger.error(f"Error fetching videos from YouTube API: {e}")
                    errors.append({
                        "error": "api_error",
                        "message": str(e)
                    })
        
        # Combine all videos
        all_videos = cached_videos + new_videos
        
        # Create snapshots
        snapshots = []
        snapshot_date = datetime.utcnow()
        
        for video in all_videos:
            url, position = video_mapping.get(video.video_id, (None, 0))
            if url:
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
                    subscriber_count=0,  # Will be enriched with channel data
                    engagement_rate=video.engagement_rate,
                    duration_seconds=video.duration_seconds,
                    tags=video.tags,
                    video_url=video.video_url
                )
                snapshots.append(snapshot)
        
        # Get channel data for subscriber counts
        if snapshots and self.youtube:
            await self._enrich_with_channel_data(snapshots)
        
        # Store snapshots in database
        if snapshots:
            await self._store_video_snapshots(snapshots)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return VideoEnrichmentResult(
            client_id=client_id,
            enriched_count=len(new_videos),
            cached_count=len(cached_videos),
            failed_count=len(video_ids) - len(all_videos),
            quota_used=quota_used,
            snapshots=snapshots,
            errors=errors,
            processing_time=processing_time
        )
    
    async def _fetch_videos_from_api(self, video_ids: List[str]) -> List[YouTubeVideoStats]:
        """Fetch video statistics from YouTube API"""
        all_videos = []
        
        # Process in batches of 50 (YouTube API limit)
        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i:i+50]
            
            async with self._semaphore:
                try:
                    # Run in thread to avoid blocking
                    response = await asyncio.to_thread(
                        self.youtube.videos().list(
                            part='snippet,statistics,contentDetails',
                            id=','.join(batch_ids)
                        ).execute
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
    
    async def _enrich_with_channel_data(self, snapshots: List[VideoSnapshot]):
        """Enrich snapshots with channel subscriber counts"""
        # Get unique channel IDs
        channel_ids = list(set(s.channel_id for s in snapshots))
        
        if not channel_ids or not self.quota_manager.check_quota('channels.list', len(channel_ids)):
            return
        
        # Fetch channel data
        channel_map = {}
        
        try:
            # Process in batches of 50
            for i in range(0, len(channel_ids), 50):
                batch_ids = channel_ids[i:i+50]
                
                response = await asyncio.to_thread(
                    self.youtube.channels().list(
                        part='statistics,snippet',
                        id=','.join(batch_ids)
                    ).execute
                )
                
                for item in response.get('items', []):
                    channel_id = item['id']
                    stats = item.get('statistics', {})
                    snippet = item.get('snippet', {})
                    subscriber_count = int(stats.get('subscriberCount', 0))
                    channel_map[channel_id] = {
                        'subscriber_count': subscriber_count,
                        'description': snippet.get('description', ''),
                        'custom_url': snippet.get('customUrl', '')
                    }
            
            self.quota_manager.update_usage('channels.list', len(channel_ids))
            
            # Update snapshots
            for snapshot in snapshots:
                if snapshot.channel_id in channel_map:
                    channel_data = channel_map[snapshot.channel_id]
                    snapshot.subscriber_count = channel_data['subscriber_count']
                    # Store channel description in video data for later use
                    if hasattr(snapshot, 'channel_description'):
                        snapshot.channel_description = channel_data['description']
                    if hasattr(snapshot, 'channel_custom_url'):
                        snapshot.channel_custom_url = channel_data['custom_url']
                    
        except Exception as e:
            logger.error(f"Error fetching channel data: {e}")
    
    async def _get_cached_video(self, video_id: str) -> Optional[YouTubeVideoStats]:
        """Get cached video data"""
        if self.redis:
            try:
                cache_key = f"video:{video_id}"
                cached = await asyncio.to_thread(self.redis.get, cache_key)
                if cached:
                    data = json.loads(cached)
                    return YouTubeVideoStats(**data)
            except Exception as e:
                logger.error(f"Redis error: {e}")
        return None
    
    async def _cache_video(self, video_data: YouTubeVideoStats):
        """Cache video data for 7 days"""
        if self.redis:
            try:
                cache_key = f"video:{video_data.video_id}"
                await asyncio.to_thread(
                    self.redis.setex,
                    cache_key,
                    604800,  # 7 days
                    json.dumps(video_data.dict(), default=str)
                )
            except Exception as e:
                logger.error(f"Redis error: {e}")
    
    async def _store_video_snapshots(self, snapshots: List[VideoSnapshot]):
        """Store video snapshots in database"""
        
        for snapshot in snapshots:
            try:
                await self.db.execute(
                    """
                    INSERT INTO video_snapshots (
                        id, snapshot_date, client_id, keyword, position,
                        video_id, video_title, channel_id, channel_title,
                        published_at, view_count, like_count, comment_count,
                        subscriber_count, engagement_rate, duration_seconds,
                        tags, serp_engine, fetched_at, video_url
                    ) VALUES (
                        gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9,
                        $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
                    )
                    ON CONFLICT (client_id, video_id, snapshot_date) DO UPDATE SET
                        view_count = EXCLUDED.view_count,
                        like_count = EXCLUDED.like_count,
                        comment_count = EXCLUDED.comment_count,
                        subscriber_count = EXCLUDED.subscriber_count,
                        engagement_rate = EXCLUDED.engagement_rate,
                        fetched_at = EXCLUDED.fetched_at
                    """,
                    snapshot.snapshot_date.date(),
                    snapshot.client_id,
                    snapshot.keyword,
                    snapshot.position,
                    snapshot.video_id,
                    snapshot.video_title,
                    snapshot.channel_id,
                    snapshot.channel_title,
                    snapshot.published_at,
                    snapshot.view_count,
                    snapshot.like_count,
                    snapshot.comment_count,
                    snapshot.subscriber_count,
                    snapshot.engagement_rate,
                    snapshot.duration_seconds,
                    snapshot.tags,
                    snapshot.serp_engine,
                    snapshot.fetched_at,
                    snapshot.video_url
                )
            except Exception as e:
                logger.error(f"Error storing video snapshot: {e}")
    
    async def calculate_video_metrics(self, client_id: str, days: int = 30) -> VideoMetrics:
        """Calculate aggregate video metrics"""
        
        cutoff_date = date.today() - timedelta(days=days)
        
        result = await self.db.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT video_id) as total_videos,
                SUM(view_count) as total_views,
                SUM(like_count) as total_likes,
                SUM(comment_count) as total_comments,
                AVG(engagement_rate) as avg_engagement,
                AVG(view_count) as avg_view_count
            FROM video_snapshots
            WHERE client_id = $1 
            AND snapshot_date >= $2
            AND snapshot_date = (
                SELECT MAX(snapshot_date) 
                FROM video_snapshots vs2 
                WHERE vs2.video_id = video_snapshots.video_id
                AND vs2.client_id = $1
            )
            """,
            client_id, cutoff_date
        )
        
        # Get top video
        top_video_row = await self.db.fetchrow(
            """
            SELECT video_id, video_title, view_count, video_url
            FROM video_snapshots
            WHERE client_id = $1 
            AND snapshot_date >= $2
            ORDER BY view_count DESC
            LIMIT 1
            """,
            client_id, cutoff_date
        )
        
        top_video = None
        if top_video_row:
            top_video = {
                "video_id": top_video_row['video_id'],
                "title": top_video_row['video_title'],
                "views": top_video_row['view_count'],
                "url": top_video_row['video_url']
            }
        
        # Get channel distribution
        channel_dist = await self.db.fetch(
            """
            SELECT 
                channel_title,
                COUNT(DISTINCT video_id) as video_count,
                SUM(view_count) as total_views
            FROM video_snapshots
            WHERE client_id = $1 
            AND snapshot_date >= $2
            AND snapshot_date = (
                SELECT MAX(snapshot_date) 
                FROM video_snapshots vs2 
                WHERE vs2.video_id = video_snapshots.video_id
                AND vs2.client_id = $1
            )
            GROUP BY channel_title
            ORDER BY total_views DESC
            LIMIT 10
            """,
            client_id, cutoff_date
        )
        
        return VideoMetrics(
            total_videos=result['total_videos'] or 0,
            total_views=result['total_views'] or 0,
            total_likes=result['total_likes'] or 0,
            total_comments=result['total_comments'] or 0,
            avg_engagement=round(result['avg_engagement'] or 0, 2),
            avg_view_count=round(result['avg_view_count'] or 0, 0),
            top_video=top_video,
            channel_distribution=[dict(row) for row in channel_dist]
        )
    
    async def get_top_videos(self, client_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing videos"""
        
        rows = await self.db.fetch(
            """
            SELECT 
                video_id,
                video_title,
                channel_title,
                view_count,
                like_count,
                comment_count,
                engagement_rate,
                video_url
            FROM video_snapshots
            WHERE client_id = $1
            AND snapshot_date = (
                SELECT MAX(snapshot_date) 
                FROM video_snapshots 
                WHERE client_id = $1
            )
            ORDER BY view_count DESC
            LIMIT $2
            """,
            client_id, limit
        )
        
        return [dict(row) for row in rows]
    
    async def get_channel_performance(self, client_id: str) -> List[Dict[str, Any]]:
        """Get channel performance metrics"""
        
        rows = await self.db.fetch(
            """
            SELECT 
                channel_id,
                channel_title,
                COUNT(DISTINCT video_id) as video_count,
                SUM(view_count) as total_views,
                AVG(view_count) as avg_views,
                SUM(like_count + comment_count) as total_engagement,
                AVG(engagement_rate) as avg_engagement_rate,
                MAX(subscriber_count) as subscribers
            FROM video_snapshots
            WHERE client_id = $1
            AND snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY channel_id, channel_title
            ORDER BY total_views DESC
            """,
            client_id
        )
        
        return [dict(row) for row in rows] 