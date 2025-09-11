"""
API endpoints for monitoring and robustness metrics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.robustness import (
    CircuitBreakerManager, StateTracker, JobQueueManager, RetryManager
)
# from app.services.pipeline.enhanced_pipeline_service import EnhancedPipelineService  # Moved to redundant
from app.services.pipeline.pipeline_service import PipelineService
from app.core.config import get_settings


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status response"""
    service_name: str
    current_state: str
    failure_count: int
    success_count: int
    total_requests: int
    total_failures: int
    total_successes: int
    success_rate: float
    last_failure_at: Optional[datetime]
    last_success_at: Optional[datetime]
    opened_at: Optional[datetime]
    half_opened_at: Optional[datetime]


class PipelineStateProgress(BaseModel):
    """Pipeline state progress response"""
    pipeline_id: UUID
    phase: Optional[str]
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    skipped: int
    completion_percentage: float
    avg_attempts: Optional[float]
    max_attempts: Optional[int]


class JobQueueStatus(BaseModel):
    """Job queue status response"""
    queue_name: str
    pending_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    dead_letter_count: int
    avg_processing_time_seconds: Optional[float]


class RetryStatistics(BaseModel):
    """Retry statistics response"""
    entity_type: str
    total_retries: int
    unique_entities: int
    avg_attempts: float
    max_attempts: int
    successful_retries: int
    failed_retries: int
    unique_error_codes: int
    avg_retry_delay: float
    success_rate: float


class HealthStatus(BaseModel):
    """Overall system health status"""
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    circuit_breakers: Dict[str, str]  # service -> state
    job_queues: Dict[str, int]  # queue -> pending count
    error_rate_1h: float
    api_quota_usage: Dict[str, Dict[str, Any]]  # service -> quota info


class SerpBatch(BaseModel):
    """SERP batch information"""
    id: str
    name: str
    status: str
    searches_total_count: int
    results_count: int
    created_at: datetime
    last_run: Optional[datetime] = None
    content_type: Optional[str] = None
    result_sets: Optional[List[Dict[str, Any]]] = None


class SerpBatchesResponse(BaseModel):
    """Response containing SERP batch information"""
    cylvy_batches: List[SerpBatch]
    third_party_batches: List[SerpBatch]


@router.get("/health", response_model=HealthStatus)
async def get_health_status(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
    settings=Depends(get_settings)
):
    """Get overall system health status"""
    
    # Initialize services
    cb_manager = CircuitBreakerManager(db)
    jq_manager = JobQueueManager(db)
    
    # Get circuit breaker states
    cb_metrics = await cb_manager.get_all_metrics()
    cb_states = {name: metrics['current_state'] for name, metrics in cb_metrics.items()}
    
    # Get job queue counts
    jq_stats = await jq_manager.get_all_stats()
    jq_pending = {name: stats['pending_count'] for name, stats in jq_stats.items()}
    
    # Calculate error rate for last hour
    async with db.acquire() as conn:
        error_stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) FILTER (WHERE last_error IS NOT NULL) as error_count,
                COUNT(*) as total_count
            FROM pipeline_state
            WHERE updated_at >= NOW() - INTERVAL '1 hour'
            """
        )
        
        error_rate = 0
        if error_stats and error_stats['total_count'] > 0:
            error_rate = (error_stats['error_count'] / error_stats['total_count']) * 100
    
    # Get API quota usage
    api_quota = {}
    
    # Scale SERP quota
    try:
        from app.services.serp.unified_serp_collector import UnifiedSERPCollector
        serp_collector = UnifiedSERPCollector(settings, db)
        serp_quota = await serp_collector.check_quota()
        api_quota['scale_serp'] = serp_quota
    except:
        pass
    
    # Determine overall health status
    status = "healthy"
    
    # Check circuit breakers
    if any(state == "open" for state in cb_states.values()):
        status = "degraded"
    
    # Check error rate
    if error_rate > 10:
        status = "degraded"
    elif error_rate > 25:
        status = "unhealthy"
    
    # Check job queues
    total_pending = sum(jq_pending.values())
    if total_pending > 1000:
        status = "degraded"
    elif total_pending > 5000:
        status = "unhealthy"
    
    return HealthStatus(
        status=status,
        timestamp=datetime.utcnow(),
        circuit_breakers=cb_states,
        job_queues=jq_pending,
        error_rate_1h=round(error_rate, 2),
        api_quota_usage=api_quota
    )


@router.get("/circuit-breakers", response_model=List[CircuitBreakerStatus])
async def get_circuit_breakers(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get status of all circuit breakers"""
    
    cb_manager = CircuitBreakerManager(db)
    metrics = await cb_manager.get_all_metrics()
    
    return [
        CircuitBreakerStatus(**metric_data)
        for metric_data in metrics.values()
    ]


@router.post("/circuit-breakers/{service_name}/reset")
async def reset_circuit_breaker(
    service_name: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Manually reset a circuit breaker"""
    
    cb_manager = CircuitBreakerManager(db)
    breaker = cb_manager.get_breaker(service_name)
    await breaker.reset()
    
    return {"message": f"Circuit breaker for {service_name} reset to CLOSED state"}


@router.get("/pipeline/{pipeline_id}/progress", response_model=PipelineStateProgress)
async def get_pipeline_progress(
    pipeline_id: UUID,
    phase: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get progress for a specific pipeline execution"""
    
    state_tracker = StateTracker(db)
    
    if phase:
        progress = await state_tracker.get_phase_progress(pipeline_id, phase)
    else:
        progress = await state_tracker.get_pipeline_progress(pipeline_id)
    
    return PipelineStateProgress(
        pipeline_id=pipeline_id,
        phase=phase,
        **progress
    )


@router.get("/pipeline/{pipeline_id}/failed-items")
async def get_pipeline_failed_items(
    pipeline_id: UUID,
    phase: Optional[str] = None,
    error_category: Optional[str] = None,
    limit: int = Query(100, le=1000),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get failed items for a pipeline execution"""
    
    state_tracker = StateTracker(db)
    failed_items = await state_tracker.get_failed_items(
        pipeline_id,
        phase=phase,
        error_category=error_category
    )
    
    return {
        "pipeline_id": pipeline_id,
        "total_failed": len(failed_items),
        "failed_items": failed_items[:limit]
    }


@router.post("/pipeline/{pipeline_id}/retry-failed")
async def retry_failed_items(
    pipeline_id: UUID,
    phase: Optional[str] = None,
    max_items: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Reset failed items to pending for retry"""
    
    state_tracker = StateTracker(db)
    reset_count = await state_tracker.reset_failed_items(
        pipeline_id,
        phase=phase,
        max_items=max_items
    )
    
    return {
        "pipeline_id": pipeline_id,
        "items_reset": reset_count,
        "message": f"Reset {reset_count} failed items to pending status"
    }


@router.get("/job-queues", response_model=List[JobQueueStatus])
async def get_job_queues(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get status of all job queues"""
    
    jq_manager = JobQueueManager(db)
    stats = await jq_manager.get_all_stats()
    
    return [
        JobQueueStatus(queue_name=name, **queue_stats)
        for name, queue_stats in stats.items()
    ]


@router.post("/job-queues/{queue_name}/retry-dead-letter")
async def retry_dead_letter_jobs(
    queue_name: str,
    job_ids: Optional[List[UUID]] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Retry jobs from dead letter queue"""
    
    jq_manager = JobQueueManager(db)
    queue = jq_manager.get_queue(queue_name)
    count = await queue.retry_dead_letter_jobs(job_ids)
    
    return {
        "queue_name": queue_name,
        "jobs_retried": count,
        "message": f"Moved {count} jobs from dead letter back to pending"
    }


@router.get("/retry-statistics", response_model=List[RetryStatistics])
async def get_retry_statistics(
    entity_type: Optional[str] = None,
    time_window_hours: int = Query(24, ge=1, le=168),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get retry statistics"""
    
    retry_manager = RetryManager(db)
    stats = await retry_manager.get_retry_statistics(
        entity_type=entity_type,
        time_window_hours=time_window_hours
    )
    
    return [
        RetryStatistics(entity_type=entity, **entity_stats)
        for entity, entity_stats in stats.items()
    ]


@router.get("/service-health/{service_name}")
async def get_service_health_metrics(
    service_name: str,
    time_window_hours: int = Query(24, ge=1, le=168),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get detailed health metrics for a specific service"""
    
    async with db.acquire() as conn:
        # Get service health metrics
        metrics = await conn.fetch(
            """
            SELECT 
                window_start,
                window_end,
                request_count,
                success_count,
                failure_count,
                timeout_count,
                avg_response_time_ms,
                p95_response_time_ms,
                p99_response_time_ms,
                error_breakdown
            FROM service_health_metrics
            WHERE service_name = $1
            AND window_start >= NOW() - INTERVAL '%s hours'
            ORDER BY window_start DESC
            """,
            service_name,
            time_window_hours
        )
        
        return {
            "service_name": service_name,
            "time_window_hours": time_window_hours,
            "metrics": [dict(row) for row in metrics]
        }


@router.post("/error-categories/{error_code}/update")
async def update_error_category(
    error_code: str,
    updates: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Update error category configuration"""
    
    retry_manager = RetryManager(db)
    await retry_manager.update_error_category(error_code, updates)
    
    return {
        "error_code": error_code,
        "message": "Error category updated successfully",
        "updates": updates
    }


@router.get("/pipeline/{pipeline_id}/metrics")
async def get_pipeline_metrics(
    pipeline_id: UUID,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
    settings=Depends(get_settings)
):
    """Get comprehensive metrics for a pipeline execution"""
    
    pipeline_service = PipelineService(settings, db)
    metrics = await pipeline_service.get_pipeline_metrics(pipeline_id)
    
    return {
        "pipeline_id": pipeline_id,
        "timestamp": datetime.utcnow(),
        "metrics": metrics
    }


@router.get("/serp-batches")
async def get_serp_batch_status(
    current_user: dict = Depends(get_current_user),
    settings=Depends(get_settings)
):
    """Get Scale SERP batch status from external API"""
    
    try:
        import httpx
        api_key = settings.SCALE_SERP_API_KEY
        
        if not api_key:
            return {"error": "Scale SERP API key not configured"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.scaleserp.com/batches?api_key={api_key}"
            )
            
            if response.status_code == 200:
                batch_data = response.json()
                
                # Filter to recent Cylvy batches
                cylvy_batches = []
                for batch in batch_data.get('batches', []):
                    if 'Cylvy' in batch.get('name', '') or 'Direct Test' in batch.get('name', ''):
                        cylvy_batches.append({
                            'id': batch.get('id'),
                            'name': batch.get('name'),
                            'status': batch.get('status'),
                            'searches_total_count': batch.get('searches_total_count', 0),
                            'results_count': batch.get('results_count', 0),
                            'created_at': batch.get('created_at'),
                            'last_run': batch.get('last_run')
                        })
                
                return {
                    "success": True,
                    "total_batches": len(batch_data.get('batches', [])),
                    "cylvy_batches": cylvy_batches,
                    "timestamp": datetime.utcnow()
                }
            else:
                return {
                    "success": False,
                    "error": f"Scale SERP API error: {response.status_code}",
                    "details": response.text[:200]
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/system/performance")
async def get_system_performance(
    time_window_minutes: int = Query(60, ge=5, le=1440),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get system-wide performance metrics"""
    
    async with db.acquire() as conn:
        # Get pipeline performance
        pipeline_perf = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_pipelines,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
            FROM pipeline_executions
            WHERE started_at >= NOW() - INTERVAL '%s minutes'
            """,
            time_window_minutes
        )
        
        # Get API performance
        api_perf = await conn.fetch(
            """
            SELECT 
                api_name,
                COUNT(*) as request_count,
                AVG(duration_ms) as avg_duration_ms,
                MAX(duration_ms) as max_duration_ms
            FROM api_usage
            WHERE created_at >= NOW() - INTERVAL '%s minutes'
            GROUP BY api_name
            """,
            time_window_minutes
        )
        
        return {
            "time_window_minutes": time_window_minutes,
            "pipeline_performance": dict(pipeline_perf) if pipeline_perf else {},
            "api_performance": [dict(row) for row in api_perf],
            "timestamp": datetime.utcnow()
        }


@router.get("/serp-batches", response_model=SerpBatchesResponse)
async def get_serp_batches(
    limit: int = 20,
    include_completed: bool = True,
    current_user: dict = Depends(get_current_user),
    settings=Depends(get_settings),
    db=Depends(get_db)
):
    """Get recent SERP batch statuses from database and Scale SERP API"""
    import json
    from loguru import logger
    
    try:
        cylvy_batches = []
        
        # Get recent batch IDs from pipeline executions
        async with db.acquire() as conn:
            recent_batches = await conn.fetch("""
                SELECT DISTINCT 
                    phase_results->'serp_collection'->'content_type_results' as batch_data,
                    created_at
                FROM pipeline_executions
                WHERE phase_results->'serp_collection' IS NOT NULL
                  AND created_at > NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
            
            # Extract batch IDs from the results
            batch_ids = []
            for row in recent_batches:
                if row['batch_data']:
                    batch_data = json.loads(row['batch_data']) if isinstance(row['batch_data'], str) else row['batch_data']
                    for content_type, result in batch_data.items():
                        if isinstance(result, dict) and result.get('batch_id'):
                            batch_ids.append({
                                'batch_id': result['batch_id'],
                                'content_type': content_type,
                                'created_at': row['created_at']
                            })
        
        # Query Scale SERP API for batch details if we have API key
        if settings.SCALE_SERP_API_KEY and batch_ids:
            import httpx
            async with httpx.AsyncClient() as client:
                for batch_info in batch_ids[:limit]:  # Limit API calls
                    try:
                        # Get batch details
                        batch_response = await client.get(
                            f"https://api.scaleserp.com/batches/{batch_info['batch_id']}",
                            params={"api_key": settings.SCALE_SERP_API_KEY},
                            timeout=10.0
                        )
                        
                        if batch_response.status_code == 200:
                            batch_data = batch_response.json().get('batch', {})
                            
                            # Get result sets for this batch
                            results_response = await client.get(
                                f"https://api.scaleserp.com/batches/{batch_info['batch_id']}/results",
                                params={"api_key": settings.SCALE_SERP_API_KEY},
                                timeout=10.0
                            )
                            
                            result_sets = []
                            if results_response.status_code == 200:
                                result_sets = results_response.json().get('results', [])
                            
                            cylvy_batches.append(SerpBatch(
                                id=batch_data.get('id', batch_info['batch_id']),
                                name=batch_data.get('name', f"Batch {batch_info['batch_id']}"),
                                status=batch_data.get('status', 'unknown'),
                                searches_total_count=batch_data.get('searches_total_count', 0),
                                results_count=len(result_sets),
                                created_at=batch_info['created_at'],
                                last_run=result_sets[0].get('ended_at') if result_sets else None,
                                content_type=batch_info['content_type'],
                                result_sets=result_sets[:5]  # Include first 5 result sets
                            ))
                            
                    except Exception as e:
                        logger.warning(f"Failed to fetch batch {batch_info['batch_id']}: {e}")
                        # Add partial data
                        cylvy_batches.append(SerpBatch(
                            id=batch_info['batch_id'],
                            name=f"{batch_info['content_type'].title()} Batch",
                            status="unknown",
                            searches_total_count=0,
                            results_count=0,
                            created_at=batch_info['created_at'],
                            content_type=batch_info['content_type']
                        ))
        
        return SerpBatchesResponse(
            cylvy_batches=cylvy_batches,
            third_party_batches=[]
        )
    except Exception as e:
        logger.error(f"Error fetching SERP batches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Add the monitoring router to the API
def include_router(api_router):
    """Include monitoring router in the main API router"""
    api_router.include_router(router)
