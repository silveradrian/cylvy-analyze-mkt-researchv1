"""Pipeline monitoring endpoints for real-time tracking"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from app.core.auth import get_current_user
from app.core.database import db_pool
from app.models.auth import User
from loguru import logger

router = APIRouter()


async def get_db():
    """Get database connection"""
    async with db_pool.acquire() as connection:
        yield connection


@router.get("/monitoring", response_model=Dict[str, Any])
async def get_pipeline_monitoring_data(
    current_user: Optional[User] = Depends(get_current_user),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get comprehensive pipeline monitoring data"""
    try:
        # Simple query to get recent pipelines
        query = """
            SELECT 
                id,
                status,
                mode,
                started_at,
                completed_at,
                keywords_processed,
                serp_results_collected,
                companies_enriched,
                videos_enriched,
                content_analyzed,
                landscapes_calculated
            FROM pipeline_executions
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
            LIMIT 20
        """
        
        results = await db.fetch(query)
        pipelines = []
        
        for row in results:
            # Determine current phase and actual status based on metrics
            current_phase = 'pending'
            phases_completed = []
            
            if row['keywords_processed'] > 0:
                phases_completed.append('keyword_metrics')
                current_phase = 'serp_collection'
            
            if row['serp_results_collected'] > 0:
                phases_completed.append('serp_collection')
                current_phase = 'company_enrichment'
                
            if row['companies_enriched'] > 0:
                phases_completed.append('company_enrichment')
                current_phase = 'video_enrichment'
                
            if row['videos_enriched'] > 0:
                phases_completed.append('video_enrichment')
                current_phase = 'content_analysis'
                
            if row['content_analyzed'] > 0:
                phases_completed.append('content_analysis')
                current_phase = 'dsi_calculation'
                
            if row['landscapes_calculated'] > 0:
                phases_completed.append('dsi_calculation')
                current_phase = 'completed'
            
            if row['status'] == 'completed':
                current_phase = 'completed'
            elif row['status'] == 'failed':
                current_phase = 'failed'
            
            # Build phases based on counts
            phases = {
                'keyword_metrics': {
                    'status': 'completed' if 'keyword_metrics' in phases_completed else ('running' if current_phase == 'keyword_metrics' else 'pending'),
                    'progress': 100 if 'keyword_metrics' in phases_completed else (50 if current_phase == 'keyword_metrics' else 0),
                    'itemsProcessed': row['keywords_processed'],
                    'totalItems': max(row['keywords_processed'], 5),
                    'startTime': start_time.isoformat() if current_phase == 'keyword_metrics' or 'keyword_metrics' in phases_completed else None
                },
                'serp_collection': {
                    'status': 'completed' if 'serp_collection' in phases_completed else ('running' if current_phase == 'serp_collection' else 'pending'),
                    'progress': 100 if 'serp_collection' in phases_completed else (50 if current_phase == 'serp_collection' else 0),
                    'itemsProcessed': row['serp_results_collected'],
                    'totalItems': max(row['serp_results_collected'], row['keywords_processed'] * 5) if row['keywords_processed'] > 0 else 25,
                    'startTime': start_time.isoformat() if current_phase == 'serp_collection' or 'serp_collection' in phases_completed else None
                },
                'company_enrichment': {
                    'status': 'completed' if 'company_enrichment' in phases_completed else ('running' if current_phase == 'company_enrichment' else 'pending'),
                    'progress': 100 if 'company_enrichment' in phases_completed else (50 if current_phase == 'company_enrichment' else 0),
                    'itemsProcessed': row['companies_enriched'],
                    'totalItems': max(row['companies_enriched'], 10),
                    'startTime': start_time.isoformat() if current_phase == 'company_enrichment' or 'company_enrichment' in phases_completed else None
                },
                'video_enrichment': {
                    'status': 'completed' if 'video_enrichment' in phases_completed else ('running' if current_phase == 'video_enrichment' else 'pending'),
                    'progress': 100 if 'video_enrichment' in phases_completed else (50 if current_phase == 'video_enrichment' else 0),
                    'itemsProcessed': row['videos_enriched'],
                    'totalItems': max(row['videos_enriched'], 10),
                    'startTime': start_time.isoformat() if current_phase == 'video_enrichment' or 'video_enrichment' in phases_completed else None
                },
                'content_analysis': {
                    'status': 'completed' if 'content_analysis' in phases_completed else ('running' if current_phase == 'content_analysis' else 'pending'),
                    'progress': 100 if 'content_analysis' in phases_completed else (50 if current_phase == 'content_analysis' else 0),
                    'itemsProcessed': row['content_analyzed'],
                    'totalItems': max(row['content_analyzed'], 10),
                    'startTime': start_time.isoformat() if current_phase == 'content_analysis' or 'content_analysis' in phases_completed else None
                },
                'dsi_calculation': {
                    'status': 'completed' if 'dsi_calculation' in phases_completed else ('running' if current_phase == 'dsi_calculation' else 'pending'),
                    'progress': 100 if 'dsi_calculation' in phases_completed else (50 if current_phase == 'dsi_calculation' else 0),
                    'itemsProcessed': row['landscapes_calculated'],
                    'totalItems': max(row['landscapes_calculated'], 10),
                    'startTime': start_time.isoformat() if current_phase == 'dsi_calculation' or 'dsi_calculation' in phases_completed else None
                }
            }
            
            # Calculate elapsed time
            elapsed_ms = 0
            if row['started_at']:
                from datetime import timezone
                # Make sure both times are timezone-aware
                start_time = row['started_at']
                if row['completed_at']:
                    end_time = row['completed_at']
                else:
                    # Use timezone-aware UTC now
                    end_time = datetime.now(timezone.utc)
                
                # Only calculate if both are timezone-aware
                if start_time.tzinfo is not None and end_time.tzinfo is not None:
                    elapsed_ms = int((end_time - start_time).total_seconds() * 1000)
            
            pipeline = {
                'id': str(row['id']),
                'status': row['status'],
                'mode': row['mode'] or 'manual',
                'startTime': row['started_at'].isoformat() if row['started_at'] else None,
                'endTime': row['completed_at'].isoformat() if row['completed_at'] else None,
                'contentTypes': ['organic', 'news', 'video'],
                'regions': ['US', 'UK', 'DE', 'SA', 'VN'],
                'currentPhase': current_phase,
                'phases': phases,
                'elapsedMs': elapsed_ms,
                'metrics': {
                    'totalKeywords': max(row['keywords_processed'], 5),
                    'totalSearches': row['serp_results_collected'] if row['serp_results_collected'] > 0 else (row['keywords_processed'] * 5 if row['keywords_processed'] > 0 else 25),
                    'resultsCollected': row['serp_results_collected'],
                    'domainsEnriched': row['companies_enriched'],
                    'videosAnalyzed': row['videos_enriched'],
                    'contentAnalyzed': row['content_analyzed']
                }
            }
            
            pipelines.append(pipeline)
        
        return {
            'pipelines': pipelines,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get monitoring data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitoring data: {str(e)}"
        )


@router.post("/{pipeline_id}/pause")
async def pause_pipeline(
    pipeline_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Pause a running pipeline"""
    # TODO: Implement pause functionality
    return {"message": "Pipeline pause not yet implemented", "pipeline_id": str(pipeline_id)}


@router.post("/{pipeline_id}/resume")
async def resume_pipeline(
    pipeline_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Resume a paused pipeline"""
    # TODO: Implement resume functionality
    return {"message": "Pipeline resume not yet implemented", "pipeline_id": str(pipeline_id)}


@router.post("/{pipeline_id}/cancel")
async def cancel_pipeline(
    pipeline_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Cancel a running pipeline"""
    try:
        # Update pipeline status to cancelled
        await db.execute(
            """
            UPDATE pipeline_executions 
            SET status = 'cancelled', completed_at = NOW()
            WHERE id = $1 AND status = 'running'
            """,
            pipeline_id
        )
        
        return {"message": "Pipeline cancelled successfully", "pipeline_id": str(pipeline_id)}
        
    except Exception as e:
        logger.error(f"Failed to cancel pipeline {pipeline_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel pipeline: {str(e)}"
        )


@router.post("/{pipeline_id}/delete")
async def delete_pipeline_data(
    pipeline_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Delete all data associated with a pipeline"""
    try:
        # Delete pipeline state first (due to foreign key)
        await db.execute(
            "DELETE FROM pipeline_state WHERE pipeline_execution_id = $1",
            pipeline_id
        )
        
        # Delete checkpoints
        await db.execute(
            "DELETE FROM pipeline_checkpoints WHERE pipeline_execution_id = $1",
            pipeline_id
        )
        
        # Delete the pipeline execution record
        await db.execute(
            "DELETE FROM pipeline_executions WHERE id = $1",
            pipeline_id
        )
        
        return {"message": "Pipeline data deleted successfully", "pipeline_id": str(pipeline_id)}
        
    except Exception as e:
        logger.error(f"Failed to delete pipeline {pipeline_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete pipeline data: {str(e)}"
        )


@router.get("/{pipeline_id}/logs")
async def get_pipeline_logs(
    pipeline_id: UUID,
    limit: int = 100,
    offset: int = 0,
    db: asyncpg.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """Get logs for a specific pipeline - returns simulated logs for now"""
    try:
        # Check if pipeline exists
        pipeline = await db.fetchrow(
            "SELECT * FROM pipeline_executions WHERE id = $1",
            pipeline_id
        )
        
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # For now, return simulated log entries based on pipeline status
        base_time = pipeline['started_at'] or datetime.now(timezone.utc)
        logs = []
        
        # Generate log entries based on pipeline metrics
        if pipeline['keywords_processed'] > 0:
            logs.append({
                "level": "INFO",
                "message": f"Processed {pipeline['keywords_processed']} keywords",
                "timestamp": base_time.isoformat(),
                "phase": "keyword_metrics"
            })
        
        if pipeline['serp_results_collected'] > 0:
            logs.append({
                "level": "INFO", 
                "message": f"Collected {pipeline['serp_results_collected']} SERP results",
                "timestamp": (base_time + timedelta(seconds=30)).isoformat(),
                "phase": "serp_collection"
            })
        
        if pipeline['companies_enriched'] > 0:
            logs.append({
                "level": "INFO",
                "message": f"Enriched {pipeline['companies_enriched']} companies",
                "timestamp": (base_time + timedelta(seconds=60)).isoformat(),
                "phase": "company_enrichment"
            })
        
        if pipeline['videos_enriched'] > 0:
            logs.append({
                "level": "INFO",
                "message": f"Enriched {pipeline['videos_enriched']} videos",
                "timestamp": (base_time + timedelta(seconds=90)).isoformat(),
                "phase": "video_enrichment"
            })
        
        if pipeline['content_analyzed'] > 0:
            logs.append({
                "level": "INFO",
                "message": f"Analyzed {pipeline['content_analyzed']} content pieces",
                "timestamp": (base_time + timedelta(seconds=120)).isoformat(),
                "phase": "content_analysis"
            })
        
        # Add status log
        if pipeline['status'] == 'failed':
            logs.append({
                "level": "ERROR",
                "message": "Pipeline failed - check error logs",
                "timestamp": (pipeline['completed_at'] or datetime.now(timezone.utc)).isoformat(),
                "phase": "pipeline"
            })
        elif pipeline['status'] == 'completed':
            logs.append({
                "level": "INFO",
                "message": "Pipeline completed successfully",
                "timestamp": (pipeline['completed_at'] or datetime.now(timezone.utc)).isoformat(),
                "phase": "pipeline"
            })
        else:
            logs.append({
                "level": "INFO",
                "message": f"Pipeline is {pipeline['status']}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phase": "pipeline"
            })
        
        # Sort logs by timestamp
        logs.sort(key=lambda x: x['timestamp'])
        
        # Apply pagination
        paginated_logs = logs[offset:offset + limit]
        
        return {
            "logs": paginated_logs,
            "total": len(logs),
            "limit": limit,
            "offset": offset,
            "pipeline_id": str(pipeline_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get logs for pipeline {pipeline_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get logs: {str(e)}"
        )