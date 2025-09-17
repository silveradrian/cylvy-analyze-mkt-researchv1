"""
Pipeline Management API Endpoints
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

from app.core.auth import get_current_user
from app.models.user import User
from app.core.database import db_pool
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
    regions: Optional[List[str]] = Field(None, description="Regions to collect data for (null = use schedule config)")
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
    
    # Testing mode configuration
    testing_mode: bool = Field(False, description="Enable testing mode to force full pipeline run")
    testing_batch_size: Optional[int] = Field(None, ge=1, le=100, description="Limit keyword batch size for testing")
    testing_skip_delays: bool = Field(False, description="Skip rate limiting delays in testing mode")
    
    # Mode
    mode: PipelineMode = PipelineMode.MANUAL
    
    # SERP reuse option
    reuse_serp_from_pipeline_id: Optional[str] = Field(None, description="UUID of previous pipeline to reuse SERP results from")


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
        # Idempotency guard: if a pipeline started very recently and is running, return it
        try:
            async with db_pool.acquire() as conn:
                existing = await conn.fetchrow(
                    """
                    SELECT id
                    FROM pipeline_executions
                    WHERE status = 'running'
                      AND started_at >= NOW() - INTERVAL '15 seconds'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                )
                if existing and existing.get('id'):
                    return {
                        "pipeline_id": str(existing['id']),
                        "message": "Pipeline already running (recent start); returning existing execution.",
                        "status": "running"
                    }
        except Exception:
            pass

        # Get active schedule to use its configuration
        async with db_pool.acquire() as conn:
            schedule_data = await conn.fetchrow(
                """
                SELECT id, content_schedules, regions, custom_keywords
                FROM pipeline_schedules 
                WHERE is_active = true
                LIMIT 1
                """
            )
        
        # Create pipeline config
        # Prefer explicit request keywords; otherwise use active schedule custom_keywords if available
        schedule_keywords = None
        if schedule_data and schedule_data.get('custom_keywords'):
            try:
                import json as _json
                raw = _json.loads(schedule_data['custom_keywords']) if isinstance(schedule_data['custom_keywords'], str) else schedule_data['custom_keywords']
                # Normalize to list[str]
                if isinstance(raw, list):
                    schedule_keywords = []
                    for k in raw:
                        if isinstance(k, dict) and k.get('keyword'):
                            schedule_keywords.append(str(k['keyword']))
                        elif isinstance(k, str):
                            schedule_keywords.append(k)
            except Exception:
                schedule_keywords = None

        # Prefer explicit request regions; otherwise use active schedule regions if available
        schedule_regions = None
        if schedule_data and schedule_data.get('regions'):
            schedule_regions = schedule_data['regions']
            logger.info(f"Schedule has regions configured: {schedule_regions}")

        # Use request regions if provided, otherwise fall back to schedule regions
        regions_to_use = request.regions if request.regions is not None else schedule_regions
        if not regions_to_use:
            # Final fallback if no regions configured anywhere
            regions_to_use = ["US", "UK"]
            logger.warning("No regions configured in request or schedule, using default: ['US', 'UK']")
        
        logger.info(f"Pipeline will use regions: {regions_to_use}")

        # Parse reuse_serp_from_pipeline_id if provided
        reuse_serp_uuid = None
        if request.reuse_serp_from_pipeline_id:
            try:
                reuse_serp_uuid = UUID(request.reuse_serp_from_pipeline_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid pipeline UUID format for SERP reuse")

        config = PipelineConfig(
            keywords=request.keywords or schedule_keywords,
            regions=regions_to_use,
            content_types=request.content_types,
            max_concurrent_serp=request.max_concurrent_serp,
            max_concurrent_enrichment=request.max_concurrent_enrichment,
            max_concurrent_analysis=request.max_concurrent_analysis,
            enable_company_enrichment=request.enable_company_enrichment,
            enable_video_enrichment=request.enable_video_enrichment,
            enable_content_analysis=request.enable_content_analysis,
            enable_historical_tracking=request.enable_historical_tracking,
            force_refresh=request.force_refresh,
            schedule_id=schedule_data['id'] if schedule_data else None,
            reuse_serp_from_pipeline_id=reuse_serp_uuid
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


class PipelineResumeRequest(BaseModel):
    """Request to resume a pipeline"""
    keywords: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    content_types: Optional[List[str]] = None


@router.post("/{pipeline_id}/resume", response_model=dict)
async def resume_pipeline(
    pipeline_id: UUID,
    request: PipelineResumeRequest,
    current_user: User = Depends(get_current_user),
    pipeline_svc: PipelineService = Depends(get_pipeline_service)
):
    """Resume an existing pipeline execution from where it left off."""
    if current_user.role not in ["analyst", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Build a minimal config override if provided
    config = None
    if any([request.keywords, request.regions, request.content_types]):
        config = PipelineConfig(
            keywords=request.keywords,
            regions=request.regions or ["US", "UK"],
            content_types=request.content_types or ["organic", "news", "video"],
        )

    try:
        ok = await pipeline_svc.resume_pipeline(pipeline_id, config)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to resume pipeline")
        return {"pipeline_id": str(pipeline_id), "resumed": True}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to resume pipeline")
        raise HTTPException(status_code=500, detail=f"Failed to resume pipeline: {e}")


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


@router.post("/cache/purge-keywords")
async def purge_keyword_cache(
    current_user: User = Depends(get_current_user)
):
    """Purge all keyword metrics from cache"""
    try:
        from app.services.keywords.dataforseo_service import DataForSEOService
        
        service = DataForSEOService()
        await service.initialize()
        purged_count = await service.purge_keyword_metrics_cache()
        await service.close()
        
        return {
            "success": True,
            "message": f"Purged {purged_count} keyword metrics from cache"
        }
    except Exception as e:
        logger.error(f"Failed to purge keyword cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to purge cache: {str(e)}")


@router.post("/{pipeline_id}/fail")
async def mark_pipeline_failed(
    pipeline_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Manually mark a pipeline as failed and close it out."""
    if current_user.role not in ["analyst", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        async with db_pool.acquire() as conn:
            # Update pipeline execution status and completion time
            updated = await conn.execute(
                """
                UPDATE pipeline_executions
                SET status = 'failed', completed_at = NOW()
                WHERE id = $1 AND status <> 'completed'
                """,
                pipeline_id
            )

            # Also mark any running/pending/blocked phases as failed for consistency
            await conn.execute(
                """
                UPDATE pipeline_phase_status
                SET status = 'failed', updated_at = NOW(), completed_at = NOW(),
                    result_data = COALESCE(result_data, '{}'::jsonb) || '{"manual_fail": true}'::jsonb
                WHERE pipeline_execution_id = $1 AND status IN ('running','pending','blocked')
                """,
                pipeline_id
            )

        logger.info(f"Manually marked pipeline {pipeline_id} as failed")
        return {"pipeline_id": str(pipeline_id), "status": "failed"}
    except Exception as e:
        logger.exception("Failed to mark pipeline as failed")
        raise HTTPException(status_code=500, detail=f"Failed to mark pipeline as failed: {e}")


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
                "content_types": p.content_types,
                "regions": p.regions,
                "current_phase": p.current_phase,
                "phases_completed": p.phases_completed,
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
                "regions": s.regions,
                "keywords": s.keywords,
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
                "id": str(updated_schedule.id),
                "name": updated_schedule.name,
                "is_active": updated_schedule.is_active,
                "next_execution_at": updated_schedule.next_execution_at.isoformat() if updated_schedule.next_execution_at else None
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


@router.delete("/clear-all")
async def clear_all_pipelines(
    current_user: User = Depends(get_current_user),
    pipeline_svc: PipelineService = Depends(get_pipeline_service)
):
    """Clear all pipeline execution history"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        count = await pipeline_svc.clear_all_pipelines()
        return {
            "message": f"Successfully cleared {count} pipeline executions",
            "count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear pipelines: {str(e)}")


class TestModeRequest(BaseModel):
    batch_size: int = 5
    skip_delays: bool = True
    regions: List[str] = ["US"]
    content_types: List[str] = ["organic", "news", "video"]


@router.post("/test-mode")
async def start_testing_pipeline(
    request: TestModeRequest,
    current_user: User = Depends(get_current_user),
    pipeline_svc: PipelineService = Depends(get_pipeline_service),
    scheduling_svc: SchedulingService = Depends(get_scheduling_service)
):
    """Start a pipeline in testing mode with limited batch size for rapid testing"""
    if current_user.role not in ["admin", "superadmin", "developer"]:
        raise HTTPException(status_code=403, detail="Testing mode requires admin/developer access")
    
    try:
        # Get regions from active schedule if available
        try:
            schedules = await scheduling_svc.get_all_schedules(active_only=True)
            regions = request.regions  # Default to request regions
            
            if schedules and len(schedules) > 0:
                # Use regions from the first active schedule
                regions = schedules[0].regions
                logger.info(f"Using regions from active schedule: {regions}")
            else:
                logger.info(f"No active schedule found, using default regions: {regions}")
        except Exception as e:
            logger.error(f"Error getting schedules: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Get the schedule_id from active schedule if available
        schedule_id = None
        if schedules and len(schedules) > 0:
            schedule_id = schedules[0].id
            logger.info(f"Using schedule_id from active schedule: {schedule_id}")
        
        # Create testing mode config
        config = PipelineConfig(
            client_id=f"test_{current_user.id}",
            testing_mode=True,
            testing_batch_size=request.batch_size,
            testing_skip_delays=request.skip_delays,
            regions=regions,
            content_types=request.content_types,
            schedule_id=schedule_id,  # Include schedule_id for proper scheduling
            # Force all phases to run
            enable_keyword_metrics=True,
            enable_company_enrichment=True,
            enable_video_enrichment=True,
            enable_content_analysis=True,
            enable_historical_tracking=True,
            enable_landscape_dsi=True,
            force_refresh=True
        )
        
        # Start pipeline
        pipeline_id = await pipeline_svc.start_pipeline(config, PipelineMode.TESTING)
        
        return {
            "pipeline_id": pipeline_id,
            "mode": "testing",
            "message": f"Testing pipeline started with {request.batch_size} keywords",
            "config": {
                "batch_size": request.batch_size,
                "skip_delays": request.skip_delays,
                "regions": request.regions,
                "content_types": request.content_types
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start testing pipeline: {str(e)}")


@router.get("/trending")
async def get_trending_content(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    historical_svc: HistoricalDataService = Depends(get_historical_service)
):
    """Get trending content based on DSI improvements"""
    trending = await historical_svc.get_trending_content(days)
    return {"trending_content": [dict(content) for content in trending]}


@router.get("/config")
async def get_pipeline_config(
    current_user: User = Depends(get_current_user),
):
    """Return the current active pipeline configuration (keywords, regions, content_schedules)."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, content_schedules, regions, custom_keywords, is_active
            FROM pipeline_schedules
            WHERE is_active = TRUE
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """
        )
    if not row:
        return {
            "id": None,
            "is_active": False,
            "content_schedules": [],
            "regions": ["US", "UK"],
            "keywords": []
        }

    # Parse JSON/arrays
    import json as _json
    content_schedules = row["content_schedules"]
    if isinstance(content_schedules, str):
        try:
            content_schedules = _json.loads(content_schedules)
        except Exception:
            content_schedules = []
    custom_keywords = row["custom_keywords"]
    keywords = []
    if custom_keywords:
        try:
            raw = _json.loads(custom_keywords) if isinstance(custom_keywords, str) else custom_keywords
            # Normalize to list[str]
            if isinstance(raw, list):
                for k in raw:
                    if isinstance(k, dict) and k.get("keyword"):
                        keywords.append(str(k["keyword"]))
                    elif isinstance(k, str):
                        keywords.append(k)
        except Exception:
            keywords = []

    return {
        "id": str(row["id"]),
        "is_active": row["is_active"],
        "content_schedules": content_schedules or [],
        "regions": row["regions"] or ["US", "UK"],
        "keywords": keywords or []
    }


class PipelineConfigUpdate(BaseModel):
    content_schedules: Optional[List[dict]] = None
    regions: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    is_active: Optional[bool] = True


@router.put("/config")
async def update_pipeline_config(
    request: PipelineConfigUpdate,
    current_user: User = Depends(get_current_user),
    scheduling_svc: SchedulingService = Depends(get_scheduling_service)
):
    """Update and activate the pipeline configuration. This persists and takes effect immediately."""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Find existing active schedule or create one
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM pipeline_schedules
            WHERE is_active = TRUE
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """
        )

    # Build updates payload for SchedulingService
    updates: dict = {}
    if request.content_schedules is not None:
        updates["content_schedules"] = request.content_schedules
    if request.regions is not None:
        updates["regions"] = request.regions
    if request.keywords is not None:
        updates["keywords"] = request.keywords
    if request.is_active is not None:
        updates["is_active"] = bool(request.is_active)

    # Ensure only one active schedule: deactivate others if we are activating
    async with db_pool.acquire() as conn:
        if updates.get("is_active", True):
            await conn.execute("UPDATE pipeline_schedules SET is_active = FALSE WHERE is_active = TRUE")

    if existing:
        # Update the existing schedule
        schedule = await scheduling_svc.update_schedule(existing["id"], updates)
        schedule_id = schedule.id
    else:
        # Create a new schedule with defaults then update
        from app.services.scheduling_service import PipelineSchedule, ContentTypeSchedule, ScheduleFrequency
        default_cs = [
            ContentTypeSchedule(content_type="organic", enabled=True, frequency=ScheduleFrequency.MONTHLY),
            ContentTypeSchedule(content_type="news", enabled=True, frequency=ScheduleFrequency.WEEKLY),
            ContentTypeSchedule(content_type="video", enabled=True, frequency=ScheduleFrequency.MONTHLY),
        ]
        new_schedule = PipelineSchedule(
            name="Active Project Config",
            description="Primary active pipeline configuration",
            is_active=True,
            content_schedules=default_cs,
            keywords=request.keywords or [],
            regions=request.regions or ["US", "UK"],
        )
        schedule_id = await scheduling_svc.create_schedule(new_schedule)
        if updates:
            await scheduling_svc.update_schedule(schedule_id, updates)

    # Return current config
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM pipeline_schedules WHERE id = $1", schedule_id)
    return {"id": str(row["id"]), "message": "Configuration saved and activated"}

