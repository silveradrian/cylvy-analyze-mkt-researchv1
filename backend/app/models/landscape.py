"""
Digital Landscape models for market segmentation and DSI calculations
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from uuid import UUID
from enum import Enum


class EntityType(str, Enum):
    """Type of entity for DSI metrics"""
    COMPANY = "company"
    PAGE = "page"


class DigitalLandscape(BaseModel):
    """Digital landscape definition"""
    id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    # Computed fields
    keyword_count: Optional[int] = 0


class CreateLandscapeRequest(BaseModel):
    """Request to create a new digital landscape"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class LandscapeKeywordAssignment(BaseModel):
    """Keyword assignment to landscape"""
    landscape_id: UUID
    keyword_ids: List[UUID]


class LandscapeDSIMetrics(BaseModel):
    """Comprehensive DSI metrics for landscape entities"""
    id: Optional[UUID] = None
    landscape_id: UUID
    calculation_date: date
    entity_type: EntityType
    
    # Entity identification
    entity_id: Optional[UUID]
    entity_name: str
    entity_domain: str
    entity_url: Optional[str] = None
    
    # Core DSI Metrics
    unique_keywords: int
    unique_pages: int
    keyword_coverage: float  # 0.0-1.0
    estimated_traffic: int
    traffic_share: float  # 0.0-1.0
    
    # DSI Score Components
    persona_alignment: Optional[float] = 0.0
    funnel_value: Optional[float] = 0.0
    dsi_score: float
    
    # Rankings
    rank_in_landscape: int
    total_entities_in_landscape: int
    market_position: str = "NICHE"  # LEADER, CHALLENGER, COMPETITOR, NICHE
    
    # Metadata
    calculation_period_days: int = 30
    created_at: Optional[datetime] = None


class LandscapeMetricsRequest(BaseModel):
    """Request for landscape metrics calculation"""
    landscape_id: UUID
    entity_type: EntityType = EntityType.COMPANY
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = Field(default=50, ge=1, le=200)


class LandscapeCalculationResult(BaseModel):
    """Result of landscape DSI calculation"""
    landscape_id: UUID
    calculation_date: date
    total_companies: int
    total_keywords: int
    companies: List[Dict[str, Any]]
    calculation_duration_seconds: Optional[float] = None


class LandscapeSummary(BaseModel):
    """Summary statistics for a landscape"""
    landscape_id: UUID
    calculation_date: date
    total_companies: int
    total_keywords: int
    total_pages: int
    total_traffic: int
    avg_dsi_score: float
    top_dsi_score: float


class LandscapeHistoricalTrend(BaseModel):
    """Historical trend data for landscape metrics"""
    calculation_date: date
    entity_name: str
    entity_domain: str
    metric_value: float
    rank_in_landscape: int

