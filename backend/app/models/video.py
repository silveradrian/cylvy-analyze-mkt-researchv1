"""
Video enrichment models
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class VideoEnrichRequest(BaseModel):
    """Request to enrich YouTube videos"""
    client_id: str
    keyword: Optional[str] = None
    video_urls: List[str]
    
    
class BatchVideoEnrichRequest(BaseModel):
    """Batch video enrichment request"""
    client_id: str
    force_refresh: bool = Field(default=False, description="Force refresh even if cached")


class YouTubeVideoStats(BaseModel):
    """YouTube video statistics"""
    video_id: str
    title: str
    description: Optional[str]
    channel_id: str
    channel_title: str
    channel_description: Optional[str] = None
    channel_custom_url: Optional[str] = None
    published_at: Optional[datetime]
    duration_seconds: int = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    tags: List[str] = []
    category_id: Optional[str]
    thumbnail_url: Optional[str]
    engagement_rate: float = Field(default=0.0, description="(likes + comments) / views * 100")
    video_url: str


class YouTubeChannelStats(BaseModel):
    """YouTube channel statistics"""
    channel_id: str
    channel_title: str
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    country: Optional[str]
    custom_url: Optional[str]
    description: Optional[str]
    published_at: Optional[datetime]


class VideoSnapshot(BaseModel):
    """Snapshot of video metrics at a point in time"""
    id: Optional[UUID] = None
    snapshot_date: datetime
    client_id: str
    keyword: Optional[str]
    position: int
    video_id: str
    video_title: str
    channel_id: str
    channel_title: str
    published_at: Optional[datetime]
    view_count: int
    like_count: int
    comment_count: int
    subscriber_count: int
    engagement_rate: float
    duration_seconds: int
    tags: List[str] = []
    serp_engine: Optional[str] = "google"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    video_url: str


class VideoMetrics(BaseModel):
    """Aggregated video metrics"""
    total_videos: int
    total_views: int
    total_likes: int
    total_comments: int
    avg_engagement: float
    avg_view_count: float
    top_video: Optional[Dict[str, Any]]
    channel_distribution: List[Dict[str, Any]]


class ChannelPerformance(BaseModel):
    """Channel performance metrics"""
    channel_id: str
    channel_title: str
    video_count: int
    total_views: int
    avg_views: float
    total_engagement: int
    avg_engagement_rate: float
    subscriber_count: int
    top_videos: List[Dict[str, Any]]


class VideoTrend(BaseModel):
    """Video performance trend over time"""
    video_id: str
    video_title: str
    dates: List[datetime]
    view_counts: List[int]
    like_counts: List[int]
    comment_counts: List[int]
    growth_rate: float
    trend_direction: str  # growing, stable, declining


class QuotaUsage(BaseModel):
    """YouTube API quota usage tracking"""
    date: datetime
    units_used: int
    units_limit: int
    operations: Dict[str, int]  # operation type -> count
    remaining: int
    reset_time: datetime


class VideoEnrichmentResult(BaseModel):
    """Result of video enrichment operation"""
    client_id: str
    enriched_count: int
    cached_count: int
    failed_count: int
    quota_used: int
    snapshots: List[VideoSnapshot]
    errors: List[Dict[str, str]] = []
    processing_time: float 