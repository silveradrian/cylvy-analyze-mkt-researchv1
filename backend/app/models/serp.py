"""
SERP-related Pydantic models
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class SERPType(str, Enum):
    """Types of SERP results"""
    ORGANIC = "organic"
    NEWS = "news"
    VIDEO = "video"
    ADS = "ads"
    FEATURED_SNIPPET = "featured_snippet"
    KNOWLEDGE_PANEL = "knowledge_panel"
    LOCAL_PACK = "local_pack"
    RELATED_SEARCHES = "related_searches"


class KeywordBase(BaseModel):
    """Base model for keywords"""
    keyword: str = Field(..., min_length=1, max_length=255)
    client_id: str = Field(..., min_length=1, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = Field(default_factory=list)
    is_active: bool = True


class KeywordCreate(KeywordBase):
    """Model for creating keywords"""
    pass


class KeywordUpdate(BaseModel):
    """Model for updating keywords"""
    keyword: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class Keyword(KeywordBase):
    """Complete keyword model"""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SERPResultBase(BaseModel):
    """Base model for SERP results"""
    keyword_id: str
    position: int
    title: str
    url: str
    domain: str
    snippet: Optional[str] = None
    serp_type: SERPType = SERPType.ORGANIC


class SERPResult(SERPResultBase):
    """Complete SERP result model"""
    id: str
    created_at: datetime
    result_type: Optional[str] = None
    search_metadata: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class SERPCollectionRequest(BaseModel):
    """Request model for SERP collection"""
    client_id: str = Field(..., min_length=1, max_length=50)
    keywords: List[str] = Field(..., min_length=1, max_length=100)
    location: str = Field("United States", max_length=100)
    device: str = Field("desktop", pattern="^(desktop|mobile)$")
    num_results: int = Field(100, ge=10, le=100)
    serp_type: str = Field("organic", pattern="^(organic|ads|all)$")
    time_period: Optional[str] = Field(None, pattern="^(last_hour|last_day|last_week|last_month|last_year|custom)$")
    
    @field_validator("keywords")
    def validate_keywords(cls, keywords):
        # Remove duplicates and empty strings
        cleaned = list(set(k.strip() for k in keywords if k.strip()))
        if not cleaned:
            raise ValueError("At least one valid keyword is required")
        return cleaned


class SERPCollectionResponse(BaseModel):
    """Response model for SERP collection"""
    job_id: str
    message: str
    keywords_count: int
    estimated_credits: int


class SERPQuotaResponse(BaseModel):
    """Response model for SERP quota check"""
    used: int
    limit: int
    remaining: int
    percentage_used: float
    overusage_limit: int
    in_overusage: bool
    reset_date: Optional[datetime] = None


class SERPSearchResponse(BaseModel):
    """Response model for SERP search results"""
    total: int
    results: List[SERPResult]
    filters_applied: Dict[str, Any]


# Additional models for analytics

class KeywordPerformance(BaseModel):
    """Model for keyword performance metrics"""
    keyword_id: str
    keyword: str
    avg_position: float
    position_changes: List[Dict[str, Any]]
    top_competitors: List[str]
    visibility_score: float
    
    model_config = {"from_attributes": True}


class CompetitorSERPAnalysis(BaseModel):
    """Model for competitor SERP analysis"""
    domain: str
    total_keywords: int
    avg_position: float
    top_ranking_keywords: List[Dict[str, Any]]
    estimated_traffic: int
    
    model_config = {"from_attributes": True} 