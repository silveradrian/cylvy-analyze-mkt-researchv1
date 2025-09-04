"""
Pipeline Management API Endpoints
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.user import User
from app.services.pipeline.pipeline_service import (
    PipelineService, PipelineConfig, PipelineMode, 
    PipelineResult, PipelineStatus
)
from app.services.scheduling_service import (
    SchedulingService, PipelineSchedule, ContentTypeSchedule,
    ScheduleExecution, ScheduleFrequency
)
from app.services.historical_data_service import HistoricalDataService
from app.core.database import get_db


router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# Request/Response Models
class PipelineStartRequest(BaseModel):
    """Request to start a pipeline"""
    client_id: Optional[str] = Field(None, description="Client ID for data isolation (defaults to authenticated user)")
    keywords: Optional[List[str]] = Field(None, description="Specific keywords to process (null = all)")
    regions: List[str] = Field(["US", "UK"], description="Regions to collect data for")
    content_types: List[str] = Field(["organic", "news", "video"], description="Content types to collect")
    
    # Execution settings
    max_concurrent_serp: int = Field(10, ge=1, le=50)
    max_concurrent_enrichment: int = Field(15, ge=1, le=30)
    max_concurrent_analysis: int = Field(20, ge=1, le=50)
    
    # Feature flags
    enable_keyword_metrics: bool = Field(True, description="Fetch Google Ads historical metrics for all keywords across selected countries")
    enable_company_enrichment: bool = True
    enable_video_enrichment: bool = True
    enable_content_analysis: bool = True
    enable_historical_tracking: bool = True
    enable_landscape_dsi: bool = Field(True, description="Calculate DSI metrics for all active digital landscapes")
    force_refresh: bool = Field(False, description="Force refresh of existing data")
    
    # Mode
    mode: PipelineMode = PipelineMode.MANUAL


class PipelineStatusResponse(BaseModel):
    """Pipeline status response"""
    pipeline_id: UUID
    status: PipelineStatus
    mode: PipelineMode
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Progress information
    current_phase: Optional[str] = None
    phases_completed: List[str] = []
    phases_remaining: List[str] = []
    
    # Statistics
    keywords_processed: int = 0
    keywords_with_metrics: int = 0
    serp_results_collected: int = 0
    companies_enriched: int = 0
    videos_enriched: int = 0
    content_analyzed: int = 0
    landscapes_calculated: int = 0
    
    # Errors
    errors: List[str] = []
    warnings: List[str] = []


class ScheduleCreateRequest(BaseModel):
    """Request to create a schedule"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    
    # Schedule configuration
    content_schedules: List[ContentTypeSchedule]
    keywords: Optional[List[str]] = None
    regions: List[str] = ["US", "UK"]
    
    # Execution settings
    max_concurrent_executions: int = Field(1, ge=1, le=5)
    
    # Notifications
    notification_emails: Optional[List[str]] = None
    notify_on_completion: bool = True
    notify_on_error: bool = True


class HistoricalSnapshotRequest(BaseModel):
    """Request to create historical snapshot"""
    snapshot_date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format (defaults to first of current month)")


# Initialize services (would be properly injected in production)
pipeline_service: Optional[PipelineService] = None
scheduling_service: Optional[SchedulingService] = None
historical_service: Optional[HistoricalDataService] = None


async def get_pipeline_service():
    """Get pipeline service instance"""
    global pipeline_service
    if not pipeline_service:
        from app.core.config import settings
        from app.core.database import get_db
        db = await get_db()
        pipeline_service = PipelineService(settings, db)
    return pipeline_service


async def get_scheduling_service():
    """Get scheduling service instance"""
    global scheduling_service
    if not scheduling_service:
        from app.core.config import settings
        from app.core.database import get_db
        db = await get_db()
        pipeline_svc = await get_pipeline_service()
        scheduling_service = SchedulingService(settings, db, pipeline_svc)
    return scheduling_service


async def get_historical_service():
    """Get historical data service instance"""
    global historical_service
    if not historical_service:
        from app.core.config import settings
        from app.core.database import get_db
        db = await get_db()
        historical_service = HistoricalDataService(db, settings)
    return historical_service


@router.post("/start", response_model=dict)
async def start_pipeline(
    request: PipelineStartRequest,
    current_user: User = Depends(get_current_user),
    pipeline_svc: PipelineService = Depends(get_pipeline_service)
):
    """Start a new pipeline execution"""
    if current_user.role not in ["analyst", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        # Create pipeline config
        config = PipelineConfig(
            keywords=request.keywords,
            regions=request.regions,
            content_types=request.content_types,
            max_concurrent_serp=request.max_concurrent_serp,
            max_concurrent_enrichment=request.max_concurrent_enrichment,
            max_concurrent_analysis=request.max_concurrent_analysis,
            enable_company_enrichment=request.enable_company_enrichment,
            enable_video_enrichment=request.enable_video_enrichment,
            enable_content_analysis=request.enable_content_analysis,
            enable_historical_tracking=request.enable_historical_tracking,
            force_refresh=request.force_refresh
        )
        
        # Start pipeline
        pipeline_id = await pipeline_svc.start_pipeline(config, request.mode)
        
        return {
            "pipeline_id": pipeline_id,
            "message": "Pipeline started successfully",
            "status": "pending"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {str(e)}")


@router.get("/status/{pipeline_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    pipeline_id: UUID,
    current_user: User = Depends(get_current_user),
    pipeline_svc: PipelineService = Depends(get_pipeline_service)
):
    """Get pipeline execution status"""
    result = await pipeline_svc.get_pipeline_status(pipeline_id)
    if not result:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    # Calculate duration
    duration_seconds = None
    if result.completed_at and result.started_at:
        duration_seconds = int((result.completed_at - result.started_at).total_seconds())
    
    # Determine current phase and progress
    current_phase = None
    phases_completed = []
    phases_remaining = []
    
    if result.phase_results:
        all_phases = ["serp_collection", "company_enrichment", "video_enrichment", 
                     "content_scraping", "content_analysis", "dsi_calculation", 
                     "historical_snapshot"]
        
        for phase in all_phases:
            if phase in result.phase_results:
                phases_completed.append(phase)
            else:
                if current_phase is None and result.status == PipelineStatus.RUNNING:
                    current_phase = phase
                phases_remaining.append(phase)
    
    return PipelineStatusResponse(
        pipeline_id=result.pipeline_id,
        status=result.status,
        mode=result.mode,
        started_at=result.started_at,
        completed_at=result.completed_at,
        duration_seconds=duration_seconds,
        current_phase=current_phase,
        phases_completed=phases_completed,
        phases_remaining=phases_remaining,
        keywords_processed=result.keywords_processed,
        serp_results_collected=result.serp_results_collected,
        companies_enriched=result.companies_enriched,
        videos_enriched=result.videos_enriched,
        content_analyzed=result.content_analyzed,
        errors=result.errors,
        warnings=result.warnings
    )


@router.delete("/{pipeline_id}")
async def cancel_pipeline(
    pipeline_id: UUID,
    current_user: User = Depends(get_current_user),
    pipeline_svc: PipelineService = Depends(get_pipeline_service)
):
    """Cancel a running pipeline"""
    if current_user.role not in ["analyst", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    success = await pipeline_svc.cancel_pipeline(pipeline_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pipeline not found or cannot be cancelled")
    
    return {"message": "Pipeline cancelled successfully"}


@router.get("/recent")
async def get_recent_pipelines(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    pipeline_svc: PipelineService = Depends(get_pipeline_service)
):
    """Get recent pipeline executions"""
    pipelines = await pipeline_svc.get_recent_pipelines(limit)
    
    return {
        "pipelines": [
            {
                "pipeline_id": p.pipeline_id,
                "status": p.status,
                "mode": p.mode,
                "started_at": p.started_at,
                "completed_at": p.completed_at,
                "keywords_processed": p.keywords_processed,
                "serp_results_collected": p.serp_results_collected,
                "content_analyzed": p.content_analyzed,
                "errors_count": len(p.errors)
            }
            for p in pipelines
        ]
    }


# Scheduling Endpoints
@router.post("/schedules", response_model=dict)
async def create_schedule(
    request: ScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    scheduling_svc: SchedulingService = Depends(get_scheduling_service)
):
    """Create a new pipeline schedule"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        schedule = PipelineSchedule(
            name=request.name,
            description=request.description,
            content_schedules=request.content_schedules,
            keywords=request.keywords,
            regions=request.regions,
            max_concurrent_executions=request.max_concurrent_executions,
            notification_emails=request.notification_emails,
            notify_on_completion=request.notify_on_completion,
            notify_on_error=request.notify_on_error
        )
        
        schedule_id = await scheduling_svc.create_schedule(schedule)
        
        return {
            "schedule_id": schedule_id,
            "message": "Schedule created successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")


@router.get("/schedules")
async def get_schedules(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    scheduling_svc: SchedulingService = Depends(get_scheduling_service)
):
    """Get all pipeline schedules"""
    schedules = await scheduling_svc.get_all_schedules(active_only)
    
    return {
        "schedules": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "is_active": s.is_active,
                "content_schedules": [cs.dict() for cs in s.content_schedules],
                "next_execution_at": s.next_execution_at,
                "last_executed_at": s.last_executed_at
            }
            for s in schedules
        ]
    }


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: UUID,
    updates: dict,
    current_user: User = Depends(get_current_user),
    scheduling_svc: SchedulingService = Depends(get_scheduling_service)
):
    """Update a pipeline schedule"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        updated_schedule = await scheduling_svc.update_schedule(schedule_id, updates)
        return {
            "message": "Schedule updated successfully",
            "schedule": {
                "id": updated_schedule.id,
                "name": updated_schedule.name,
                "is_active": updated_schedule.is_active,
                "next_execution_at": updated_schedule.next_execution_at
            }
        }
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    scheduling_svc: SchedulingService = Depends(get_scheduling_service)
):
    """Delete a pipeline schedule"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    success = await scheduling_svc.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    return {"message": "Schedule deleted successfully"}


# Historical Data Endpoints
@router.post("/snapshot", response_model=dict)
async def create_historical_snapshot(
    request: HistoricalSnapshotRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    historical_svc: HistoricalDataService = Depends(get_historical_service)
):
    """Create a historical data snapshot"""
    if current_user.role not in ["analyst", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Parse snapshot date
    snapshot_date = None
    if request.snapshot_date:
        try:
            snapshot_date = datetime.strptime(request.snapshot_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Create snapshot in background
    background_tasks.add_task(
        historical_svc.create_monthly_snapshot,
        snapshot_date
    )
    
    return {
        "message": "Historical snapshot creation started",
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else "first of current month"
    }


@router.get("/trends/dsi")
async def get_dsi_trends(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    historical_svc: HistoricalDataService = Depends(get_historical_service)
):
    """Get month-over-month DSI trends"""
    trends = await historical_svc.get_month_over_month_dsi(limit)
    return {"trends": [dict(trend) for trend in trends]}


@router.get("/trends/pages")
async def get_page_trends(
    months: int = 12,
    domain: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    historical_svc: HistoricalDataService = Depends(get_historical_service)
):
    """Get page-level trends"""
    trends = await historical_svc.get_page_trends(months, domain, content_type, limit)
    return {"trends": [dict(trend) for trend in trends]}


@router.get("/lifecycle/pages")
async def get_page_lifecycle(
    status: Optional[str] = None,
    domain: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    historical_svc: HistoricalDataService = Depends(get_historical_service)
):
    """Get page lifecycle analysis"""
    lifecycle_data = await historical_svc.get_page_lifecycle_data(status, domain)
    return {"pages": [dict(page) for page in lifecycle_data]}


@router.get("/trending")
async def get_trending_content(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    historical_svc: HistoricalDataService = Depends(get_historical_service)
):
    """Get trending content based on DSI improvements"""
    trending = await historical_svc.get_trending_content(days)
    return {"trending_content": [dict(content) for content in trending]}

