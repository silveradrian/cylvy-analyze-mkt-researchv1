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
            
            # Establish a safe start_time for phase timing references
            start_time = row['started_at'] or datetime.now(timezone.utc)

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


@router.post("/{pipeline_id}/continue_phase")
async def continue_phase(
    pipeline_id: UUID,
    payload: Dict[str, Any],
    db=Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Signal a phase to continue (set to running if currently pending/failed)."""
    try:
        phase = (payload or {}).get('phase')
        if not phase:
            raise HTTPException(status_code=400, detail='phase is required')
        row = await db.fetchrow(
            """
            UPDATE pipeline_phase_status
            SET status = 'running', started_at = COALESCE(started_at, NOW()), updated_at = NOW()
            WHERE pipeline_execution_id = $1 AND phase_name = $2
            AND status IN ('pending', 'failed', 'blocked')
            RETURNING id, phase_name, status
            """,
            pipeline_id,
            phase,
        )
        if not row:
            raise HTTPException(status_code=404, detail='Phase not found or already running/completed')
        return {'message': 'Phase started', 'phase': row['phase_name'], 'status': row['status']}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"continue_phase error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pipeline_id}/restart_phase")
async def restart_phase(
    pipeline_id: UUID,
    payload: Dict[str, Any],
    db=Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Restart a phase (reset timestamps and set status to pending) and reactivate pipeline."""
    try:
        phase = (payload or {}).get('phase')
        fresh_analysis = (payload or {}).get('fresh_analysis', False)
        if not phase:
            raise HTTPException(status_code=400, detail='phase is required')
        
        logger.info(f"🔄 Restarting phase {phase} for pipeline {pipeline_id} (fresh_analysis: {fresh_analysis})")
        
        # Handle fresh analysis for content_analysis phase
        if fresh_analysis and phase == 'content_analysis':
            logger.info(f"🧹 FRESH ANALYSIS: Clearing existing content analysis data for pipeline {pipeline_id}")
            
            # Clear existing content analysis data
            # Delete analysis data for this specific pipeline
            # optimized_content_analysis uses project_id (NULL for pipeline analyses)
            # We need to identify analyses from this pipeline by joining with scraped_content
            await db.execute(
                """
                DELETE FROM optimized_content_analysis 
                WHERE project_id IS NULL 
                AND url IN (
                    SELECT url FROM scraped_content 
                    WHERE pipeline_execution_id = $1
                )
                """,
                pipeline_id
            )
            
            await db.execute(
                """
                DELETE FROM optimized_dimension_analysis 
                WHERE analysis_id IN (
                    SELECT oca.id FROM optimized_content_analysis oca
                    JOIN scraped_content sc ON oca.url = sc.url
                    WHERE oca.project_id IS NULL 
                    AND sc.pipeline_execution_id = $1
                )
                """,
                pipeline_id
            )
            
            logger.info(f"✅ Cleared existing content analysis data for fresh analysis")
        
        # Reset phase status to pending
        row = await db.fetchrow(
            """
            UPDATE pipeline_phase_status
            SET status = 'pending', started_at = NULL, completed_at = NULL, error_message = NULL, updated_at = NOW()
            WHERE pipeline_execution_id = $1 AND phase_name = $2
            RETURNING id, phase_name, status
            """,
            pipeline_id,
            phase,
        )
        if not row:
            raise HTTPException(status_code=404, detail='Phase not found for pipeline')
        
        # CRITICAL FIX: Reactivate pipeline so it processes pending phases
        pipeline_updated = await db.fetchrow(
            """
            UPDATE pipeline_executions
            SET status = 'running', completed_at = NULL, updated_at = NOW()
            WHERE id = $1 AND status = 'completed'
            RETURNING id, status
            """,
            pipeline_id
        )
        
        if pipeline_updated:
            logger.info(f"Reactivated pipeline {pipeline_id} for phase restart: {phase}")
        
        # Special handling for content analysis restart
        if phase == 'content_analysis':
            # Import here to avoid circular import
            from app.services.pipeline.pipeline_resumption import PipelineResumptionService
            from app.services.pipeline.pipeline_service import PipelineService
            from app.core.database import db_pool
            from app.core.config import get_settings
            
            try:
                # Get services
                settings = get_settings()
                pipeline_service = PipelineService(settings, db_pool)
                resumption_service = PipelineResumptionService(pipeline_service)
                
                # Start content analysis with fresh analysis flag
                logger.info(f"🚀 Manually triggering content analysis restart for pipeline {pipeline_id}")
                await resumption_service._resume_content_analysis(pipeline_id, fresh_analysis=fresh_analysis)
                
            except Exception as e:
                logger.error(f"Failed to trigger content analysis restart: {e}")
        
        message = 'Phase reset to pending and pipeline reactivated'
        if fresh_analysis and phase == 'content_analysis':
            message = 'Fresh content analysis started - previous data cleared, all content will be reprocessed'
        
        return {
            'message': message,
            'phase': row['phase_name'], 
            'status': row['status'],
            'pipeline_reactivated': pipeline_updated is not None,
            'fresh_analysis': fresh_analysis
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"restart_phase error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/monitoring/pipelines")
async def list_pipelines(
    limit: int = 20,
    hours: int = 24,
    db=Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        rows = await db.fetch(
            """
            SELECT id, status, mode, started_at, completed_at,
                   keywords_processed, serp_results_collected,
                   companies_enriched, videos_enriched, content_analyzed,
                   landscapes_calculated
            FROM pipeline_executions
            WHERE created_at > NOW() - ($1 || ' hours')::interval
            ORDER BY created_at DESC
            LIMIT $2
            """,
            hours,
            limit,
        )
        def to_item(r):
            elapsed_ms = 0
            if r['started_at']:
                end_t = r['completed_at'] or datetime.now(timezone.utc)
                if r['started_at'].tzinfo and end_t.tzinfo:
                    elapsed_ms = int((end_t - r['started_at']).total_seconds() * 1000)
            return {
                'id': str(r['id']),
                'status': r['status'],
                'mode': r['mode'] or 'manual',
                'started_at': r['started_at'].isoformat() if r['started_at'] else None,
                'completed_at': r['completed_at'].isoformat() if r['completed_at'] else None,
                'progress_percentage': 0,
                'phases_completed': 0,
                'total_phases': 7,
                'duration_seconds': int(elapsed_ms / 1000) if elapsed_ms else None,
                'keywords_processed': r['keywords_processed'] or 0,
                'serp_results_collected': r['serp_results_collected'] or 0,
                'companies_enriched': r['companies_enriched'] or 0,
                'videos_enriched': r['videos_enriched'] or 0,
                'content_analyzed': r['content_analyzed'] or 0,
                'is_active': r['status'] in ('running', 'processing')
            }
        items = [to_item(r) for r in rows]
        active = [i for i in items if i['is_active']]
        recent = [i for i in items if not i['is_active']]
        return { 'active_pipelines': active, 'recent_pipelines': recent }
    except Exception as e:
        logger.error(f"list_pipelines error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/pipeline/{pipeline_id}/phases")
async def get_pipeline_phases(
    pipeline_id: UUID,
    db=Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Return per-phase status, timings, metrics, and simple ETA for a pipeline."""
    try:
        pe = await db.fetchrow("SELECT * FROM pipeline_executions WHERE id=$1", pipeline_id)
        if not pe:
            raise HTTPException(status_code=404, detail='Pipeline not found')

        # Load phase rows
        phase_rows = await db.fetch(
            """
            SELECT phase_name, status, started_at, completed_at, error_message, result_data
            FROM pipeline_phase_status
            WHERE pipeline_execution_id=$1
            ORDER BY created_at
            """,
            pipeline_id,
        )
        phase_map = {r['phase_name']: r for r in phase_rows}

        def elapsed_eta(row, processed: int, total: int):
            elapsed = 0
            if row and row['started_at']:
                end_t = row['completed_at'] or datetime.now(timezone.utc)
                if row['started_at'].tzinfo and end_t.tzinfo:
                    elapsed = int((end_t - row['started_at']).total_seconds())
            eta = None
            if total and processed is not None and total > 0 and processed >= 0:
                pct = max(0.01, min(0.99, processed / total)) if processed < total else 1.0
                if pct < 1.0 and elapsed > 0:
                    eta = int(elapsed * (1/pct - 1))
            return elapsed, eta

        phases_out: List[Dict[str, Any]] = []

        # 1) Keyword Metrics
        km = phase_map.get('keyword_metrics')
        km_processed = pe['keywords_processed'] or 0
        # Countries from schedule if available, fallback to default
        countries_row = await db.fetchrow("SELECT regions FROM pipeline_schedules WHERE is_active=true LIMIT 1")
        countries = len(countries_row['regions']) if countries_row and countries_row.get('regions') else 0
        km_elapsed, km_eta = elapsed_eta(km, km_processed, max(km_processed, 1))
        phases_out.append({
            'phase_name': 'keyword_metrics',
            'status': (km['status'] if km else ('completed' if km_processed > 0 else 'pending')),
            'started_at': km['started_at'].isoformat() if km and km['started_at'] else None,
            'completed_at': km['completed_at'].isoformat() if km and km['completed_at'] else None,
            'duration_seconds': km_elapsed or None,
            'eta_seconds': km_eta,
            'progress_percentage': 100 if km_processed > 0 else 0,
            'metrics': {
                'items_processed': km_processed,
                'total_items': km_processed,
                'success_rate': 100 if km_processed > 0 else 0,
                'errors_count': 0,
                'keywords': km_processed,
                'countries': countries
            }
        })

        # 2) SERP Collection
        serp = phase_map.get('serp_collection')
        serp_results = pe['serp_results_collected'] or 0
        # Get actual content type and region counts
        schedule_row = await db.fetchrow("SELECT regions, content_types FROM pipeline_schedules WHERE is_active=true LIMIT 1")
        regions_count = len(schedule_row['regions']) if schedule_row and schedule_row.get('regions') else 3
        content_types_count = len(schedule_row['content_types']) if schedule_row and schedule_row.get('content_types') else 3
        searches = (pe['keywords_processed'] or 0) * regions_count * content_types_count
        
        # Get batch statuses if available
        batch_info = {}
        try:
            batch_stats = await db.fetch(
                """SELECT content_type, status, COUNT(*) as count 
                   FROM serp_batch_coordinator_runs 
                   WHERE pipeline_execution_id=$1 
                   GROUP BY content_type, status""",
                pipeline_id
            )
            for row in batch_stats:
                ct = row['content_type']
                if ct not in batch_info:
                    batch_info[ct] = {}
                batch_info[ct][row['status']] = row['count']
        except Exception:
            # Table might not exist yet
            pass
        
        serp_elapsed, serp_eta = elapsed_eta(serp, serp_results, max(searches, 1))
        phases_out.append({
            'phase_name': 'serp_collection',
            'status': (serp['status'] if serp else ('completed' if serp_results > 0 else 'pending')),
            'started_at': serp['started_at'].isoformat() if serp and serp['started_at'] else None,
            'completed_at': serp['completed_at'].isoformat() if serp and serp['completed_at'] else None,
            'duration_seconds': serp_elapsed or None,
            'eta_seconds': serp_eta,
            'progress_percentage': min(100, int(100 * serp_results / max(searches, 1))) if searches else None,
            'metrics': {
                'items_processed': serp_results,
                'total_items': searches,
                'success_rate': 100 if searches and serp_results else 0,
                'errors_count': 0,
                'searches_expected': searches,
                'serps_collected': serp_results,
                'keywords': pe['keywords_processed'] or 0,
                'regions': regions_count,
                'content_types': content_types_count,
                'batch_status': batch_info
            }
        })

        # 3) Company Enrichment (SERP)
        ce = phase_map.get('company_enrichment_serp') or phase_map.get('company_enrichment')
        enriched = pe['companies_enriched'] or 0
        # total unique domains from latest SERP for this pipeline
        domains_row = await db.fetchrow(
            "SELECT COUNT(DISTINCT domain) AS c FROM serp_results WHERE pipeline_execution_id=$1 AND domain IS NOT NULL AND domain<>''",
            pipeline_id,
        )
        total_domains = domains_row['c'] if domains_row and domains_row.get('c') is not None else 0
        ce_elapsed, ce_eta = elapsed_eta(ce, enriched, max(total_domains, 1))
        phases_out.append({
            'phase_name': 'company_enrichment_serp',
            'status': (ce['status'] if ce else ('completed' if enriched > 0 else 'pending')),
            'started_at': ce['started_at'].isoformat() if ce and ce['started_at'] else None,
            'completed_at': ce['completed_at'].isoformat() if ce and ce['completed_at'] else None,
            'duration_seconds': ce_elapsed or None,
            'eta_seconds': ce_eta,
            'progress_percentage': min(100, int(100 * enriched / max(total_domains, 1))) if total_domains else None,
            'metrics': {
                'items_processed': enriched,
                'total_items': total_domains,
                'success_rate': int(100 * enriched / max(total_domains, 1)) if total_domains else 0,
                'errors_count': 0,
                'enriched_domains': enriched,
                'unique_domains': total_domains
            }
        })

        # 4) YouTube Metrics
        ye = phase_map.get('youtube_enrichment')
        videos = pe['videos_enriched'] or 0
        
        # Get total YouTube URLs and enrichment stats
        video_stats = await db.fetchrow(
            """SELECT 
                COUNT(DISTINCT sr.url) as total_video_urls,
                COUNT(DISTINCT vs.video_id) as enriched_videos,
                COUNT(DISTINCT vs.channel_id) as unique_channels,
                AVG(vs.view_count) as avg_views,
                AVG(vs.engagement_rate) as avg_engagement
            FROM serp_results sr
            LEFT JOIN video_snapshots vs ON sr.url = vs.video_url AND sr.pipeline_execution_id::text = vs.client_id
            WHERE sr.pipeline_execution_id = $1 AND sr.url LIKE '%youtube.com%'""",
            pipeline_id
        )
        
        total_videos = video_stats['total_video_urls'] or 0
        enriched_videos = video_stats['enriched_videos'] or 0
        unique_channels = video_stats['unique_channels'] or 0
        
        # Check for circuit breaker status
        circuit_breaker_status = 'unknown'
        ye_result_data = ye.get('result_data') if ye else None
        if ye_result_data:
            try:
                import json
                result_json = json.loads(ye_result_data) if isinstance(ye_result_data, str) else ye_result_data
                if 'errors' in result_json:
                    for error in result_json.get('errors', []):
                        if 'quota_exceeded' in str(error.get('error', '')):
                            circuit_breaker_status = 'quota_exceeded'
                            break
            except:
                pass
                
        ye_elapsed, ye_eta = elapsed_eta(ye, enriched_videos, max(total_videos, 1))
        phases_out.append({
            'phase_name': 'youtube_enrichment',
            'status': (ye['status'] if ye else ('completed' if videos > 0 else 'pending')),
            'started_at': ye['started_at'].isoformat() if ye and ye['started_at'] else None,
            'completed_at': ye['completed_at'].isoformat() if ye and ye['completed_at'] else None,
            'duration_seconds': ye_elapsed or None,
            'eta_seconds': ye_eta,
            'progress_percentage': min(100, int(100 * enriched_videos / max(total_videos, 1))) if total_videos else None,
            'metrics': {
                'items_processed': enriched_videos,
                'total_items': total_videos,
                'success_rate': int(100 * enriched_videos / max(total_videos, 1)) if total_videos else 0,
                'errors_count': max(0, total_videos - enriched_videos),
                'videos_found': total_videos,
                'videos_enriched': enriched_videos,
                'unique_channels': unique_channels,
                'avg_views': int(video_stats['avg_views']) if video_stats['avg_views'] else 0,
                'avg_engagement': round(float(video_stats['avg_engagement'] or 0), 2),
                'circuit_breaker': circuit_breaker_status
            }
        })

        # 5) Content Scraping
        cs = phase_map.get('content_scraping')
        
        # Get detailed scraping stats
        scraping_stats = await db.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT sc.url) FILTER (WHERE sc.status = 'completed') as completed,
                COUNT(DISTINCT sc.url) FILTER (WHERE sc.status = 'failed') as failed,
                COUNT(DISTINCT sc.url) FILTER (WHERE sc.status = 'pending') as pending,
                COUNT(DISTINCT sr.url) as total_urls,
                AVG(sc.word_count) FILTER (WHERE sc.status = 'completed') as avg_word_count,
                COUNT(DISTINCT sc.domain) FILTER (WHERE sc.status = 'completed') as unique_domains
            FROM serp_results sr
            LEFT JOIN scraped_content sc ON sr.url = sc.url AND sr.pipeline_execution_id = sc.pipeline_execution_id
            WHERE sr.pipeline_execution_id = $1 
            AND sr.serp_type IN ('organic','news') 
            AND sr.url IS NOT NULL AND sr.url <> ''
            """,
            pipeline_id,
        )
        
        scraped_completed = scraping_stats['completed'] or 0
        scraped_failed = scraping_stats['failed'] or 0
        scraped_pending = scraping_stats['pending'] or 0
        total_pages = scraping_stats['total_urls'] or 0
        avg_word_count = int(scraping_stats['avg_word_count']) if scraping_stats['avg_word_count'] else 0
        unique_domains = scraping_stats['unique_domains'] or 0
        
        cs_elapsed, cs_eta = elapsed_eta(cs, scraped_completed, max(total_pages, 1))
        phases_out.append({
            'phase_name': 'content_scraping',
            'status': (cs['status'] if cs else ('completed' if scraped_completed > 0 else 'pending')),
            'started_at': cs['started_at'].isoformat() if cs and cs['started_at'] else None,
            'completed_at': cs['completed_at'].isoformat() if cs and cs['completed_at'] else None,
            'duration_seconds': cs_elapsed or None,
            'eta_seconds': cs_eta,
            'progress_percentage': min(100, int(100 * scraped_completed / max(total_pages, 1))) if total_pages else None,
            'metrics': {
                'items_processed': scraped_completed,
                'total_items': total_pages,
                'success_rate': int(100 * scraped_completed / max(total_pages, 1)) if total_pages else 0,
                'errors_count': scraped_failed,
                'pages_scraped': scraped_completed,
                'pages_failed': scraped_failed,
                'pages_pending': scraped_pending,
                'unique_pages': total_pages,
                'unique_domains': unique_domains,
                'avg_word_count': avg_word_count,
                'scraping_rate': round(scraped_completed / cs_elapsed, 2) if cs_elapsed and cs_elapsed > 0 else 0
            }
        })

        # 6) YouTube Company / Channel Resolver
        ycr = phase_map.get('channel_company_resolver')
        resolved_row = await db.fetchrow(
            """SELECT COUNT(DISTINCT ycc.channel_id) AS c 
               FROM youtube_channel_companies ycc
               WHERE ycc.channel_id IN (
                   SELECT DISTINCT channel_id 
                   FROM video_snapshots vs
                   INNER JOIN serp_results sr ON sr.url = vs.video_url
                   WHERE sr.pipeline_execution_id = $1
                   AND vs.channel_id IS NOT NULL
               )
               AND ycc.company_domain IS NOT NULL""",
            pipeline_id,
        )
        resolved = resolved_row['c'] if resolved_row and resolved_row.get('c') is not None else 0
        total_channels_row = await db.fetchrow(
            """SELECT COUNT(DISTINCT channel_id) AS c 
               FROM video_snapshots vs
               INNER JOIN serp_results sr ON sr.url = vs.video_url
               WHERE sr.pipeline_execution_id = $1
               AND vs.channel_id IS NOT NULL""",
            pipeline_id,
        )
        total_channels = total_channels_row['c'] if total_channels_row and total_channels_row.get('c') is not None else 0
        success_rate = int(100 * resolved / max(total_channels, 1)) if total_channels else 0
        ycr_elapsed, ycr_eta = elapsed_eta(ycr, resolved, max(total_channels, 1))
        phases_out.append({
            'phase_name': 'channel_company_resolver',
            'status': (ycr['status'] if ycr else ('completed' if resolved > 0 else 'pending')),
            'started_at': ycr['started_at'].isoformat() if ycr and ycr['started_at'] else None,
            'completed_at': ycr['completed_at'].isoformat() if ycr and ycr['completed_at'] else None,
            'duration_seconds': ycr_elapsed or None,
            'eta_seconds': ycr_eta,
            'progress_percentage': min(100, int(100 * resolved / max(total_channels, 1))) if total_channels else None,
            'metrics': {
                'items_processed': resolved,
                'total_items': total_channels,
                'success_rate': success_rate,
                'errors_count': 0,
                'channels_resolved': resolved,
                'unique_channels': total_channels
            }
        })

        # 7) Content Analysis
        ca = phase_map.get('content_analysis')
        analyzed = pe['content_analyzed'] or 0
        
        # Get detailed analysis metrics
        analysis_stats = await db.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT oca.url) as analyzed_count,
                AVG(CARDINALITY(oca.jtbd_phases)) as avg_jtbd_phases,
                AVG(oca.relevance_score) as avg_relevance,
                AVG(oca.trust_score) as avg_trust,
                COUNT(DISTINCT oca.url) FILTER (WHERE oca.relevance_score > 0.7) as highly_relevant,
                COUNT(DISTINCT oca.url) FILTER (WHERE 'solution_exploration' = ANY(oca.jtbd_phases)) as solution_phase,
                COUNT(DISTINCT oca.url) FILTER (WHERE 'problem_exploration' = ANY(oca.jtbd_phases)) as problem_phase
            FROM optimized_content_analysis oca
            WHERE EXISTS (
                SELECT 1 FROM scraped_content sc 
                WHERE sc.url = oca.url 
                AND sc.pipeline_execution_id = $1
            )
            """,
            pipeline_id
        )
        
        analyzed_actual = analysis_stats['analyzed_count'] or 0
        pending = max(0, scraped_completed - analyzed_actual)
        
        ca_elapsed, ca_eta = elapsed_eta(ca, analyzed_actual, max(scraped_completed, 1))
        phases_out.append({
            'phase_name': 'content_analysis',
            'status': (ca['status'] if ca else ('completed' if analyzed > 0 else 'pending')),
            'started_at': ca['started_at'].isoformat() if ca and ca['started_at'] else None,
            'completed_at': ca['completed_at'].isoformat() if ca and ca['completed_at'] else None,
            'duration_seconds': ca_elapsed or None,
            'eta_seconds': ca_eta,
            'progress_percentage': min(100, int(100 * analyzed_actual / max(scraped_completed, 1))) if scraped_completed else None,
            'metrics': {
                'items_processed': analyzed_actual,
                'total_items': scraped_completed,
                'success_rate': int(100 * analyzed_actual / max(scraped_completed, 1)) if scraped_completed else 0,
                'errors_count': 0,
                'pending': pending,
                'avg_jtbd_phases': round(float(analysis_stats['avg_jtbd_phases'] or 0), 1),
                'avg_relevance': round(float(analysis_stats['avg_relevance'] or 0), 2),
                'avg_trust': round(float(analysis_stats['avg_trust'] or 0), 2),
                'highly_relevant': analysis_stats['highly_relevant'] or 0,
                'solution_focused': analysis_stats['solution_phase'] or 0,
                'problem_focused': analysis_stats['problem_phase'] or 0,
                'analysis_rate': round(analyzed_actual / ca_elapsed, 2) if ca_elapsed and ca_elapsed > 0 else 0
            }
        })

        # 8) DSI Calculation
        dsi = phase_map.get('dsi_calculation')
        landscapes = pe['landscapes_calculated'] or 0
        dsi_elapsed, dsi_eta = elapsed_eta(dsi, landscapes, max(landscapes, 1))
        phases_out.append({
            'phase_name': 'dsi_calculation',
            'status': (dsi['status'] if dsi else ('completed' if landscapes > 0 else 'pending')),
            'started_at': dsi['started_at'].isoformat() if dsi and dsi['started_at'] else None,
            'completed_at': dsi['completed_at'].isoformat() if dsi and dsi['completed_at'] else None,
            'duration_seconds': dsi_elapsed or None,
            'eta_seconds': dsi_eta,
            'progress_percentage': 100 if landscapes > 0 else 0,
            'metrics': {
                'items_processed': landscapes,
                'total_items': landscapes,
                'success_rate': 100 if landscapes > 0 else 0,
                'errors_count': 0
            }
        })

        return { 'phases': phases_out }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_pipeline_phases error: {e}")
        raise HTTPException(status_code=500, detail=str(e))