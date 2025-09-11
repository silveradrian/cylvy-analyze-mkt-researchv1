"""
Configuration models
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ClientConfig(BaseModel):
    """Client configuration model"""
    id: Optional[UUID] = None
    company_name: str
    company_domain: str
    company_logo_url: Optional[str] = None
    primary_color: str = "#3B82F6"
    secondary_color: str = "#10B981"
    admin_email: Optional[str] = None
    support_email: Optional[str] = None
    description: Optional[str] = None
    legal_name: Optional[str] = None
    additional_domains: Optional[List[str]] = None
    competitors: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator('primary_color', 'secondary_color')
    def validate_color(cls, v):
        if not v.startswith('#') or len(v) != 7:
            raise ValueError('Color must be in hex format (#RRGGBB)')
        return v
    
    class Config:
        from_attributes = True


class AnalysisConfig(BaseModel):
    """Analysis configuration model"""
    id: Optional[UUID] = None
    personas: list = []
    jtbd_phases: list = []
    competitor_domains: list = []
    custom_dimensions: dict = {}
    temperature: float = 0.7
    max_tokens: int = 4000
    model: str = "gpt-4o-mini"
    enable_mention_extraction: bool = True
    enable_sentiment_analysis: bool = True
    enable_competitor_tracking: bool = True
    enable_historical_tracking: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class APIKeyConfig(BaseModel):
    """API key configuration model"""
    id: Optional[UUID] = None
    service_name: str
    api_key_encrypted: str
    is_active: bool = True
    last_used: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
