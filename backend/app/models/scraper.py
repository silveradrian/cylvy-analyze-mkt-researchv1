from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ScraperEngine(str, Enum):
    """Available scraper engines"""
    DIRECT = "direct"
    SCRAPINGBEE = "scrapingbee"
    CACHE = "cache"


class ScrapeRequest(BaseModel):
    """Request model for scraping URLs"""
    urls: List[HttpUrl] = Field(..., description="URLs to scrape", max_items=100)
    client_id: str = Field(..., description="Client ID")
    use_javascript: bool = Field(False, description="Force JavaScript rendering")
    force_refresh: bool = Field(False, description="Skip cache and force fresh scrape")
    max_concurrent: int = Field(5, description="Maximum concurrent requests", ge=1, le=20)
    
    @validator('urls')
    def validate_urls(cls, v):
        if not v:
            raise ValueError("At least one URL is required")
        return v


class ScrapedContent(BaseModel):
    """Model for scraped content"""
    id: Optional[str] = None
    url: str
    final_url: Optional[str] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    content: str
    word_count: int
    content_type: str
    engine: ScraperEngine
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    status_code: Optional[int] = None
    scraped_at: datetime
    cached: bool = False
    credits_used: Optional[str] = None


class BatchScrapeResult(BaseModel):
    """Result of batch scraping operation"""
    job_id: str
    client_id: str
    total_urls: int
    successful: int
    failed: int
    results: List[ScrapedContent]
    started_at: datetime
    completed_at: datetime
    duration_seconds: float


class ScrapeJob(BaseModel):
    """Model for scraping job tracking"""
    job_id: str
    client_id: str
    status: str
    total_urls: int
    processed_urls: int = 0
    successful_urls: int = 0
    failed_urls: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class DocumentParseResult(BaseModel):
    """Result of document parsing"""
    url: Optional[str] = None
    file_path: Optional[str] = None
    document_type: str
    content: str
    word_count: int
    page_count: Optional[int] = None
    paragraph_count: Optional[int] = None
    table_count: Optional[int] = None
    error: Optional[str] = None
    parsed_at: datetime = Field(default_factory=datetime.utcnow)


class ScrapeStatsResponse(BaseModel):
    """Response model for scraping statistics"""
    client_id: str
    total_scraped: int
    total_cached: int
    total_failed: int
    engines_used: Dict[str, int]
    date_range: Dict[str, datetime]
    top_domains: List[Dict[str, Any]]
    average_word_count: float
    total_credits_used: int 