"""Keyword model for comprehensive SEO analysis"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from uuid import UUID


class KeywordBase(BaseModel):
    """Base keyword model with all SEO fields"""
    keyword: str = Field(..., description="The keyword phrase")
    country: Optional[str] = Field(None, description="Target country for the keyword")
    category: Optional[str] = Field(None, description="Keyword category")
    jtbd_stage: Optional[str] = Field(None, description="Jobs-to-be-done stage")
    avg_monthly_searches: Optional[int] = Field(None, description="Average monthly search volume")
    competition: Optional[int] = Field(None, description="Competition level as numeric value")
    competition_index: Optional[float] = Field(None, ge=0, le=100, description="Competition index 0-100")
    low_top_page_bid: Optional[float] = Field(None, ge=0, description="Low range for top page bid")
    high_top_page_bid: Optional[float] = Field(None, ge=0, description="High range for top page bid")
    client_score: Optional[float] = Field(None, ge=0, le=100, description="Client relevance score")
    client_rationale: Optional[str] = Field(None, description="Reasoning for client score")
    persona_score: Optional[float] = Field(None, ge=0, le=100, description="Persona relevance score")
    persona_rationale: Optional[str] = Field(None, description="Reasoning for persona score")
    seo_score: Optional[float] = Field(None, ge=0, le=100, description="SEO opportunity score")
    seo_rationale: Optional[str] = Field(None, description="Reasoning for SEO score")
    composite_score: Optional[int] = Field(None, description="Overall composite score")
    is_brand: bool = Field(False, description="Whether this is a brand keyword")
    is_active: bool = Field(True, description="Whether the keyword is active")


class KeywordCreate(KeywordBase):
    """Model for creating a new keyword"""
    client_id: str = Field(..., description="Client ID this keyword belongs to")


class KeywordUpdate(BaseModel):
    """Model for updating a keyword - all fields optional"""
    keyword: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    jtbd_stage: Optional[str] = None
    avg_monthly_searches: Optional[int] = None
    competition: Optional[int] = None
    competition_index: Optional[float] = Field(None, ge=0, le=100)
    low_top_page_bid: Optional[float] = Field(None, ge=0)
    high_top_page_bid: Optional[float] = Field(None, ge=0)
    client_score: Optional[float] = Field(None, ge=0, le=100)
    client_rationale: Optional[str] = None
    persona_score: Optional[float] = Field(None, ge=0, le=100)
    persona_rationale: Optional[str] = None
    seo_score: Optional[float] = Field(None, ge=0, le=100)
    seo_rationale: Optional[str] = None
    composite_score: Optional[int] = None
    is_brand: Optional[bool] = None
    is_active: Optional[bool] = None


class Keyword(KeywordBase):
    """Complete keyword model with database fields"""
    id: UUID
    client_id: Optional[str] = Field(default="default")  # Optional for single-tenant
    created_at: datetime
    updated_at: datetime
    countries: Optional[list[str]] = Field(default_factory=list, description="Countries where keyword is tracked")

    class Config:
        from_attributes = True


class KeywordWithScores(Keyword):
    """Keyword model with calculated metrics"""
    has_serp_data: bool = Field(False, description="Whether SERP data has been collected")
    has_content_analysis: bool = Field(False, description="Whether content analysis has been done")
    opportunity_score: Optional[float] = Field(None, description="Calculated opportunity score")
    
    @property
    def competition_level(self) -> str:
        """Convert numeric competition to text level"""
        if self.competition is None:
            return "Unknown"
        elif self.competition <= 33:
            return "Low"
        elif self.competition <= 66:
            return "Medium"
        else:
            return "High"
    
    @property
    def bid_range(self) -> Optional[str]:
        """Format bid range as string"""
        if self.low_top_page_bid and self.high_top_page_bid:
            return f"${self.low_top_page_bid:.2f} - ${self.high_top_page_bid:.2f}"
        return None


class KeywordBulkUpload(BaseModel):
    """Model for bulk keyword upload"""
    client_id: str
    keywords: list[KeywordCreate]
    
    @field_validator('keywords')
    @classmethod
    def validate_keywords_count(cls, v: list) -> list:
        """Validate number of keywords"""
        if len(v) > 10000:
            raise ValueError("Cannot upload more than 10,000 keywords at once")
        return v