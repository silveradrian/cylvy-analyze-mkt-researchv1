"""
Digital Landscape Management API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer
from typing import List, Optional
from datetime import datetime, date, timedelta
from uuid import UUID

from app.core.database import db_pool
from app.core.auth import get_current_user
from app.models.landscape import (
    DigitalLandscape, CreateLandscapeRequest, LandscapeKeywordAssignment,
    LandscapeDSIMetrics, LandscapeMetricsRequest, LandscapeSummary,
    LandscapeHistoricalTrend, EntityType
)
from app.models.user import User
from app.services.landscape.production_landscape_calculator import ProductionLandscapeCalculator
from app.services.metrics.dsi_calculator import DSICalculator
from app.core.config import settings

router = APIRouter()
security = HTTPBearer()


def get_landscape_calculator():
    """Dependency to get landscape calculator"""
    return ProductionLandscapeCalculator(db_pool)


@router.get("/", response_model=List[DigitalLandscape])
async def get_landscapes(current_user: User = Depends(get_current_user)):
    """Get all defined digital landscapes"""
    async with db_pool.acquire() as conn:
        landscapes = await conn.fetch("""
            SELECT l.id, l.name, l.description, l.is_active, l.created_at,
                   COUNT(lk.keyword_id) as keyword_count
            FROM digital_landscapes l
            LEFT JOIN landscape_keywords lk ON l.id = lk.landscape_id
            WHERE l.is_active = true
            GROUP BY l.id, l.name, l.description, l.is_active, l.created_at
            ORDER BY l.created_at DESC
        """)
        
        return [
            DigitalLandscape(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                is_active=row['is_active'],
                created_at=row['created_at'],
                keyword_count=row['keyword_count']
            )
            for row in landscapes
        ]


@router.post("/", response_model=DigitalLandscape)
async def create_landscape(
    landscape: CreateLandscapeRequest,
    current_user: User = Depends(get_current_user)
):
    """Create new digital landscape"""
    async with db_pool.acquire() as conn:
        # Check if name already exists
        existing = await conn.fetchrow("""
            SELECT id FROM digital_landscapes WHERE name = $1 AND is_active = true
        """, landscape.name)
        
        if existing:
            raise HTTPException(status_code=400, detail="Landscape name already exists")
        
        # Create landscape
        landscape_id = await conn.fetchval("""
            INSERT INTO digital_landscapes (name, description)
            VALUES ($1, $2) RETURNING id
        """, landscape.name, landscape.description)
        
        # Get created landscape
        created = await conn.fetchrow("""
            SELECT id, name, description, is_active, created_at
            FROM digital_landscapes WHERE id = $1
        """, landscape_id)
        
        return DigitalLandscape(
            id=created['id'],
            name=created['name'],
            description=created['description'],
            is_active=created['is_active'],
            created_at=created['created_at'],
            keyword_count=0
        )


@router.get("/{landscape_id}", response_model=DigitalLandscape)
async def get_landscape(
    landscape_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get specific landscape details"""
    async with db_pool.acquire() as conn:
        landscape = await conn.fetchrow("""
            SELECT l.id, l.name, l.description, l.is_active, l.created_at,
                   COUNT(lk.keyword_id) as keyword_count
            FROM digital_landscapes l
            LEFT JOIN landscape_keywords lk ON l.id = lk.landscape_id
            WHERE l.id = $1 AND l.is_active = true
            GROUP BY l.id, l.name, l.description, l.is_active, l.created_at
        """, landscape_id)
        
        if not landscape:
            raise HTTPException(status_code=404, detail="Landscape not found")
        
        return DigitalLandscape(
            id=landscape['id'],
            name=landscape['name'],
            description=landscape['description'],
            is_active=landscape['is_active'],
            created_at=landscape['created_at'],
            keyword_count=landscape['keyword_count']
        )


@router.get("/{landscape_id}/keywords")
async def get_landscape_keywords(
    landscape_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get keywords assigned to landscape"""
    async with db_pool.acquire() as conn:
        keywords = await conn.fetch("""
            SELECT k.id, k.keyword, k.avg_monthly_searches as search_volume, k.competition_level
            FROM landscape_keywords lk
            JOIN keywords k ON lk.keyword_id = k.id
            WHERE lk.landscape_id = $1
            ORDER BY k.keyword
        """, landscape_id)
        
        return [dict(row) for row in keywords]


@router.post("/{landscape_id}/keywords")
async def assign_keywords_to_landscape(
    landscape_id: str,
    keyword_ids: List[str],
    current_user: User = Depends(get_current_user)
):
    """Assign keywords to landscape"""
    async with db_pool.acquire() as conn:
        # Verify landscape exists
        landscape = await conn.fetchrow("""
            SELECT id FROM digital_landscapes WHERE id = $1 AND is_active = true
        """, landscape_id)
        
        if not landscape:
            raise HTTPException(status_code=404, detail="Landscape not found")
        
        # Clear existing assignments
        await conn.execute("""
            DELETE FROM landscape_keywords WHERE landscape_id = $1
        """, landscape_id)
        
        # Add new assignments
        assigned_count = 0
        for keyword_id in keyword_ids:
            # Verify keyword exists
            keyword_exists = await conn.fetchval("""
                SELECT id FROM keywords WHERE id = $1
            """, keyword_id)
            
            if keyword_exists:
                await conn.execute("""
                    INSERT INTO landscape_keywords (landscape_id, keyword_id)
                    VALUES ($1, $2)
                    ON CONFLICT (landscape_id, keyword_id) DO NOTHING
                """, landscape_id, keyword_id)
                assigned_count += 1
        
        return {
            "landscape_id": landscape_id,
            "keywords_assigned": assigned_count,
            "total_requested": len(keyword_ids)
        }


@router.post("/{landscape_id}/calculate")
async def calculate_landscape_dsi(
    landscape_id: str,
    current_user: User = Depends(get_current_user),
    calculator: ProductionLandscapeCalculator = Depends(get_landscape_calculator)
):
    """Calculate DSI metrics for landscape"""
    try:
        result = await calculator.calculate_and_store_landscape_dsi(landscape_id, current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


@router.get("/{landscape_id}/summary", response_model=Optional[LandscapeSummary])
async def get_landscape_summary(
    landscape_id: str,
    calculation_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    calculator: ProductionLandscapeCalculator = Depends(get_landscape_calculator)
):
    """Get landscape summary statistics"""
    summary = await calculator.get_landscape_summary(landscape_id, calculation_date)
    return summary


@router.get("/{landscape_id}/metrics")
async def get_landscape_metrics(
    landscape_id: str,
    entity_type: EntityType = Query(EntityType.COMPANY),
    limit: int = Query(50, ge=1, le=200),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """Get detailed metrics for landscape entities"""
    
    # Default to last 30 days if no dates provided
    if not date_to:
        date_to = datetime.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    async with db_pool.acquire() as conn:
        metrics = await conn.fetch("""
            SELECT 
                entity_name,
                entity_domain,
                entity_url,
                unique_keywords,
                unique_pages,
                keyword_coverage,
                estimated_traffic,
                traffic_share,
                persona_alignment,
                funnel_value,
                dsi_score,
                rank_in_landscape,
                market_position,
                calculation_date
            FROM landscape_dsi_metrics
            WHERE landscape_id = $1
                AND entity_type = $2
                AND calculation_date >= $3
                AND calculation_date <= $4
            ORDER BY calculation_date DESC, rank_in_landscape ASC
            LIMIT $5
        """, landscape_id, entity_type.value, date_from, date_to, limit)
        
        return {
            "landscape_id": landscape_id,
            "entity_type": entity_type,
            "date_range": {"from": date_from, "to": date_to},
            "metrics": [dict(row) for row in metrics]
        }


@router.get("/{landscape_id}/historical")
async def get_historical_trends(
    landscape_id: str,
    entity_id: Optional[str] = Query(None),
    metric: str = Query("dsi_score", regex="^(dsi_score|keyword_coverage|traffic_share|estimated_traffic)$"),
    current_user: User = Depends(get_current_user)
):
    """Get historical trends for specific metrics"""
    
    where_clause = "WHERE landscape_id = $1 AND entity_type = 'company'"
    params = [landscape_id]
    
    if entity_id:
        where_clause += " AND entity_id = $2"
        params.append(entity_id)
    
    async with db_pool.acquire() as conn:
        trends = await conn.fetch(f"""
            SELECT 
                calculation_date,
                entity_name,
                entity_domain,
                {metric} as metric_value,
                rank_in_landscape
            FROM landscape_dsi_metrics
            {where_clause}
            ORDER BY calculation_date DESC, rank_in_landscape ASC
            LIMIT 100
        """, *params)
        
        return {
            "landscape_id": landscape_id,
            "metric": metric,
            "entity_id": entity_id,
            "trends": [dict(row) for row in trends]
        }


@router.get("/keywords/available")
async def get_available_keywords(
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user)
):
    """Get available keywords for assignment"""
    async with db_pool.acquire() as conn:
        if search:
            keywords = await conn.fetch("""
                SELECT id, keyword, avg_monthly_searches as search_volume, competition_level
                FROM keywords
                WHERE keyword ILIKE $1
                ORDER BY avg_monthly_searches DESC NULLS LAST, keyword
                LIMIT $2
            """, f"%{search}%", limit)
        else:
            keywords = await conn.fetch("""
                SELECT id, keyword, avg_monthly_searches as search_volume, competition_level
                FROM keywords
                ORDER BY avg_monthly_searches DESC NULLS LAST, keyword
                LIMIT $1
            """, limit)
        
        return [dict(row) for row in keywords]


@router.delete("/{landscape_id}")
async def delete_landscape(
    landscape_id: str,
    current_user: User = Depends(get_current_user)
):
    """Soft delete a landscape"""
    async with db_pool.acquire() as conn:
        # Check if landscape exists
        landscape = await conn.fetchrow("""
            SELECT id FROM digital_landscapes WHERE id = $1 AND is_active = true
        """, landscape_id)
        
        if not landscape:
            raise HTTPException(status_code=404, detail="Landscape not found")
        
        # Soft delete
        await conn.execute("""
            UPDATE digital_landscapes 
            SET is_active = false 
            WHERE id = $1
        """, landscape_id)
        
        return {"message": "Landscape deleted successfully"}
