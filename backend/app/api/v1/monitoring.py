"""
Simple, focused monitoring endpoints for pipeline tracking
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
import asyncpg
from loguru import logger

from app.core.database import db_pool

router = APIRouter()


async def get_db():
    """Get database connection"""
    async with db_pool.acquire() as connection:
        yield connection


@router.get("/pipelines")
async def get_pipelines(
    status_filter: Optional[str] = Query(None, description="Filter by status: active, completed, failed"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get list of pipelines with basic info"""
    try:
        # Build query based on filter
        if status_filter == "active":
            status_condition = "AND status IN ('pending', 'running')"
        elif status_filter == "completed":
            status_condition = "AND status = 'completed'"
        elif status_filter == "failed":
            status_condition = "AND status = 'failed'"
        else:
            status_condition = ""
        
        query = f"""
            SELECT 
                pe.id,
                pe.status,
                pe.mode,
                pe.started_at,
                pe.completed_at,
                pe.keywords_processed,
                pe.serp_results_collected,
                pe.companies_enriched,
                pe.videos_enriched,
                pe.content_analyzed,
                pe.errors,
                -- Get current phase
                (
                    SELECT phase_name 
                    FROM pipeline_phase_status pps 
                    WHERE pps.pipeline_execution_id = pe.id 
                    AND pps.status = 'running' 
                    LIMIT 1
                ) as current_phase,
                -- Get phase counts
                (
                    SELECT COUNT(*) 
                    FROM pipeline_phase_status pps 
                    WHERE pps.pipeline_execution_id = pe.id 
                    AND pps.status = 'completed'
                ) as phases_completed,
                (
                    SELECT COUNT(*) 
                    FROM pipeline_phase_status pps 
                    WHERE pps.pipeline_execution_id = pe.id
                ) as total_phases
            FROM pipeline_executions pe
            WHERE created_at > NOW() - INTERVAL '48 hours'
            {status_condition}
            ORDER BY started_at DESC
            LIMIT $1 OFFSET $2
        """
        
        rows = await db.fetch(query, limit, offset)
        
        pipelines = []
        for row in rows:
            pipeline = dict(row)
            
            # Calculate duration and progress
            if pipeline['completed_at'] and pipeline['started_at']:
                duration = (pipeline['completed_at'] - pipeline['started_at']).total_seconds()
                pipeline['duration_seconds'] = duration
            elif pipeline['started_at']:
                duration = (datetime.now(timezone.utc) - pipeline['started_at'].replace(tzinfo=timezone.utc)).total_seconds()
                pipeline['duration_seconds'] = duration
            
            # Calculate overall progress
            if pipeline['total_phases'] > 0:
                pipeline['progress_percentage'] = int((pipeline['phases_completed'] / pipeline['total_phases']) * 100)
            else:
                pipeline['progress_percentage'] = 0
            
            # Determine if active
            pipeline['is_active'] = pipeline['status'] in ('pending', 'running')
            
            pipelines.append(pipeline)
        
        # Separate active and recent
        active_pipelines = [p for p in pipelines if p['is_active']]
        recent_pipelines = [p for p in pipelines if not p['is_active']]
        
        return {
            "active_pipelines": active_pipelines,
            "recent_pipelines": recent_pipelines,
            "total_active": len(active_pipelines)
        }
        
    except Exception as e:
        logger.error(f"Error getting pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/{pipeline_id}/phases")
async def get_pipeline_phases(
    pipeline_id: UUID,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed phase information for a pipeline"""
    try:
        # Get pipeline basic info
        pipeline_query = """
            SELECT 
                id, status, mode, started_at, completed_at,
                keywords_processed, serp_results_collected,
                companies_enriched, videos_enriched,
                content_analyzed, errors
            FROM pipeline_executions
            WHERE id = $1
        """
        pipeline = await db.fetchrow(pipeline_query, pipeline_id)
        
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # Get phase details
        phases_query = """
            SELECT 
                phase_name,
                status,
                started_at,
                completed_at,
                result_data,
                error_message,
                retry_count,
                EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            ORDER BY created_at
        """
        phases_rows = await db.fetch(phases_query, pipeline_id)
        
        phases = []
        for row in phases_rows:
            phase = dict(row)
            
            # Parse result data for metrics
            if phase['result_data']:
                result = phase['result_data']
                if isinstance(result, dict):
                    phase['metrics'] = {
                        'items_processed': result.get('items_processed', 0),
                        'total_items': result.get('total_items', 0),
                        'success_rate': result.get('success_rate', 0),
                        'errors_count': len(result.get('errors', []))
                    }
            
            # Calculate progress for running phases
            if phase['status'] == 'running' and phase['result_data']:
                result = phase['result_data']
                if isinstance(result, dict):
                    processed = result.get('items_processed', 0)
                    total = result.get('total_items', 1)
                    phase['progress_percentage'] = int((processed / total) * 100) if total > 0 else 0
            
            phases.append(phase)
        
        # Phase dependencies for visualization
        phase_dependencies = {
            "keyword_metrics": [],
            "serp_collection": ["keyword_metrics"],
            "company_enrichment_serp": ["serp_collection"],
            "youtube_enrichment": ["serp_collection"],
            "content_scraping": ["serp_collection"],
            "company_enrichment_youtube": ["youtube_enrichment", "company_enrichment_serp"],
            "content_analysis": ["content_scraping", "company_enrichment_serp"],
            "dsi_calculation": ["content_analysis", "company_enrichment_youtube"]
        }
        
        return {
            "pipeline": dict(pipeline),
            "phases": phases,
            "phase_dependencies": phase_dependencies,
            "current_phase": next((p['phase_name'] for p in phases if p['status'] == 'running'), None)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pipeline phases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/{pipeline_id}/activity")
async def get_pipeline_activity(
    pipeline_id: UUID,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get current processing activity for a pipeline"""
    try:
        # Get current phase
        current_phase_query = """
            SELECT 
                phase_name, 
                status, 
                started_at,
                result_data
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1 
            AND status = 'running'
            LIMIT 1
        """
        current_phase = await db.fetchrow(current_phase_query, pipeline_id)
        
        if not current_phase:
            return {
                "is_active": False,
                "current_phase": None,
                "current_items": [],
                "processing_rate": 0
            }
        
        phase_name = current_phase['phase_name']
        
        # Get items being processed from pipeline_state table
        items_query = """
            SELECT 
                item_type,
                item_id,
                status,
                attempts,
                last_error,
                updated_at
            FROM pipeline_state
            WHERE pipeline_execution_id = $1
            AND phase = $2
            AND status IN ('processing', 'queued')
            ORDER BY updated_at DESC
            LIMIT 20
        """
        items = await db.fetch(items_query, pipeline_id, phase_name)
        
        # Calculate processing rate (items per minute)
        rate_query = """
            SELECT 
                COUNT(*) as completed_count
            FROM pipeline_state
            WHERE pipeline_execution_id = $1
            AND phase = $2
            AND status = 'completed'
            AND updated_at > NOW() - INTERVAL '1 minute'
        """
        rate_result = await db.fetchrow(rate_query, pipeline_id, phase_name)
        processing_rate = rate_result['completed_count'] if rate_result else 0
        
        # Get queue size
        queue_query = """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'queued') as queued,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) as total
            FROM pipeline_state
            WHERE pipeline_execution_id = $1
            AND phase = $2
        """
        queue_stats = await db.fetchrow(queue_query, pipeline_id, phase_name)
        
        # Estimate time remaining
        if processing_rate > 0 and queue_stats['queued'] > 0:
            minutes_remaining = queue_stats['queued'] / processing_rate
            estimated_completion = datetime.now(timezone.utc) + timedelta(minutes=minutes_remaining)
        else:
            estimated_completion = None
        
        return {
            "is_active": True,
            "current_phase": phase_name,
            "phase_started_at": current_phase['started_at'],
            "current_items": [dict(item) for item in items],
            "processing_rate": processing_rate,
            "queue_stats": dict(queue_stats),
            "estimated_completion": estimated_completion
        }
        
    except Exception as e:
        logger.error(f"Error getting pipeline activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/{pipeline_id}/metrics")
async def get_pipeline_metrics(
    pipeline_id: UUID,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get real-time metrics for a pipeline"""
    try:
        # Get pipeline metrics
        metrics_query = """
            SELECT 
                keywords_processed,
                keywords_with_metrics,
                serp_results_collected,
                companies_enriched,
                videos_enriched,
                content_analyzed,
                landscapes_calculated,
                phase_results,
                api_calls_made,
                estimated_cost
            FROM pipeline_executions
            WHERE id = $1
        """
        metrics = await db.fetchrow(metrics_query, pipeline_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # Get phase-specific metrics
        phase_metrics_query = """
            SELECT 
                phase_name,
                result_data,
                completed_at
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            AND status = 'completed'
            ORDER BY completed_at DESC
        """
        phase_results = await db.fetch(phase_metrics_query, pipeline_id)
        
        # Extract detailed metrics from phase results
        detailed_metrics = {}
        for phase in phase_results:
            if phase['result_data'] and isinstance(phase['result_data'], dict):
                phase_name = phase['phase_name']
                result = phase['result_data']
                
                if phase_name == 'serp_collection':
                    detailed_metrics['serp_by_type'] = result.get('content_type_results', {})
                elif phase_name == 'content_scraping':
                    detailed_metrics['scraping_success_rate'] = result.get('success_rate', 0)
                    detailed_metrics['urls_scraped'] = result.get('urls_scraped', 0)
                elif phase_name == 'content_analysis':
                    detailed_metrics['analysis_success_rate'] = result.get('success_rate', 0)
        
        return {
            "basic_metrics": dict(metrics),
            "detailed_metrics": detailed_metrics,
            "last_updated": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pipeline metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))