"""
Webhook endpoints for external service integrations
"""
from typing import Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from loguru import logger
from pydantic import BaseModel
from datetime import datetime
import asyncio

from app.core.database import get_db
from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig
from app.services.serp.unified_serp_collector import UnifiedSERPCollector


router = APIRouter()


class ScaleSERPWebhookPayload(BaseModel):
    """Scale SERP webhook payload structure"""
    request_info: Dict[str, Any]
    batch: Dict[str, Any]
    result_set: Dict[str, Any]


class WebhookResponse(BaseModel):
    """Standard webhook response"""
    success: bool
    message: str
    pipeline_id: str = None


@router.post("/scaleserp/batch-complete", response_model=WebhookResponse)
async def handle_scaleserp_batch_complete(
    payload: ScaleSERPWebhookPayload,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """
    Handle Scale SERP batch completion webhook
    
    This endpoint:
    1. Receives notification when a Scale SERP batch completes
    2. Validates the payload
    3. Triggers pipeline execution for processing results
    4. Returns quickly (within 5 seconds) to avoid timeout
    """
    try:
        # Extract key information from payload
        batch_id = payload.batch.get('id')
        batch_name = payload.batch.get('name', '')
        result_set_id = payload.result_set.get('id')
        searches_completed = payload.result_set.get('searches_completed', 0)
        searches_failed = payload.result_set.get('searches_failed', 0)
        
        logger.info(f"📨 WEBHOOK: Scale SERP batch completed - ID: {batch_id}, Name: {batch_name}")
        logger.info(f"📊 Results: {searches_completed} completed, {searches_failed} failed")
        
        # Validate webhook type
        request_type = payload.request_info.get('type')
        if request_type != 'batch_resultset_completed':
            logger.warning(f"⚠️ Unexpected webhook type: {request_type}")
            return WebhookResponse(
                success=False,
                message=f"Unexpected webhook type: {request_type}"
            )
        
        # Extract download links
        download_links = payload.result_set.get('download_links', {})
        json_links = download_links.get('json', {})
        csv_links = download_links.get('csv', {})
        
        # Check if we have valid download links
        if not json_links and not csv_links:
            logger.error(f"❌ No download links in webhook payload for batch {batch_id}")
            return WebhookResponse(
                success=False,
                message="No download links in webhook payload"
            )
        
        # Queue pipeline execution in background
        # This allows us to respond quickly to the webhook
        background_tasks.add_task(
            trigger_pipeline_from_webhook,
            batch_id=batch_id,
            batch_name=batch_name,
            result_set_id=result_set_id,
            download_links=download_links,
            db=db
        )
        
        return WebhookResponse(
            success=True,
            message=f"Pipeline execution queued for batch {batch_id}",
            pipeline_id=batch_id  # Using batch_id as pipeline reference for now
        )
        
    except Exception as e:
        logger.error(f"❌ Error handling Scale SERP webhook: {e}")
        # Return error but with 200 status to prevent Scale SERP from retrying
        return WebhookResponse(
            success=False,
            message=f"Error processing webhook: {str(e)}"
        )


async def trigger_pipeline_from_webhook(
    batch_id: str,
    batch_name: str,
    result_set_id: int,
    download_links: Dict[str, Any],
    db
):
    """
    Trigger pipeline execution from webhook data
    
    This runs in the background after webhook response is sent
    """
    try:
        logger.info(f"🚀 Starting pipeline from webhook for batch {batch_id}")
        logger.info(f"📋 Batch name: {batch_name}")
        
        # Extract content type from batch name
        # Expected formats: 
        # - "Cylvy ORGANIC Batch YYYYMMDD_HHMMSS"
        # - "Cylvy NEWS Batch YYYYMMDD_HHMMSS"
        # - "Cylvy VIDEOS Batch YYYYMMDD_HHMMSS"
        content_type = None
        batch_name_upper = batch_name.upper()
        
        if "ORGANIC" in batch_name_upper:
            content_type = "organic"
        elif "NEWS" in batch_name_upper:
            content_type = "news"
        elif "VIDEO" in batch_name_upper or "VIDEOS" in batch_name_upper:
            content_type = "video"
        else:
            # Fallback: try to determine from batch name pattern
            logger.warning(f"⚠️ Could not determine content type from batch name: {batch_name}")
            # Process all content types as fallback
            content_type = None
        
        logger.info(f"📊 Detected content type: {content_type or 'ALL'}")
        
        # Check if we need to wait for other content type batches
        # This is relevant when multiple content types are scheduled for the same time
        from app.core.database import db_pool
        async with db_pool.acquire() as conn:
            # Check for other pending batches from the same schedule
            # You might want to implement logic here to wait for all batches
            # from the same schedule period before processing
            pass
        
        # Initialize settings
        from app.core.config import get_settings
        settings = get_settings()
        
        # Determine which phases to run based on content type
        enable_company_enrichment = True
        enable_youtube_enrichment = content_type in ["organic", "video", None]
        enable_content_analysis = True
        enable_dsi_calculation = True
        
        # Create pipeline config
        config = PipelineConfig(
            client_id="webhook",
            # Use specific content type if identified, otherwise process all
            content_types=[content_type] if content_type else ["organic", "news", "video"],
            keywords=None,  # Will use all project keywords
            regions=["US", "UK", "DE", "SA", "VN"],  # All configured regions
            is_initial_run=False,
            # Skip phases that are already done
            enable_keyword_metrics=False,  # Keywords already have metrics from scheduled batch
            enable_serp_collection=False,  # Skip SERP collection since we have results from the batch
            # Enable subsequent phases based on content type
            enable_company_enrichment=enable_company_enrichment,
            enable_video_enrichment=enable_youtube_enrichment,
            enable_content_analysis=enable_content_analysis,
            enable_landscape_dsi=enable_dsi_calculation,
            # Pass the batch ID, result set ID, and download links so pipeline can fetch results
            serp_batch_id=batch_id,
            serp_result_set_id=result_set_id,
            serp_download_links=download_links
        )
        
        # Log batch information for tracking
        logger.info(f"🔧 Webhook source info: batch_id={batch_id}, content_type={content_type}, result_set_id={result_set_id}")
        logger.info(f"📥 Download links: {download_links}")
        
        logger.info(f"🔧 Pipeline config: content_types={config.content_types}, regions={config.regions}")
        logger.info(f"🔧 Phases enabled: company_enrichment={enable_company_enrichment}, youtube_enrichment={enable_youtube_enrichment}")
        
        # Record completion only; coordinator will decide when to start a pipeline
        try:
            from uuid import UUID
            from datetime import datetime as _dt
            from app.services.serp.serp_batch_coordinator import SerpBatchCoordinator
            from app.core.database import db_pool as _pool

            # Derive a project_id and period_date; for now use a single-project mode if not present
            # TODO: parse project_id from webhook payload when available
            project_id = UUID("00000000-0000-0000-0000-000000000001")
            period_date = _dt.utcnow().date()

            coordinator = SerpBatchCoordinator(_pool, PipelineService(settings, db))
            await coordinator.record_batch_completion(
                project_id=project_id,
                content_type=content_type or "organic",
                period_date=period_date,
                batch_id=batch_id,
                result_set_id=result_set_id,
                download_links=download_links
            )

            if settings.WEBHOOK_STARTS_PIPELINE:
                await coordinator.try_start_pipeline(project_id, period_date)

            # Store batch completion record for tracking (legacy table)
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO webhook_batch_completions (
                        batch_id, batch_name, content_type, result_set_id,
                        completed_at, success
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (batch_id) DO UPDATE SET
                        completed_at = EXCLUDED.completed_at,
                        success = EXCLUDED.success
                    """,
                    batch_id, batch_name, content_type, result_set_id,
                    datetime.utcnow(), True
                )
            logger.info(f"✅ Recorded webhook batch {batch_id} for coordination")
        except Exception as e:
            logger.error(f"❌ Failed to record webhook batch {batch_id}: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error triggering pipeline from webhook: {e}")
        import traceback
        logger.error(traceback.format_exc())


@router.post("/manual/trigger-pipeline", response_model=WebhookResponse)
async def manual_trigger_pipeline(
    background_tasks: BackgroundTasks,
    config: PipelineConfig = None,
    db = Depends(get_db)
):
    """
    Manually trigger a pipeline execution
    
    This endpoint allows manual triggering of the pipeline with custom configuration
    """
    try:
        logger.info("🔧 Manual pipeline trigger received")
        
        # Use default config if none provided
        if config is None:
            config = PipelineConfig(
                client_id="manual",
                is_initial_run=True  # For manual triggers, often want full historical data
            )
        
        # Queue pipeline execution in background
        background_tasks.add_task(
            run_pipeline_async,
            config=config,
            db=db
        )
        
        return WebhookResponse(
            success=True,
            message="Pipeline execution queued",
            pipeline_id=f"manual_{datetime.utcnow().timestamp()}"
        )
        
    except Exception as e:
        logger.error(f"❌ Error triggering manual pipeline: {e}")
        return WebhookResponse(
            success=False,
            message=f"Error triggering pipeline: {str(e)}"
        )


async def run_pipeline_async(config: PipelineConfig, db):
    """Run pipeline asynchronously in background"""
    try:
        logger.info(f"🚀 Starting pipeline with config: {config.client_id}")
        
        pipeline_service = PipelineService(db)
        result = await pipeline_service.run_pipeline(config)
        
        if result['success']:
            logger.info(f"✅ Pipeline completed successfully: {result.get('pipeline_id')}")
        else:
            logger.error(f"❌ Pipeline failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"❌ Error running pipeline: {e}")
        import traceback
        logger.error(traceback.format_exc())


# Health check endpoint for webhook testing
@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoints"""
    return {
        "status": "healthy",
        "service": "webhook-handler",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/resend/{batch_id}/{result_set_id}")
async def resend_webhook(
    batch_id: str,
    result_set_id: int,
    db = Depends(get_db)
):
    """
    Manually resend a Scale SERP webhook for a specific batch and result set
    
    Args:
        batch_id: The Scale SERP batch ID
        result_set_id: The result set ID within the batch
    """
    try:
        logger.info(f"📨 Resending webhook for batch {batch_id}, result set {result_set_id}")
        
        # Initialize Scale SERP client
        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        
        if not settings.SCALE_SERP_API_KEY:
            raise HTTPException(status_code=500, detail="Scale SERP API key not configured")
        
        # Make the request to Scale SERP to resend webhook
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.scaleserp.com/batches/{batch_id}/results/{result_set_id}/resendwebhook",
                params={"api_key": settings.SCALE_SERP_API_KEY},
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("request_info", {}).get("success"):
                    logger.info(f"✅ Webhook resent successfully for batch {batch_id}")
                    return {
                        "success": True,
                        "message": f"Webhook resent for batch {batch_id}, result set {result_set_id}",
                        "scale_serp_response": result
                    }
                else:
                    error_msg = result.get("request_info", {}).get("message", "Unknown error")
                    logger.error(f"❌ Scale SERP rejected webhook resend: {error_msg}")
                    raise HTTPException(status_code=400, detail=f"Scale SERP error: {error_msg}")
            else:
                logger.error(f"❌ Scale SERP API error: {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Scale SERP API error: {response.text}"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error resending webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

