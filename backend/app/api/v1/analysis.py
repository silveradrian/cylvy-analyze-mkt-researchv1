"""
Analysis configuration API endpoints
"""
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.auth import get_current_user, require_admin
from app.models.user import User
from app.services.analysis.analysis_config_service import AnalysisConfigService


router = APIRouter()


class PersonaRequest(BaseModel):
    """Persona configuration request"""
    name: str
    description: str
    title: str = ""
    goals: List[str] = []
    pain_points: List[str] = []
    decision_criteria: List[str] = []
    content_preferences: List[str] = []


class JTBDPhaseRequest(BaseModel):
    """JTBD phase configuration request"""
    name: str
    description: str
    buyer_mindset: str = ""
    key_questions: List[str] = []
    content_types: List[str] = []


class AnalysisConfigRequest(BaseModel):
    """Analysis configuration request"""
    personas: List[PersonaRequest] = []
    jtbd_phases: List[JTBDPhaseRequest] = []
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


# Initialize service
analysis_config_service: Optional[AnalysisConfigService] = None


async def get_analysis_config_service():
    """Get analysis config service instance"""
    global analysis_config_service
    if not analysis_config_service:
        from app.core.config import settings
        from app.core.database import get_db
        db = await get_db()
        analysis_config_service = AnalysisConfigService(settings, db)
    return analysis_config_service


@router.get("/config")
async def get_analysis_config(
    current_user: User = Depends(get_current_user),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Get current analysis configuration"""
    config = await service.get_config()
    return config


@router.put("/config")
async def update_analysis_config(
    config_update: AnalysisConfigRequest,
    current_user: User = Depends(require_admin),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Update analysis configuration"""
    config = await service.update_config(config_update.dict())
    return {"message": "Configuration updated successfully", "config": config}


@router.get("/personas")
async def get_personas(
    current_user: User = Depends(get_current_user),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Get configured personas"""
    config = await service.get_config()
    return {"personas": config.personas}


@router.put("/personas")
async def update_personas(
    personas_data: Dict[str, List[PersonaRequest]],
    current_user: User = Depends(require_admin),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Update personas configuration"""
    await service.update_config({"personas": personas_data["personas"]})
    return {"message": "Personas updated successfully"}


@router.get("/jtbd")
async def get_jtbd_phases(
    current_user: User = Depends(get_current_user),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Get JTBD phases configuration"""
    config = await service.get_config()
    return {"jtbd_phases": config.jtbd_phases}


@router.put("/jtbd")
async def update_jtbd_phases(
    phases_data: Dict[str, List[JTBDPhaseRequest]],
    current_user: User = Depends(require_admin),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Update JTBD phases configuration"""
    await service.update_config({"jtbd_phases": phases_data["phases"]})
    return {"message": "JTBD phases updated successfully"}


@router.get("/competitors")
async def get_competitors(
    current_user: User = Depends(get_current_user),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Get competitor domains"""
    config = await service.get_config()
    return {"competitor_domains": config.competitor_domains}


@router.put("/competitors")
async def update_competitors(
    competitors_data: Dict[str, List[str]],
    current_user: User = Depends(require_admin),
    service: AnalysisConfigService = Depends(get_analysis_config_service)
):
    """Update competitor domains"""
    await service.update_config({"competitor_domains": competitors_data["competitor_domains"]})
    return {"message": "Competitors updated successfully"}
