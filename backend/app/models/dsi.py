"""
DSI (Digital Share of Intelligence) calculation models
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class DSIType(str, Enum):
    """Types of DSI calculations"""
    ORGANIC = "organic"
    NEWS = "news"
    YOUTUBE = "youtube"


class MarketPosition(str, Enum):
    """Market position based on DSI score"""
    LEADER = "leader"          # DSI >= 30
    CHALLENGER = "challenger"  # DSI >= 15
    COMPETITOR = "competitor"  # DSI >= 5
    NICHE = "niche"           # DSI < 5


class OrganicDSIRequest(BaseModel):
    """Request for organic DSI calculation"""
    client_id: str
    lookback_days: int = Field(default=30, ge=1, le=90)
    include_page_level: bool = Field(default=True)
    
    
class NewsDSIRequest(BaseModel):
    """Request for news DSI calculation"""
    client_id: str
    lookback_days: int = Field(default=30, ge=1, le=90)
    include_article_level: bool = Field(default=True)
    
    
class YouTubeDSIRequest(BaseModel):
    """Request for YouTube DSI calculation"""
    client_id: str
    lookback_days: int = Field(default=30, ge=1, le=90)
    include_channel_metrics: bool = Field(default=True)


class DSICalculationRequest(BaseModel):
    """Unified DSI calculation request"""
    client_id: str
    dsi_types: List[DSIType] = Field(default=[DSIType.ORGANIC])
    lookback_days: int = Field(default=30, ge=1, le=90)
    include_detailed_metrics: bool = Field(default=True)


class PageDSIMetrics(BaseModel):
    """Page-level DSI metrics for organic results"""
    page_id: UUID
    url: str
    title: str
    content_type: Optional[str]
    keyword_count: int
    estimated_traffic: float
    keyword_coverage: float  # Keywords for this page / total keywords
    traffic_share: float     # Traffic to page / total traffic
    relevance_score: float   # Average persona/JTBD alignment (0-1)
    funnel_value: float   # Based on content classification (BUY=1.0, CONVERT=0.8, etc.)
    dsi_score: float        # Final DSI score
    rank_in_company: int
    rank_in_market: int


class CompanyDSIMetrics(BaseModel):
    """Company-level DSI metrics"""
    company_id: UUID
    domain: str
    company_name: str
    total_keywords: int
    total_traffic: float
    total_pages: int
    keyword_coverage: float  # Company keywords / market keywords
    traffic_share: float     # Company traffic / market traffic
    avg_relevance: float     # Average relevance across pages
    avg_funnel_value: float  # Score based on content classification (BUY=1.0, CONVERT=0.8, etc.)
    dsi_score: float        # Final DSI score
    market_position: MarketPosition
    rank_in_market: int
    total_companies_in_market: int
    page_metrics: Optional[List[PageDSIMetrics]] = None


class PublisherDSIMetrics(BaseModel):
    """Publisher-level DSI metrics for news"""
    publisher_domain: str
    publisher_name: str
    total_articles: int
    total_serp_appearances: int
    keyword_coverage: float      # Keywords covered / total keywords
    avg_persona_relevance: float # Average relevance score
    dsi_score: float
    rank_in_market: int


class ArticleDSIMetrics(BaseModel):
    """Article-level DSI metrics for news"""
    article_id: UUID
    url: str
    title: str
    publisher: str
    published_date: Optional[datetime]
    serp_appearances: int
    keyword_coverage: float
    persona_relevance: float
    sentiment: Optional[str]
    dsi_score: float
    rank_in_publisher: int


class YouTubeChannelDSIMetrics(BaseModel):
    """YouTube channel-level DSI metrics"""
    channel_id: str
    channel_name: str
    total_videos: int
    total_views: int
    total_likes: int
    total_comments: int
    subscriber_count: Optional[int]
    serp_appearances: int
    keyword_coverage: float
    engagement_rate: float  # (likes + comments) / views
    dsi_score: float
    rank_in_market: int


class YouTubeVideoDSIMetrics(BaseModel):
    """YouTube video-level DSI metrics"""
    video_id: str
    url: str
    title: str
    channel_name: str
    published_date: Optional[datetime]
    view_count: int
    like_count: int
    comment_count: int
    duration_seconds: Optional[int]
    serp_appearances: int
    keyword_coverage: float
    engagement_rate: float
    watch_time_estimate: Optional[float]  # Estimated based on views and duration
    dsi_score: float
    rank_in_channel: int


class MarketTotals(BaseModel):
    """Market-wide totals for DSI calculations"""
    total_keywords: int
    total_traffic: float
    total_companies: int
    total_pages: int
    avg_relevance: float
    calculation_date: datetime


class DSICalculationResult(BaseModel):
    """Complete DSI calculation result"""
    job_id: UUID
    client_id: str
    calculation_type: DSIType
    lookback_days: int
    period_start: datetime
    period_end: datetime
    calculated_at: datetime
    market_totals: MarketTotals
    
    # Results based on type
    organic_results: Optional[List[CompanyDSIMetrics]] = None
    news_results: Optional[List[PublisherDSIMetrics]] = None
    youtube_results: Optional[List[YouTubeChannelDSIMetrics]] = None
    
    # Summary statistics
    client_total_dsi: float
    client_market_share: float
    top_performers: List[Dict[str, Any]]
    insights: List[str]


class DSIHistoricalTrend(BaseModel):
    """Historical DSI trend data"""
    entity_id: str  # Company domain, publisher, or channel
    entity_type: DSIType
    period: str  # YYYY-MM
    dsi_score: float
    market_position: MarketPosition
    rank: int
    change_from_previous: Optional[float]


class DSIBatchResult(BaseModel):
    """Result of batch DSI calculations"""
    job_id: UUID
    started_at: datetime
    completed_at: Optional[datetime]
    status: str  # pending, processing, completed, failed
    total_clients: int
    processed_clients: int
    successful: int
    failed: int
    error_details: Optional[List[Dict[str, str]]] = None
    results: Optional[List[DSICalculationResult]] = None 