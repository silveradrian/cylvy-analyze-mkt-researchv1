"""
Analysis configuration models
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PersonaConfig(BaseModel):
    """Persona configuration model"""
    name: str
    description: str
    title: str = ""
    goals: List[str] = []
    pain_points: List[str] = []
    decision_criteria: List[str] = []
    content_preferences: List[str] = []


class JTBDPhaseConfig(BaseModel):
    """JTBD phase configuration model"""
    name: str
    description: str
    buyer_mindset: str = ""
    key_questions: List[str] = []
    content_types: List[str] = []


class AnalysisConfig(BaseModel):
    """Complete analysis configuration"""
    id: Optional[UUID] = None
    
    # Configuration data
    personas: List[PersonaConfig] = []
    jtbd_phases: List[JTBDPhaseConfig] = []
    competitor_domains: List[str] = []
    custom_dimensions: Dict[str, List[str]] = {}
    
    # AI Configuration
    temperature: float = 0.7
    max_tokens: int = 4000
    model: str = "gpt-4-turbo-preview"
    
    # Feature flags
    enable_mention_extraction: bool = True
    enable_sentiment_analysis: bool = True
    enable_competitor_tracking: bool = True
    enable_historical_tracking: bool = True
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
