"""
Historical Keyword Metrics API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, date, timedelta
from uuid import UUID

from app.core.database import db_pool
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/keywords")
async def get_historical_keyword_metrics(
    keyword_id: Optional[str] = Query(None, description="Filter by specific keyword"),
    country_code: Optional[str] = Query(None, description="Filter by country (US, UK, DE, etc.)"),
    source: Optional[str] = Query(None, description="Filter by source (SERP, GOOGLE_ADS)"),
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline execution"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user)
):
    """Get historical keyword metrics with filtering options"""
    
    # Default to last 90 days if no dates provided
    if not date_to:
        date_to = datetime.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=90)
    
    # Build dynamic query
    where_clauses = ["snapshot_date >= $1", "snapshot_date <= $2"]
    params = [date_from, date_to]
    param_count = 2
    
    if keyword_id:
        param_count += 1
        where_clauses.append(f"keyword_id = ${param_count}")
        params.append(keyword_id)
    
    if country_code:
        param_count += 1
        where_clauses.append(f"country_code = ${param_count}")
        params.append(country_code.upper())
    
    if source:
        param_count += 1
        where_clauses.append(f"source = ${param_count}")
        params.append(source.upper())
        
    if pipeline_id:
        param_count += 1
        where_clauses.append(f"pipeline_execution_id = ${param_count}")
        params.append(pipeline_id)
    
    where_clause = " AND ".join(where_clauses)
    
    async with db_pool.acquire() as conn:
        metrics = await conn.fetch(f"""
            SELECT 
                hkm.snapshot_date,
                hkm.keyword_text,
                hkm.country_code,
                hkm.source,
                hkm.avg_monthly_searches,
                hkm.competition_level,
                hkm.avg_position,
                hkm.estimated_monthly_traffic,
                hkm.low_top_of_page_bid_micros,
                hkm.high_top_of_page_bid_micros,
                hkm.pipeline_execution_id,
                hkm.calculation_frequency,
                pe.started_at as pipeline_started_at,
                pe.status as pipeline_status
            FROM historical_keyword_metrics hkm
            LEFT JOIN pipeline_executions pe ON hkm.pipeline_execution_id = pe.id
            WHERE {where_clause}
            ORDER BY hkm.snapshot_date DESC, hkm.keyword_text, hkm.country_code
            LIMIT ${param_count + 1}
        """, *params, limit)
        
        return {
            "date_range": {"from": date_from, "to": date_to},
            "total_metrics": len(metrics),
            "metrics": [dict(row) for row in metrics]
        }


@router.get("/keywords/summary")
async def get_keyword_metrics_summary(
    country_code: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """Get summary statistics for keyword metrics"""
    
    where_clause = ""
    params = []
    
    if country_code:
        where_clause = "WHERE country_code = $1"
        params = [country_code.upper()]
    
    async with db_pool.acquire() as conn:
        summary = await conn.fetchrow(f"""
            SELECT 
                COUNT(DISTINCT keyword_id) as unique_keywords,
                COUNT(DISTINCT country_code) as countries_tracked,
                COUNT(DISTINCT pipeline_execution_id) as pipeline_runs,
                COUNT(*) FILTER (WHERE source = 'GOOGLE_ADS') as google_ads_metrics,
                COUNT(*) FILTER (WHERE source = 'SERP') as serp_metrics,
                AVG(avg_monthly_searches) FILTER (WHERE avg_monthly_searches > 0) as avg_search_volume,
                COUNT(*) FILTER (WHERE competition_level = 'HIGH') as high_competition_count,
                MAX(snapshot_date) as latest_snapshot
            FROM historical_keyword_metrics
            {where_clause}
        """, *params)
        
        return dict(summary) if summary else {}


@router.get("/keywords/trends/{keyword_id}")
async def get_keyword_trends(
    keyword_id: str,
    country_code: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=24),
    current_user: User = Depends(get_current_user)
):
    """Get historical trends for a specific keyword"""
    
    end_date = date.today()
    start_date = end_date - timedelta(days=months * 30)
    
    where_clause = "WHERE keyword_id = $1 AND snapshot_date >= $2 AND snapshot_date <= $3"
    params = [keyword_id, start_date, end_date]
    
    if country_code:
        where_clause += " AND country_code = $4"
        params.append(country_code.upper())
    
    async with db_pool.acquire() as conn:
        trends = await conn.fetch(f"""
            SELECT 
                snapshot_date,
                country_code,
                source,
                avg_monthly_searches,
                competition_level,
                avg_position,
                estimated_monthly_traffic
            FROM historical_keyword_metrics
            {where_clause}
            ORDER BY snapshot_date DESC, country_code
        """, *params)
        
        return {
            "keyword_id": keyword_id,
            "date_range": {"from": start_date, "to": end_date},
            "country_filter": country_code,
            "trends": [dict(row) for row in trends]
        }


@router.get("/keywords/by-pipeline/{pipeline_id}")
async def get_pipeline_keyword_metrics(
    pipeline_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get all keyword metrics generated by a specific pipeline execution"""
    
    async with db_pool.acquire() as conn:
        # Get pipeline info
        pipeline = await conn.fetchrow("""
            SELECT id, started_at, completed_at, status, keywords_processed, keywords_with_metrics
            FROM pipeline_executions 
            WHERE id = $1
        """, pipeline_id)
        
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline execution not found")
        
        # Get keyword metrics for this pipeline
        metrics = await conn.fetch("""
            SELECT 
                keyword_text,
                country_code,
                source,
                avg_monthly_searches,
                competition_level,
                low_top_of_page_bid_micros,
                high_top_of_page_bid_micros,
                snapshot_date
            FROM historical_keyword_metrics
            WHERE pipeline_execution_id = $1
            ORDER BY country_code, avg_monthly_searches DESC
        """, pipeline_id)
        
        # Group by country for easier analysis
        by_country = {}
        for metric in metrics:
            country = metric['country_code']
            if country not in by_country:
                by_country[country] = []
            by_country[country].append(dict(metric))
        
        return {
            "pipeline_id": pipeline_id,
            "pipeline_info": dict(pipeline),
            "total_metrics": len(metrics),
            "metrics_by_country": by_country
        }


@router.get("/countries/performance")
async def get_country_performance_comparison(
    current_user: User = Depends(get_current_user)
):
    """Compare keyword performance across countries"""
    
    async with db_pool.acquire() as conn:
        country_stats = await conn.fetch("""
            SELECT 
                country_code,
                COUNT(DISTINCT keyword_id) as unique_keywords,
                COUNT(*) as total_snapshots,
                AVG(avg_monthly_searches) FILTER (WHERE avg_monthly_searches > 0) as avg_search_volume,
                COUNT(*) FILTER (WHERE competition_level = 'HIGH') as high_competition_keywords,
                COUNT(*) FILTER (WHERE source = 'GOOGLE_ADS') as google_ads_metrics,
                MAX(snapshot_date) as latest_snapshot,
                COUNT(DISTINCT pipeline_execution_id) as pipeline_runs
            FROM historical_keyword_metrics
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY country_code
            ORDER BY avg_search_volume DESC NULLS LAST
        """)
        
        return {
            "comparison_period": "Last 90 days",
            "countries": [dict(row) for row in country_stats]
        }
