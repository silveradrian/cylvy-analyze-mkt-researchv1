"""
Content Analysis Models
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from enum import Enum


class ContentClassification(str, Enum):
    """B2B Content Classification Categories"""
    ATTRACT = "ATTRACT"  # Education & Discovery
    LEARN = "LEARN"  # Buyers - Brand-specific content
    CONVERT_TRY = "CONVERT/TRY"  # Buyer Enablement - High value engagement
    BUY = "BUY"  # Buyer Enablement - Continued
    OTHER = "OTHER"  # Content that doesn't fit other categories


class SourceType(str, Enum):
    """Content source classification"""
    OWNED = "owned"
    COMPETITOR = "competitor"
    PREMIUM_PUBLISHER = "premium_publisher"
    TECHNOLOGY = "technology"
    FINANCE = "finance"
    PROFESSIONAL_BODY = "professional_body"
    SOCIAL_MEDIA = "social_media"
    EDUCATION = "education"
    NON_PROFIT = "non_profit"
    GOVERNMENT = "government"
    OTHER = "other"


class Sentiment(str, Enum):
    """Content sentiment"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Persona(BaseModel):
    """Persona configuration"""
    name: str = Field(..., description="Persona name")
    description: str = Field(..., description="Persona description")
    title: Optional[str] = Field(None, description="Job title/role")
    goals: List[str] = Field(default_factory=list, description="Primary goals")
    pain_points: List[str] = Field(default_factory=list, description="Key pain points")
    decision_criteria: List[str] = Field(default_factory=list, description="Decision criteria")
    content_preferences: List[str] = Field(default_factory=list, description="Preferred content types")


class JTBDPhase(BaseModel):
    """Jobs to be Done phase configuration"""
    name: str = Field(..., description="Phase name")
    description: str = Field(..., description="Phase description")
    key_questions: List[str] = Field(default_factory=list, description="Questions buyers ask in this phase")
    content_types: List[str] = Field(default_factory=list, description="Effective content types for this phase")
    buyer_mindset: str = Field("", description="Buyer's mindset in this phase")


class PageType(BaseModel):
    """B2B Page Type definition"""
    id: str = Field(..., description="Unique page type identifier")
    name: str = Field(..., description="Page type name")
    category: str = Field(..., description="Page category grouping")
    description: str = Field(..., description="Page type description")
    indicators: List[str] = Field(default_factory=list, description="Key indicators of this page type")
    buyer_journey_stage: str = Field(..., description="Primary buyer journey stage alignment")


class Mention(BaseModel):
    """Entity mention in content"""
    entity: str = Field(..., description="Entity name/domain mentioned")
    count: int = Field(..., description="Number of mentions")
    snippets: List[str] = Field(default_factory=list, description="Context snippets")
    sentiment: Sentiment = Field(Sentiment.NEUTRAL, description="Sentiment of mentions")
    sentiment_reasoning: Optional[str] = Field(None, description="AI reasoning for sentiment")
    positions: List[int] = Field(default_factory=list, description="Character positions")
    context_analysis: Optional[str] = Field(None, description="AI analysis of mention context")


class ContentAnalysisRequest(BaseModel):
    """Request to analyze content"""
    client_id: str = Field(..., description="Client ID")
    url: str = Field(..., description="URL to analyze")
    content: Optional[str] = Field(None, description="Content if already scraped")
    force_reanalyze: bool = Field(False, description="Force re-analysis even if cached")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="Override default config")


class BatchAnalysisRequest(BaseModel):
    """Request to analyze multiple URLs"""
    client_id: str = Field(..., description="Client ID")
    urls: List[str] = Field(..., description="URLs to analyze", min_length=1, max_length=100)
    force_reanalyze: bool = Field(False, description="Force re-analysis even if cached")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="Override default config")
    
    @field_validator('urls')
    @classmethod
    def unique_urls(cls, v: List[str]) -> List[str]:
        """Ensure URLs are unique"""
        return list(set(v))


class AnalysisConfig(BaseModel):
    """Analysis configuration for a client"""
    personas: List[Persona] = Field(default_factory=list, description="Target personas")
    jtbd_phases: List[JTBDPhase] = Field(default_factory=list, description="Jobs to be Done phases")
    page_types: List[PageType] = Field(default_factory=list, description="B2B page type definitions")
    competitor_domains: List[str] = Field(default_factory=list, description="Competitor domains to track")
    custom_dimensions: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Custom analysis dimensions"
    )
    content_categories: Dict[str, str] = Field(
        default_factory=lambda: {
            "ATTRACT": "Education & Discovery - Unbranded foundational knowledge",
            "LEARN": "Buyers - Brand-specific content & thought leadership",
            "CONVERT/TRY": "Buyer Enablement - High value customer engagement",
            "BUY": "Buyer Enablement - Continued"
        },
        description="Content category definitions"
    )
    max_content_length: int = Field(8000, description="Max content length for analysis")
    temperature: float = Field(0.3, description="LLM temperature", ge=0.0, le=1.0)
    enable_mention_extraction: bool = Field(True, description="Extract entity mentions")
    enable_sentiment_analysis: bool = Field(True, description="Analyze sentiment")
    custom_prompt_instructions: Optional[str] = Field(None, description="Additional prompt instructions")


class ContentAnalysisResult(BaseModel):
    """Content analysis result"""
    id: UUID = Field(..., description="Analysis ID")
    client_id: str = Field(..., description="Client ID")
    content_asset_id: UUID = Field(..., description="Content asset ID")
    url: str = Field(..., description="Analyzed URL")
    
    # Core analysis results
    summary: str = Field(..., description="Content summary")
    content_classification: ContentClassification = Field(..., description="Content category")
    primary_persona: str = Field(..., description="Primary target persona")
    persona_alignment_scores: Dict[str, float] = Field(..., description="Persona alignment scores (0-1)")
    jtbd_phase: str = Field(..., description="Primary JTBD phase")
    jtbd_alignment_score: float = Field(..., description="JTBD alignment score (0-1)")
    
    # Additional insights
    custom_dimensions: Dict[str, Any] = Field(default_factory=dict, description="Custom dimension values")
    key_topics: List[str] = Field(default_factory=list, description="Key topics extracted")
    sentiment: Sentiment = Field(..., description="Overall sentiment")
    
    # Confidence scores (0-10) for each dimension
    confidence_scores: Optional[Dict[str, Any]] = Field(
        None, 
        description="Confidence scores (0-10) for analysis dimensions"
    )
    
    # Mentions
    brand_mentions: List[Mention] = Field(default_factory=list, description="Brand mentions")
    competitor_mentions: List[Mention] = Field(default_factory=list, description="Competitor mentions")
    
    # Source classification
    source_type: Optional[SourceType] = Field(None, description="Content source type")
    source_company_id: Optional[UUID] = Field(None, description="Source company profile ID")
    source_company_name: Optional[str] = Field(None, description="Source company name")
    source_company_industry: Optional[str] = Field(None, description="Source company industry")
    source_company_description: Optional[str] = Field(None, description="Source company description")
    source_identification_reasoning: Optional[str] = Field(None, description="AI reasoning for source identification")
    
    # Metadata
    analyzed_at: datetime = Field(..., description="Analysis timestamp")
    analysis_version: str = Field("1.0", description="Analysis version")
    model_used: str = Field("gpt-4o-mini", description="LLM model used")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class AnalysisJob(BaseModel):
    """Batch analysis job status"""
    id: UUID = Field(..., description="Job ID")
    client_id: str = Field(..., description="Client ID")
    status: str = Field(..., description="Job status")
    total_urls: int = Field(..., description="Total URLs to process")
    processed: int = Field(0, description="URLs processed")
    successful: int = Field(0, description="Successful analyses")
    failed: int = Field(0, description="Failed analyses")
    error_details: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    created_at: datetime = Field(..., description="Job creation time")
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage"""
        if self.total_urls == 0:
            return 0.0
        return (self.processed / self.total_urls) * 100


class ClientAnalysisConfig(BaseModel):
    """Client-specific analysis configuration"""
    id: UUID = Field(..., description="Config ID")
    client_id: str = Field(..., description="Client ID")
    config: AnalysisConfig = Field(..., description="Analysis configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AnalysisStats(BaseModel):
    """Analysis statistics for a client"""
    client_id: str = Field(..., description="Client ID")
    total_analyzed: int = Field(..., description="Total content analyzed")
    by_classification: Dict[str, int] = Field(..., description="Count by classification")
    by_source_type: Dict[str, int] = Field(..., description="Count by source type")
    by_sentiment: Dict[str, int] = Field(..., description="Count by sentiment")
    avg_jtbd_score: float = Field(..., description="Average JTBD alignment score")
    top_personas: List[Dict[str, Any]] = Field(..., description="Top aligned personas")
    recent_analyses: List[ContentAnalysisResult] = Field(..., description="Recent analysis results")