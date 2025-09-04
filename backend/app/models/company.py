"""Company enrichment models"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from enum import Enum


class CompanyEnrichmentRequest(BaseModel):
    """Request model for company enrichment"""
    client_id: str = Field(..., description="Client ID")
    domains: List[str] = Field(..., min_items=1, max_items=100, description="List of domains to enrich")
    country: Optional[str] = Field(None, description="Country filter for better matching")
    force_refresh: bool = Field(False, description="Force refresh from API, bypassing cache")


class CompanyProfile(BaseModel):
    """Complete company profile with enriched data"""
    # Basic Information
    domain: str = Field(..., description="Primary domain")
    company_name: str = Field(..., description="Company name")
    website: Optional[str] = Field(None, description="Company website URL")
    
    # Industry & Classification
    industry: Optional[str] = Field(None, description="Primary industry")
    sub_industry: Optional[str] = Field(None, description="Sub-industry")
    sic_code: Optional[str] = Field(None, description="SIC code")
    naics_code: Optional[str] = Field(None, description="NAICS code")
    source_type: Optional[str] = Field(None, description="Content source classification (OWNED, COMPETITOR, TECHNOLOGY, etc.)")
    
    # Financial Information
    revenue_amount: Optional[float] = Field(None, description="Annual revenue amount")
    revenue_range: Optional[str] = Field(None, description="Revenue range description")
    revenue_currency: str = Field("USD", description="Revenue currency")
    
    # Company Size
    headcount: Optional[int] = Field(None, description="Number of employees")
    employee_range: Optional[str] = Field(None, description="Employee range description")
    
    # Company Details
    founded_year: Optional[int] = Field(None, description="Year founded")
    description: Optional[str] = Field(None, description="Company description")
    company_type: Optional[str] = Field(None, description="Company type (public/private)")
    
    # Location
    headquarters_location: Optional[Dict[str, str]] = Field(None, description="HQ location")
    phone: Optional[str] = Field(None, description="Company phone number")
    
    # Technology Stack
    technologies: List[str] = Field(default_factory=list, description="Technologies used")
    
    # Social Profiles
    social_profiles: Optional[Dict[str, str]] = Field(None, description="Social media profiles")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn company page URL")
    
    # Metadata
    last_confirmed: Optional[str] = Field(None, description="Last data confirmation date")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Data confidence score")
    source: str = Field("cognism", description="Data source")
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('domain')
    @classmethod
    def clean_domain(cls, v: str) -> str:
        """Clean and normalize domain"""
        if not v:
            raise ValueError("Domain is required")
        # Remove protocol
        v = v.replace('http://', '').replace('https://', '')
        # Remove www
        v = v.replace('www.', '')
        # Remove path
        v = v.split('/')[0]
        # Convert to lowercase
        return v.lower()
    
    @field_validator('revenue_amount')
    @classmethod
    def validate_revenue(cls, v: Optional[float]) -> Optional[float]:
        """Validate revenue amount"""
        if v is not None and v < 0:
            raise ValueError("Revenue cannot be negative")
        return v
    
    @field_validator('headcount')
    @classmethod
    def validate_headcount(cls, v: Optional[int]) -> Optional[int]:
        """Validate employee count"""
        if v is not None and v < 0:
            raise ValueError("Headcount cannot be negative")
        return v
    
    @field_validator('founded_year')
    @classmethod
    def validate_founded_year(cls, v: Optional[int]) -> Optional[int]:
        """Validate founded year"""
        if v is not None:
            current_year = datetime.now().year
            if v < 1700 or v > current_year:
                raise ValueError(f"Founded year must be between 1700 and {current_year}")
        return v


class CompanyEnrichmentResult(BaseModel):
    """Result of company enrichment operation"""
    domain: str
    success: bool
    profile: Optional[CompanyProfile] = None
    error: Optional[str] = None
    cached: bool = Field(False, description="Whether result was from cache")
    
    
class BatchEnrichmentResult(BaseModel):
    """Result of batch enrichment operation"""
    job_id: str
    client_id: str
    total: int
    successful: int
    failed: int
    results: List[CompanyEnrichmentResult]
    started_at: datetime
    completed_at: Optional[datetime] = None
    

class CompanySearchResult(BaseModel):
    """Internal model for company search results"""
    id: str
    name: str
    domain: str
    website: Optional[str] = None
    industry: Optional[str] = None
    revenue: Optional[str] = None
    employee_count: Optional[str] = None
    headquarters: Optional[Any] = None  # Can be list or dict
    score: float = Field(0.0, description="Match score")
    raw_data: Dict[str, Any] = Field(default_factory=dict)