"""
Dashboard API endpoints for results and analytics
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user
from app.models.user import User
from app.services.dashboard_service import DashboardService


router = APIRouter()


# Initialize service
dashboard_service: Optional[DashboardService] = None


async def get_dashboard_service():
    """Get dashboard service instance"""
    global dashboard_service
    if not dashboard_service:
        from app.core.config import settings
        from app.core.database import get_db
        db = await get_db()
        dashboard_service = DashboardService(settings, db)
    return dashboard_service


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service)
):
    """Get dashboard summary statistics"""
    summary = await service.get_summary()
    return summary


@router.get("/dsi")
async def get_dsi_rankings(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service)
):
    """Get DSI company rankings"""
    rankings = await service.get_dsi_rankings(limit)
    return {"rankings": rankings}


@router.get("/content")
async def get_content_analysis(
    limit: int = Query(100, ge=1, le=500),
    domain: Optional[str] = Query(None),
    persona: Optional[str] = Query(None),
    jtbd_phase: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service)
):
    """Get content analysis results"""
    content = await service.get_content_analysis(
        limit=limit,
        domain=domain,
        persona=persona,
        jtbd_phase=jtbd_phase
    )
    return {"content": content}


@router.get("/companies/{domain}")
async def get_company_details(
    domain: str,
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service)
):
    """Get detailed company information"""
    details = await service.get_company_details(domain)
    return details


@router.get("/export")
async def export_results(
    format: str = Query("csv", regex="^(csv|json|excel)$"),
    filters: Optional[Dict] = None,
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service)
):
    """Export analysis results"""
    # This would return a file download
    return {"message": f"Export in {format} format would be implemented"}


@router.get("/trending")
async def get_trending_content(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service)
):
    """Get trending content"""
    trending = await service.get_trending_content(days)
    return {"trending": trending}
