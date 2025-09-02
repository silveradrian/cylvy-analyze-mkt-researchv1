"""
Keyword metrics API endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from app.core.auth import get_current_user, require_admin
from app.models.user import User
from app.models.keyword_metrics import KeywordMetric, KeywordMetricsRequest, KeywordJob
from app.services.keywords.google_ads_service import GoogleAdsService
from app.services.keywords_service import KeywordsService


router = APIRouter(prefix="/keyword-metrics", tags=["keyword-metrics"])


class KeywordMetricsUploadRequest(BaseModel):
    """Request for uploading keywords with metrics fetch"""
    keywords: List[str]
    regions: List[str] = ["US", "UK"]
    fetch_google_ads_metrics: bool = True


class KeywordMetricsResponse(BaseModel):
    """Response with keyword metrics"""
    keyword: str
    metrics: Optional[KeywordMetric] = None
    error: Optional[str] = None


# Initialize services
google_ads_service: Optional[GoogleAdsService] = None
keywords_service: Optional[KeywordsService] = None


async def get_google_ads_service():
    """Get Google Ads service instance"""
    global google_ads_service
    if not google_ads_service:
        google_ads_service = GoogleAdsService()
        await google_ads_service.initialize()
    return google_ads_service


async def get_keywords_service():
    """Get keywords service instance"""
    global keywords_service
    if not keywords_service:
        from app.core.config import settings
        from app.core.database import get_db
        db = await get_db()
        keywords_service = KeywordsService(settings, db)
    return keywords_service


@router.post("/fetch")
async def fetch_keyword_metrics(
    keywords: List[str],
    location_id: str = "2840",  # US by default
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    ads_service: GoogleAdsService = Depends(get_google_ads_service)
):
    """Fetch keyword metrics from Google Ads API"""
    if not keywords:
        raise HTTPException(status_code=400, detail="No keywords provided")
    
    # Process in background
    job_id = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    background_tasks.add_task(
        process_keyword_metrics_job,
        job_id,
        keywords,
        location_id,
        ads_service
    )
    
    return {
        "job_id": job_id,
        "message": f"Started metrics fetch for {len(keywords)} keywords",
        "status": "processing"
    }


@router.post("/upload-and-process")
async def upload_keywords_with_metrics(
    request: KeywordMetricsUploadRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    keywords_svc: KeywordsService = Depends(get_keywords_service),
    ads_service: GoogleAdsService = Depends(get_google_ads_service)
):
    """Upload keywords and fetch Google Ads metrics"""
    
    # First, upload keywords to database
    keywords_processed = 0
    errors = []
    
    async with db_pool.acquire() as conn:
        for keyword in request.keywords:
            try:
                await conn.execute(
                    """
                    INSERT INTO keywords (keyword, created_at)
                    VALUES ($1, NOW())
                    ON CONFLICT (keyword) DO NOTHING
                    """,
                    keyword.strip()
                )
                keywords_processed += 1
            except Exception as e:
                errors.append(f"Failed to insert '{keyword}': {str(e)}")
    
    # Start background metrics fetch if enabled
    metrics_job_id = None
    if request.fetch_google_ads_metrics and request.keywords:
        metrics_job_id = f"upload_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        background_tasks.add_task(
            process_keyword_metrics_job,
            metrics_job_id,
            request.keywords,
            "2840",  # US location
            ads_service
        )
    
    return {
        "total_keywords": len(request.keywords),
        "keywords_processed": keywords_processed,
        "metrics_job_id": metrics_job_id,
        "metrics_fetch_started": request.fetch_google_ads_metrics,
        "errors": errors
    }


@router.get("/test-connection")
async def test_google_ads_connection(
    current_user: User = Depends(require_admin),
    ads_service: GoogleAdsService = Depends(get_google_ads_service)
):
    """Test Google Ads API connection"""
    result = await ads_service.test_connection()
    
    if result["status"] == "error":
        raise HTTPException(status_code=503, detail=result["message"])
    
    return result


@router.get("/keywords/{keyword_id}/metrics")
async def get_keyword_metrics(
    keyword_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get stored metrics for a specific keyword"""
    async with db_pool.acquire() as conn:
        metrics = await conn.fetchrow(
            """
            SELECT k.keyword, k.avg_monthly_searches, k.competition_level,
                   k.client_score, k.persona_score, k.seo_score
            FROM keywords k
            WHERE k.id = $1
            """,
            keyword_id
        )
        
        if not metrics:
            raise HTTPException(status_code=404, detail="Keyword not found")
        
        return dict(metrics)


async def process_keyword_metrics_job(
    job_id: str,
    keywords: List[str],
    location_id: str,
    ads_service: GoogleAdsService
):
    """Background task to process keyword metrics"""
    logger.info(f"Processing keyword metrics job {job_id} for {len(keywords)} keywords")
    
    try:
        # Batch process keywords (Google Ads has limits)
        batch_size = 10
        total_processed = 0
        
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i:i + batch_size]
            
            try:
                # Fetch metrics for batch
                metrics = await ads_service.get_keyword_metrics(batch, location_id)
                
                # Store metrics in database
                async with db_pool.acquire() as conn:
                    for metric in metrics:
                        await conn.execute(
                            """
                            UPDATE keywords 
                            SET 
                                avg_monthly_searches = $2,
                                competition_level = $3,
                                updated_at = NOW()
                            WHERE keyword = $1
                            """,
                            metric.keyword,
                            metric.avg_monthly_searches,
                            metric.competition_level
                        )
                
                total_processed += len(metrics)
                logger.info(f"Job {job_id}: Processed {total_processed}/{len(keywords)} keywords")
                
            except Exception as e:
                logger.error(f"Job {job_id}: Error processing batch {i//batch_size + 1}: {e}")
            
            # Rate limiting delay
            await asyncio.sleep(1)
        
        logger.info(f"Job {job_id} completed. Processed {total_processed} keywords")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        # In a full implementation, you'd update job status in database
