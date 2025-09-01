"""
Keywords management API endpoints
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_admin
from app.models.user import User
from app.models.keyword import Keyword, KeywordCreate, KeywordUpdate
from app.services.keywords_service import KeywordsService
from app.core.database import get_db


router = APIRouter()


class KeywordUploadRequest(BaseModel):
    """Request for uploading keywords"""
    regions: List[str] = Field(["US", "UK"], description="Regions to fetch metrics for")


class KeywordUploadResult(BaseModel):
    """Result of keyword upload"""
    total_keywords: int
    keywords_processed: int
    metrics_fetched: int
    errors: List[str] = []


# Initialize service
keywords_service: Optional[KeywordsService] = None


async def get_keywords_service():
    """Get keywords service instance"""
    global keywords_service
    if not keywords_service:
        from app.core.config import settings
        db = await get_db()
        keywords_service = KeywordsService(settings, db)
    return keywords_service


@router.get("", response_model=List[Keyword])
async def get_keywords(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    keywords_svc: KeywordsService = Depends(get_keywords_service)
):
    """Get keywords with filtering and pagination"""
    keywords = await keywords_svc.get_keywords(
        limit=limit,
        offset=offset,
        category=category,
        search=search
    )
    return keywords


@router.post("", response_model=Keyword)
async def create_keyword(
    keyword_data: KeywordCreate,
    current_user: User = Depends(require_admin),
    keywords_svc: KeywordsService = Depends(get_keywords_service)
):
    """Create a new keyword"""
    return await keywords_svc.create_keyword(keyword_data)


@router.put("/{keyword_id}", response_model=Keyword)
async def update_keyword(
    keyword_id: UUID,
    updates: KeywordUpdate,
    current_user: User = Depends(require_admin),
    keywords_svc: KeywordsService = Depends(get_keywords_service)
):
    """Update an existing keyword"""
    return await keywords_svc.update_keyword(keyword_id, updates)


@router.delete("/{keyword_id}")
async def delete_keyword(
    keyword_id: UUID,
    current_user: User = Depends(require_admin),
    keywords_svc: KeywordsService = Depends(get_keywords_service)
):
    """Delete a keyword"""
    success = await keywords_svc.delete_keyword(keyword_id)
    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"message": "Keyword deleted successfully"}


@router.post("/upload", response_model=KeywordUploadResult)
async def upload_keywords(
    file: UploadFile = File(...),
    regions: str = Query("US,UK", description="Comma-separated list of regions"),
    current_user: User = Depends(require_admin),
    keywords_svc: KeywordsService = Depends(get_keywords_service)
):
    """Upload keywords from CSV file"""
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    # Parse regions
    region_list = [r.strip() for r in regions.split(',')]
    
    try:
        result = await keywords_svc.upload_keywords_from_csv(file, region_list)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/categories")
async def get_keyword_categories(
    current_user: User = Depends(get_current_user),
    keywords_svc: KeywordsService = Depends(get_keywords_service)
):
    """Get available keyword categories"""
    categories = await keywords_svc.get_categories()
    return {"categories": categories}


@router.get("/stats")
async def get_keyword_stats(
    current_user: User = Depends(get_current_user),
    keywords_svc: KeywordsService = Depends(get_keywords_service)
):
    """Get keyword statistics"""
    stats = await keywords_svc.get_stats()
    return stats
