"""
Generic Analysis API

API endpoints for performing content analysis with generic dimensions
and retrieving flexible analysis results.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.auth import User
from app.models.generic_dimensions import (
    GenericAnalysisRequest,
    GenericAnalysisResponse,
    GenericDimensionAnalysis,
    EvidenceAnalysis,
    ScoringBreakdown
)
# from app.services.analysis.generic_content_analyzer import GenericContentAnalyzer  # Moved to redundant
from app.services.scraping.web_scraper import WebScraper
from loguru import logger


router = APIRouter()


@router.post(
    "/content-analysis/generic-dimensions",
    response_model=GenericAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze content with generic dimensions",
    description="Perform content analysis using configured generic dimensions"
)
async def analyze_content_generic_dimensions(
    analysis_request: GenericAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze content using generic custom dimensions.
    
    This endpoint scrapes content from the provided URL and analyzes it
    against all configured generic dimensions for the client, or optionally
    against filtered dimensions.
    """
    
    try:
        logger.info(f"Starting generic dimension analysis for client {analysis_request.client_id}")
        
        # Initialize services
        # analyzer = GenericContentAnalyzer()  # Service moved to redundant - endpoint temporarily disabled
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generic analysis endpoint is temporarily disabled during refactoring"
        )
        scraper = WebScraper()
        
        # Get client dimensions
        dimensions = await analyzer.get_client_dimensions(
            client_id=analysis_request.client_id,
            dimension_filters=analysis_request.dimension_filters,
            db=db
        )
        
        if not dimensions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active generic dimensions found for client '{analysis_request.client_id}'"
            )
        
        logger.info(f"Found {len(dimensions)} dimensions for analysis")
        
        # Scrape content
        scraping_result = await scraper.scrape_url(analysis_request.url)
        if not scraping_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to scrape content from URL: {scraping_result.error}"
            )
        
        content = scraping_result.content
        if len(content.strip()) < 100:  # Minimum content threshold
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient content found at URL for meaningful analysis"
            )
        
        # Create content analysis record
        analysis_id = await _create_content_analysis_record(
            url=analysis_request.url,
            title=scraping_result.title or "Untitled",
            content=content,
            client_id=analysis_request.client_id,
            analysis_type="generic_dimensions",
            db=db
        )
        
        # Perform generic dimension analysis
        analysis_results = await analyzer.analyze_content_with_generic_dimensions(
            content=content,
            url=analysis_request.url,
            client_id=analysis_request.client_id,
            dimensions=dimensions,
            content_analysis_id=analysis_id,
            db=db
        )
        
        db.commit()
        
        # Build response
        response = GenericAnalysisResponse(
            analysis_id=analysis_id,
            url=analysis_request.url,
            client_id=analysis_request.client_id,
            generic_dimensions=analysis_results
        )
        
        logger.info(f"Completed generic dimension analysis with ID: {analysis_id}")
        return response
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in generic dimension analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze content"
        )


@router.get(
    "/content-analysis/{analysis_id}/generic-dimensions",
    response_model=GenericAnalysisResponse,
    summary="Get generic dimension analysis results",
    description="Retrieve analysis results for a specific content analysis"
)
async def get_generic_analysis_results(
    analysis_id: UUID,
    dimension_filters: Optional[List[str]] = Query(None, description="Filter to specific dimensions"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get generic dimension analysis results for a specific analysis."""
    
    try:
        # Get content analysis info
        content_info = db.execute(
            text("""
                SELECT id, url, client_id, title, created_at
                FROM content_analysis 
                WHERE id = :analysis_id
            """),
            {"analysis_id": analysis_id}
        ).fetchone()
        
        if not content_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Content analysis with ID {analysis_id} not found"
            )
        
        # Build query for dimension analysis results
        query = """
            SELECT gda.*, gcd.name as dimension_name
            FROM generic_dimension_analysis gda
            JOIN generic_custom_dimensions gcd ON gda.dimension_id = gcd.dimension_id 
                AND gcd.client_id = :client_id
            WHERE gda.content_analysis_id = :analysis_id
        """
        params = {
            "analysis_id": analysis_id,
            "client_id": content_info.client_id
        }
        
        # Apply dimension filters if provided
        if dimension_filters:
            placeholders = ",".join([f":dim_{i}" for i in range(len(dimension_filters))])
            query += f" AND gda.dimension_id IN ({placeholders})"
            for i, dim_id in enumerate(dimension_filters):
                params[f"dim_{i}"] = dim_id
        
        query += " ORDER BY gda.analyzed_at DESC"
        
        # Execute query
        results = db.execute(text(query), params).fetchall()
        
        if not results:
            # Check if analysis exists but no dimensions were analyzed
            dimension_check = db.execute(
                text("""
                    SELECT COUNT(*) as count
                    FROM generic_dimension_analysis 
                    WHERE content_analysis_id = :analysis_id
                """),
                {"analysis_id": analysis_id}
            ).fetchone()
            
            if dimension_check.count == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No generic dimension analysis found for this content"
                )
        
        # Convert results to GenericDimensionAnalysis objects
        dimension_analyses = {}
        for row in results:
            evidence_analysis = EvidenceAnalysis(**row.evidence_analysis)
            scoring_breakdown = ScoringBreakdown(**row.scoring_breakdown)
            
            analysis = GenericDimensionAnalysis(
                id=row.id,
                content_analysis_id=row.content_analysis_id,
                dimension_id=row.dimension_id,
                final_score=row.final_score,
                evidence_summary=row.evidence_summary,
                evidence_analysis=evidence_analysis,
                scoring_breakdown=scoring_breakdown,
                confidence_score=row.confidence_score,
                detailed_reasoning=row.detailed_reasoning,
                matched_criteria=row.matched_criteria,
                analysis_metadata=row.analysis_metadata or {},
                analyzed_at=row.analyzed_at,
                model_used=row.model_used,
                analysis_version=row.analysis_version
            )
            
            dimension_analyses[row.dimension_id] = analysis
        
        # Build response
        response = GenericAnalysisResponse(
            analysis_id=analysis_id,
            url=content_info.url,
            client_id=content_info.client_id,
            generic_dimensions=dimension_analyses
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generic analysis results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analysis results"
        )


@router.get(
    "/clients/{client_id}/generic-analysis/summary",
    summary="Get generic analysis summary for client",
    description="Get aggregated analysis metrics across all generic dimensions for a client"
)
async def get_client_generic_analysis_summary(
    client_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to include in summary"),
    dimension_filters: Optional[List[str]] = Query(None, description="Filter to specific dimensions"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get aggregated analysis summary for a client's generic dimensions."""
    
    try:
        # Build base query
        query = """
            WITH recent_analyses AS (
                SELECT 
                    gda.dimension_id,
                    gcd.name as dimension_name,
                    gda.final_score,
                    gda.confidence_score,
                    gda.evidence_analysis,
                    gda.analyzed_at,
                    ca.url,
                    ca.title
                FROM generic_dimension_analysis gda
                JOIN content_analysis ca ON gda.content_analysis_id = ca.id
                JOIN generic_custom_dimensions gcd ON gda.dimension_id = gcd.dimension_id 
                    AND gcd.client_id = :client_id
                WHERE ca.created_at >= NOW() - INTERVAL ':days days'
                    AND gcd.is_active = true
        """
        
        params = {"client_id": client_id, "days": days}
        
        if dimension_filters:
            placeholders = ",".join([f":dim_{i}" for i in range(len(dimension_filters))])
            query += f" AND gda.dimension_id IN ({placeholders})"
            for i, dim_id in enumerate(dimension_filters):
                params[f"dim_{i}"] = dim_id
        
        query += """
            )
            SELECT 
                dimension_id,
                dimension_name,
                COUNT(*) as total_analyses,
                ROUND(AVG(final_score::numeric), 2) as avg_score,
                ROUND(AVG(confidence_score::numeric), 2) as avg_confidence,
                MIN(final_score) as min_score,
                MAX(final_score) as max_score,
                COUNT(CASE WHEN final_score >= 7 THEN 1 END) as high_scores,
                COUNT(CASE WHEN final_score <= 3 THEN 1 END) as low_scores
            FROM recent_analyses
            GROUP BY dimension_id, dimension_name
            ORDER BY avg_score DESC
        """
        
        results = db.execute(text(query), params).fetchall()
        
        # Calculate overall metrics
        total_query = """
            SELECT 
                COUNT(DISTINCT gda.content_analysis_id) as total_content_analyzed,
                COUNT(*) as total_dimension_analyses,
                ROUND(AVG(gda.final_score::numeric), 2) as overall_avg_score
            FROM generic_dimension_analysis gda
            JOIN content_analysis ca ON gda.content_analysis_id = ca.id
            JOIN generic_custom_dimensions gcd ON gda.dimension_id = gcd.dimension_id 
                AND gcd.client_id = :client_id
            WHERE ca.created_at >= NOW() - INTERVAL ':days days'
                AND gcd.is_active = true
        """
        
        total_params = {"client_id": client_id, "days": days}
        if dimension_filters:
            total_query += f" AND gda.dimension_id IN ({placeholders})"
            total_params.update({f"dim_{i}": dim_id for i, dim_id in enumerate(dimension_filters)})
        
        total_result = db.execute(text(total_query), total_params).fetchone()
        
        # Build dimension summaries
        dimension_summaries = []
        for row in results:
            dimension_summaries.append({
                "dimension_id": row.dimension_id,
                "dimension_name": row.dimension_name,
                "total_analyses": row.total_analyses,
                "avg_score": float(row.avg_score) if row.avg_score else 0,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0,
                "min_score": row.min_score,
                "max_score": row.max_score,
                "high_scores": row.high_scores,
                "low_scores": row.low_scores,
                "performance_trend": "stable"  # Could be enhanced with historical analysis
            })
        
        # Build response
        summary = {
            "client_id": client_id,
            "summary_period_days": days,
            "generated_at": datetime.utcnow(),
            "overall_metrics": {
                "total_content_analyzed": total_result.total_content_analyzed if total_result else 0,
                "total_dimension_analyses": total_result.total_dimension_analyses if total_result else 0,
                "overall_avg_score": float(total_result.overall_avg_score) if total_result and total_result.overall_avg_score else 0
            },
            "dimension_summaries": dimension_summaries,
            "filters_applied": {
                "dimension_filters": dimension_filters
            }
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting generic analysis summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analysis summary"
        )


@router.get(
    "/generic-analysis/{analysis_id}/export",
    summary="Export generic analysis results",
    description="Export detailed analysis results in various formats"
)
async def export_generic_analysis_results(
    analysis_id: UUID,
    format: str = Query("json", regex="^(json|csv|xlsx)$", description="Export format"),
    include_raw_data: bool = Query(False, description="Include raw analysis data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export generic dimension analysis results in specified format."""
    
    try:
        # Get analysis results (reuse the get function logic)
        analysis_response = await get_generic_analysis_results(
            analysis_id=analysis_id,
            db=db,
            current_user=current_user
        )
        
        # Prepare export data
        export_data = {
            "analysis_id": str(analysis_response.analysis_id),
            "url": analysis_response.url,
            "client_id": analysis_response.client_id,
            "export_timestamp": datetime.utcnow().isoformat(),
            "dimensions": []
        }
        
        for dim_id, analysis in analysis_response.generic_dimensions.items():
            dimension_data = {
                "dimension_id": dim_id,
                "final_score": analysis.final_score,
                "confidence_score": analysis.confidence_score,
                "evidence_summary": analysis.evidence_summary,
                "detailed_reasoning": analysis.detailed_reasoning,
                "matched_criteria": analysis.matched_criteria,
                "evidence_analysis": analysis.evidence_analysis.dict(),
                "scoring_breakdown": analysis.scoring_breakdown.dict(),
                "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None
            }
            
            if include_raw_data:
                dimension_data["analysis_metadata"] = analysis.analysis_metadata
                dimension_data["model_used"] = analysis.model_used
                dimension_data["analysis_version"] = analysis.analysis_version
            
            export_data["dimensions"].append(dimension_data)
        
        # Return based on format
        if format == "json":
            return export_data
        elif format == "csv":
            # For CSV, flatten the data structure
            import pandas as pd
            
            flattened_data = []
            for dim in export_data["dimensions"]:
                flat_record = {
                    "analysis_id": export_data["analysis_id"],
                    "url": export_data["url"],
                    "client_id": export_data["client_id"],
                    "dimension_id": dim["dimension_id"],
                    "final_score": dim["final_score"],
                    "confidence_score": dim["confidence_score"],
                    "evidence_summary": dim["evidence_summary"],
                    "total_relevant_words": dim["evidence_analysis"]["total_relevant_words"],
                    "evidence_threshold_met": dim["evidence_analysis"]["evidence_threshold_met"],
                    "specificity_score": dim["evidence_analysis"]["specificity_score"],
                    "base_score": dim["scoring_breakdown"]["base_score"],
                    "scoring_rationale": dim["scoring_breakdown"]["scoring_rationale"],
                    "analyzed_at": dim["analyzed_at"]
                }
                flattened_data.append(flat_record)
            
            df = pd.DataFrame(flattened_data)
            csv_content = df.to_csv(index=False)
            
            from fastapi.responses import Response
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=generic_analysis_{analysis_id}.csv"}
            )
        else:
            # Excel format would require additional implementation
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Excel export not yet implemented"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting generic analysis results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export analysis results"
        )


async def _create_content_analysis_record(
    url: str,
    title: str,
    content: str,
    client_id: str,
    analysis_type: str,
    db: Session
) -> UUID:
    """Create a content analysis record and return its ID."""
    
    analysis_id = uuid4()
    
    db.execute(
        text("""
            INSERT INTO content_analysis (
                id, url, title, content, client_id, analysis_type,
                created_at, updated_at, status
            ) VALUES (
                :id, :url, :title, :content, :client_id, :analysis_type,
                :created_at, :updated_at, 'completed'
            )
        """),
        {
            "id": analysis_id,
            "url": url,
            "title": title,
            "content": content,
            "client_id": client_id,
            "analysis_type": analysis_type,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    )
    
    return analysis_id
