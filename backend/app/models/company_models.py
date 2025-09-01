"""Company models for database entities"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class CompanyBase(BaseModel):
    """Base company model"""
    client_id: str = Field(..., description="Unique client identifier")
    company_name: str = Field(..., description="Company name")
    domain: str = Field(..., description="Company domain")


class CompanyCreate(CompanyBase):
    """Model for creating a new company"""
    pass


class Company(CompanyBase):
    """Complete company model with database fields"""
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class ClientConfig(BaseModel):
    """Client configuration model"""
    client_id: str
    personas: List[Dict[str, Any]] = Field(default_factory=list)
    jtbd_phases: List[str] = Field(
        default_factory=lambda: ["awareness", "consideration", "decision", "retention"]
    )
    competitors: List[str] = Field(default_factory=list)
    search_regions: List[str] = Field(default_factory=lambda: ["US"])
    refresh_interval_days: int = Field(30, ge=1, le=365)
    
    class Config:
        from_attributes = True