"""
Export API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import io

from app.core.database import db_pool
from app.core.auth import get_current_user
from app.services.export.enhanced_digital_landscape_exporter import EnhancedDigitalLandscapeExporter
from loguru import logger

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/digital-landscape/{pipeline_id}")
async def export_digital_landscape(
    pipeline_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Export comprehensive digital landscape analysis to Excel
    
    Includes:
    - Company DSI Rankings
    - Page Level DSI Rankings
    - Full Page Level Data
    - SERP Analysis
    - Video Results
    - News Results
    - Summary Dashboard
    """
    try:
        # Verify pipeline exists
        async with db_pool.acquire() as conn:
            pipeline = await conn.fetchrow(
                "SELECT id, status FROM pipeline_executions WHERE id = $1",
                pipeline_id
            )
            
            if not pipeline:
                raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # Generate Excel export
        exporter = EnhancedDigitalLandscapeExporter(db_pool)
        excel_buffer = await exporter.export_pipeline_data(pipeline_id)
        
        # Prepare response
        filename = f"digital_landscape_{pipeline_id[:8]}_{pipeline['status']}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_buffer.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        )
        
    except Exception as e:
        import traceback
        logger.error(f"Error exporting digital landscape: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/dsi-rankings/{pipeline_id}")
async def export_dsi_rankings(
    pipeline_id: str,
    format: str = "csv",
    current_user: dict = Depends(get_current_user)
):
    """
    Export DSI rankings in CSV or JSON format
    """
    try:
        async with db_pool.acquire() as conn:
            # Get DSI rankings
            rankings = await conn.fetch("""
                SELECT 
                    ds.company_domain,
                    ds.dsi_score,
                    ds.keyword_overlap_score,
                    ds.content_relevance_score,
                    ds.market_presence_score,
                    ds.traffic_share_score,
                    ds.metadata,
                    RANK() OVER (ORDER BY ds.dsi_score DESC) as rank
                FROM dsi_scores ds
                WHERE ds.pipeline_execution_id = $1
                ORDER BY ds.dsi_score DESC
            """, pipeline_id)
            
            if not rankings:
                raise HTTPException(
                    status_code=404, 
                    detail="No DSI scores found for this pipeline"
                )
            
            if format == "csv":
                # Convert to CSV
                import csv
                output = io.StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=[
                        "rank", "company_domain", "dsi_score",
                        "keyword_overlap_score", "content_relevance_score",
                        "market_presence_score", "traffic_share_score"
                    ]
                )
                writer.writeheader()
                
                for row in rankings:
                    writer.writerow({
                        "rank": row["rank"],
                        "company_domain": row["company_domain"],
                        "dsi_score": round(float(row["dsi_score"]), 4),
                        "keyword_overlap_score": round(float(row["keyword_overlap_score"]), 4),
                        "content_relevance_score": round(float(row["content_relevance_score"]), 4),
                        "market_presence_score": round(float(row["market_presence_score"]), 4),
                        "traffic_share_score": round(float(row["traffic_share_score"] or 0), 4)
                    })
                
                output.seek(0)
                return StreamingResponse(
                    io.StringIO(output.getvalue()),
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=dsi_rankings_{pipeline_id[:8]}.csv"
                    }
                )
            else:
                # Return JSON
                return [
                    {
                        "rank": row["rank"],
                        "company_domain": row["company_domain"],
                        "dsi_score": float(row["dsi_score"]),
                        "keyword_overlap_score": float(row["keyword_overlap_score"]),
                        "content_relevance_score": float(row["content_relevance_score"]),
                        "market_presence_score": float(row["market_presence_score"]),
                        "traffic_share_score": float(row["traffic_share_score"] or 0),
                        "metadata": row["metadata"]
                    }
                    for row in rankings
                ]
                
    except Exception as e:
        logger.error(f"Error exporting DSI rankings: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )
