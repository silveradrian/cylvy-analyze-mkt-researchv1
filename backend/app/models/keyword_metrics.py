"""Data models for Keyword Metrics Service"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class JobStatus(str, Enum):
    """Status of a keyword metrics job"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class KeywordIdea(BaseModel):
    """Keyword suggestion from Google Ads API"""
    keyword: str
    avg_monthly_searches: Optional[int] = None
    competition: Optional[str] = None
    competition_index: Optional[int] = None
    low_top_of_page_bid_micros: Optional[int] = None
    high_top_of_page_bid_micros: Optional[int] = None


class KeywordMetricsRequest(BaseModel):
    """Request to process keyword metrics"""
    client_id: str = Field(..., description="Client identifier")
    project_id: Optional[str] = Field(None, description="Project identifier")
    keywords: List[str] = Field(..., description="Keywords to process")
    language: str = Field(default="en", description="Language code")
    
    # CHANGED: Support multiple locations
    locations: List[str] = Field(
        default_factory=lambda: ["2840"], 
        description="List of geo-target codes to process"
    )
    
    # NEW: Keyword category assignment
    keyword_category: Optional[str] = Field(
        None, 
        description="Category to assign to these keywords"
    )
    
    include_ideas: bool = Field(default=False, description="Include related keyword ideas")
    ideas_limit: Optional[int] = Field(None, description="Override IDEAS_LIMIT for this request")
    min_search_volume: Optional[int] = Field(None, description="Minimum search volume filter")
    force_refresh: bool = Field(default=False, description="Force refresh cached data")
    
    @field_validator('keywords')
    def validate_keywords(cls, v):
        """Validate keywords list"""
        if not v:
            raise ValueError("Keywords list cannot be empty")
        # Clean and deduplicate
        cleaned = []
        seen = set()
        for kw in v:
            clean_kw = kw.strip().lower()
            if clean_kw and clean_kw not in seen:
                cleaned.append(clean_kw)
                seen.add(clean_kw)
        if not cleaned:
            raise ValueError("No valid keywords provided")
        return cleaned
    
    @field_validator('locations')
    def validate_locations(cls, v):
        """Validate locations list"""
        if not v:
            raise ValueError("Locations list cannot be empty")
        # Ensure all location codes are strings
        return [str(loc).strip() for loc in v if str(loc).strip()]


class KeywordMetricsJob(BaseModel):
    """Job tracking for async processing"""
    job_id: str
    client_id: str
    project_id: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    total_keywords: int
    total_locations: int = 1
    processed_keywords: int = 0
    metrics_found: int = 0
    ideas_found: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # NEW: Track location progress
    location_progress: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description="Progress per location"
    )
    
    def update_progress(self, location: str, keywords_processed: int, metrics_found: int):
        """Update progress for a specific location"""
        if location not in self.location_progress:
            self.location_progress[location] = {
                "processed": 0,
                "found": 0
            }
        self.location_progress[location]["processed"] = keywords_processed
        self.location_progress[location]["found"] = metrics_found
        
        # Update totals
        self.processed_keywords = sum(
            loc["processed"] for loc in self.location_progress.values()
        )
        self.metrics_found = sum(
            loc["found"] for loc in self.location_progress.values()
        )
        self.updated_at = datetime.utcnow()


class KeywordMetrics(BaseModel):
    """Keyword metrics data with location support"""
    keyword: str
    location: str = Field(description="Geo-target code")
    location_name: Optional[str] = Field(None, description="Human-readable location name")
    keyword_category: Optional[str] = Field(None, description="Assigned category")
    avg_monthly_searches: Optional[int] = None
    competition: Optional[str] = None
    competition_index: Optional[int] = None
    low_top_of_page_bid_micros: Optional[int] = None
    high_top_of_page_bid_micros: Optional[int] = None
    cpc_low: Optional[float] = None
    cpc_high: Optional[float] = None
    source: str = "google_ads"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def has_data(self) -> bool:
        """Check if metrics contain actual data"""
        return self.avg_monthly_searches is not None and self.avg_monthly_searches > 0


class KeywordMetricsEvent(BaseModel):
    """Event published when metrics are ready"""
    client_id: str
    project_id: Optional[str] = None
    job_id: str
    keywords_processed: int
    metrics_found: int
    ideas_found: int
    locations_processed: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class KeywordMetricsResponse(BaseModel):
    """Response containing keyword metrics"""
    job_id: str
    status: JobStatus
    metrics: List[KeywordMetrics]
    ideas: List[KeywordIdea] = []
    total_keywords: int
    metrics_found: int
    
    # NEW: Location summary
    location_summary: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description="Summary per location"
    )


class KeywordSource(str, Enum):
    """Keyword source values"""
    SEED = "seed"
    IDEA = "idea"


class KeywordMetric(BaseModel):
    """Keyword with metrics"""
    keyword: str
    search_volume: Optional[int] = None
    cpc_micro: Optional[int] = None  # CPC in micros (multiply by 1e-6)
    competition: Optional[Decimal] = None  # 0.0 to 1.0
    source: KeywordSource = KeywordSource.SEED
    
    def get_cpc(self) -> Optional[float]:
        """Get CPC in currency units"""
        if self.cpc_micro is None:
            return None
        return self.cpc_micro / 1_000_000
    
    class Config:
        use_enum_values = True


class KeywordJob(BaseModel):
    """Job tracking model"""
    job_id: str
    client_id: str
    project_id: Optional[str] = None
    status: JobStatus
    total_keywords: int
    processed_keywords: int
    ideas_generated: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        use_enum_values = True


class KeywordMetricsCompletedEvent(BaseModel):
    """Event for keyword.metrics.completed.v1"""
    client_id: str
    project_id: Optional[str] = None
    row_count: int
    ideas_generated: int = 0
    bq_table: str = "keyword_metrics"
    job_id: str
    status: str


class GoogleAdsConfig(BaseModel):
    """Google Ads API configuration"""
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    login_customer_id: str
    customer_id: str


class ClientSettings(BaseModel):
    """Client settings from client-context-service"""
    client_id: str
    name: str
    domains: List[str] = []
    competitor_domains: List[str] = []
    seed_keywords: List[str] = []


class KeywordSearchResponse(BaseModel):
    """Response for keyword search endpoint"""
    keywords: List[Dict[str, Any]]
    total: int
    page: int
    limit: int


class ClientStats(BaseModel):
    """Client keyword statistics"""
    client_id: str
    total_keywords: int
    avg_search_volume: Optional[float]
    avg_cpc: Optional[float]
    last_updated: Optional[datetime] 