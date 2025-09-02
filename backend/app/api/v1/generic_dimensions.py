"""
Generic Dimensions API

API endpoints for managing completely generic custom dimensions with flexible
criteria-based analysis frameworks and sophisticated scoring methodologies.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.auth import User
from app.models.generic_dimensions import (
    GenericCustomDimension,
    GenericDimensionRequest,
    GenericDimensionUpdate,
    GenericDimensionAnalysis,
    GenericAnalysisRequest,
    GenericAnalysisResponse,
)
from loguru import logger


router = APIRouter()


@router.post(
    "/clients/{client_id}/generic-dimensions",
    response_model=GenericCustomDimension,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new generic custom dimension",
    description="Create a completely customizable dimension with flexible criteria and scoring framework"
)
async def create_generic_dimension(
    client_id: str,
    dimension_request: GenericDimensionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new generic custom dimension for a client.
    
    This endpoint allows creation of completely flexible dimension configurations
    with custom AI context, criteria, and scoring frameworks.
    """
    try:
        # Check if dimension_id already exists for this client
        existing = db.execute(
            text("""
                SELECT id FROM generic_custom_dimensions 
                WHERE client_id = :client_id AND dimension_id = :dimension_id
            """),
            {"client_id": client_id, "dimension_id": dimension_request.dimension_id}
        ).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Dimension '{dimension_request.dimension_id}' already exists for client '{client_id}'"
            )
        
        # Create the dimension
        dimension_id = uuid4()
        now = datetime.utcnow()
        
        db.execute(
            text("""
                INSERT INTO generic_custom_dimensions (
                    id, client_id, dimension_id, name, description,
                    ai_context, criteria, scoring_framework, metadata,
                    created_at, updated_at, created_by, is_active
                ) VALUES (
                    :id, :client_id, :dimension_id, :name, :description,
                    :ai_context, :criteria, :scoring_framework, :metadata,
                    :created_at, :updated_at, :created_by, :is_active
                )
            """),
            {
                "id": dimension_id,
                "client_id": client_id,
                "dimension_id": dimension_request.dimension_id,
                "name": dimension_request.name,
                "description": dimension_request.description,
                "ai_context": dimension_request.ai_context.dict(),
                "criteria": dimension_request.criteria.dict(),
                "scoring_framework": dimension_request.scoring_framework.dict(),
                "metadata": dimension_request.metadata,
                "created_at": now,
                "updated_at": now,
                "created_by": current_user.username if current_user else None,
                "is_active": True
            }
        )
        
        db.commit()
        
        # Return the created dimension
        result = db.execute(
            text("""
                SELECT * FROM generic_custom_dimensions WHERE id = :id
            """),
            {"id": dimension_id}
        ).fetchone()
        
        return _row_to_dimension_model(result)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating dimension: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid dimension configuration"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating generic dimension: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dimension"
        )


@router.get(
    "/clients/{client_id}/generic-dimensions",
    response_model=List[GenericCustomDimension],
    summary="List all generic dimensions for a client",
    description="Get all configured generic dimensions for a specific client"
)
async def list_generic_dimensions(
    client_id: str,
    active_only: bool = Query(True, description="Filter to active dimensions only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all generic dimensions for a client."""
    try:
        query = """
            SELECT * FROM generic_custom_dimensions 
            WHERE client_id = :client_id
        """
        params = {"client_id": client_id}
        
        if active_only:
            query += " AND is_active = true"
        
        query += " ORDER BY created_at DESC"
        
        results = db.execute(text(query), params).fetchall()
        
        return [_row_to_dimension_model(row) for row in results]
        
    except Exception as e:
        logger.error(f"Error listing generic dimensions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list dimensions"
        )


@router.get(
    "/clients/{client_id}/generic-dimensions/{dimension_id}",
    response_model=GenericCustomDimension,
    summary="Get a specific generic dimension",
    description="Retrieve configuration for a specific generic dimension"
)
async def get_generic_dimension(
    client_id: str,
    dimension_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific generic dimension configuration."""
    try:
        result = db.execute(
            text("""
                SELECT * FROM generic_custom_dimensions 
                WHERE client_id = :client_id AND dimension_id = :dimension_id
            """),
            {"client_id": client_id, "dimension_id": dimension_id}
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dimension '{dimension_id}' not found for client '{client_id}'"
            )
        
        return _row_to_dimension_model(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generic dimension: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dimension"
        )


@router.put(
    "/clients/{client_id}/generic-dimensions/{dimension_id}",
    response_model=GenericCustomDimension,
    summary="Update a generic dimension",
    description="Update configuration for an existing generic dimension"
)
async def update_generic_dimension(
    client_id: str,
    dimension_id: str,
    dimension_update: GenericDimensionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing generic dimension configuration."""
    try:
        # Check if dimension exists
        existing = db.execute(
            text("""
                SELECT id FROM generic_custom_dimensions 
                WHERE client_id = :client_id AND dimension_id = :dimension_id
            """),
            {"client_id": client_id, "dimension_id": dimension_id}
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dimension '{dimension_id}' not found for client '{client_id}'"
            )
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = {
            "client_id": client_id,
            "dimension_id": dimension_id,
            "updated_at": datetime.utcnow()
        }
        
        if dimension_update.name is not None:
            update_fields.append("name = :name")
            params["name"] = dimension_update.name
        
        if dimension_update.description is not None:
            update_fields.append("description = :description")
            params["description"] = dimension_update.description
        
        if dimension_update.ai_context is not None:
            update_fields.append("ai_context = :ai_context")
            params["ai_context"] = dimension_update.ai_context.dict()
        
        if dimension_update.criteria is not None:
            update_fields.append("criteria = :criteria")
            params["criteria"] = dimension_update.criteria.dict()
        
        if dimension_update.scoring_framework is not None:
            update_fields.append("scoring_framework = :scoring_framework")
            params["scoring_framework"] = dimension_update.scoring_framework.dict()
        
        if dimension_update.metadata is not None:
            update_fields.append("metadata = :metadata")
            params["metadata"] = dimension_update.metadata
        
        if dimension_update.is_active is not None:
            update_fields.append("is_active = :is_active")
            params["is_active"] = dimension_update.is_active
        
        update_fields.append("updated_at = :updated_at")
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Execute update
        query = f"""
            UPDATE generic_custom_dimensions 
            SET {', '.join(update_fields)}
            WHERE client_id = :client_id AND dimension_id = :dimension_id
        """
        
        db.execute(text(query), params)
        db.commit()
        
        # Return updated dimension
        result = db.execute(
            text("""
                SELECT * FROM generic_custom_dimensions 
                WHERE client_id = :client_id AND dimension_id = :dimension_id
            """),
            {"client_id": client_id, "dimension_id": dimension_id}
        ).fetchone()
        
        return _row_to_dimension_model(result)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating generic dimension: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dimension"
        )


@router.delete(
    "/clients/{client_id}/generic-dimensions/{dimension_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a generic dimension",
    description="Delete a generic dimension configuration (soft delete)"
)
async def delete_generic_dimension(
    client_id: str,
    dimension_id: str,
    hard_delete: bool = Query(False, description="Perform hard delete instead of soft delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a generic dimension configuration."""
    try:
        # Check if dimension exists
        existing = db.execute(
            text("""
                SELECT id FROM generic_custom_dimensions 
                WHERE client_id = :client_id AND dimension_id = :dimension_id
            """),
            {"client_id": client_id, "dimension_id": dimension_id}
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dimension '{dimension_id}' not found for client '{client_id}'"
            )
        
        if hard_delete:
            # Hard delete - remove completely
            db.execute(
                text("""
                    DELETE FROM generic_custom_dimensions 
                    WHERE client_id = :client_id AND dimension_id = :dimension_id
                """),
                {"client_id": client_id, "dimension_id": dimension_id}
            )
        else:
            # Soft delete - mark as inactive
            db.execute(
                text("""
                    UPDATE generic_custom_dimensions 
                    SET is_active = false, updated_at = :updated_at
                    WHERE client_id = :client_id AND dimension_id = :dimension_id
                """),
                {
                    "client_id": client_id,
                    "dimension_id": dimension_id,
                    "updated_at": datetime.utcnow()
                }
            )
        
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting generic dimension: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dimension"
        )


@router.post(
    "/clients/{client_id}/generic-dimensions/bulk",
    response_model=List[GenericCustomDimension],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create generic dimensions",
    description="Create multiple generic dimensions in a single request"
)
async def bulk_create_generic_dimensions(
    client_id: str,
    dimensions: List[GenericDimensionRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk create multiple generic dimensions."""
    try:
        created_dimensions = []
        now = datetime.utcnow()
        
        for dimension_request in dimensions:
            # Check for duplicates
            existing = db.execute(
                text("""
                    SELECT id FROM generic_custom_dimensions 
                    WHERE client_id = :client_id AND dimension_id = :dimension_id
                """),
                {"client_id": client_id, "dimension_id": dimension_request.dimension_id}
            ).fetchone()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Dimension '{dimension_request.dimension_id}' already exists"
                )
            
            # Create dimension
            dimension_id = uuid4()
            
            db.execute(
                text("""
                    INSERT INTO generic_custom_dimensions (
                        id, client_id, dimension_id, name, description,
                        ai_context, criteria, scoring_framework, metadata,
                        created_at, updated_at, created_by, is_active
                    ) VALUES (
                        :id, :client_id, :dimension_id, :name, :description,
                        :ai_context, :criteria, :scoring_framework, :metadata,
                        :created_at, :updated_at, :created_by, :is_active
                    )
                """),
                {
                    "id": dimension_id,
                    "client_id": client_id,
                    "dimension_id": dimension_request.dimension_id,
                    "name": dimension_request.name,
                    "description": dimension_request.description,
                    "ai_context": dimension_request.ai_context.dict(),
                    "criteria": dimension_request.criteria.dict(),
                    "scoring_framework": dimension_request.scoring_framework.dict(),
                    "metadata": dimension_request.metadata,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": current_user.username if current_user else None,
                    "is_active": True
                }
            )
            
            # Get created dimension
            result = db.execute(
                text("""
                    SELECT * FROM generic_custom_dimensions WHERE id = :id
                """),
                {"id": dimension_id}
            ).fetchone()
            
            created_dimensions.append(_row_to_dimension_model(result))
        
        db.commit()
        return created_dimensions
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error bulk creating generic dimensions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dimensions"
        )


@router.get(
    "/clients/{client_id}/generic-dimensions/{dimension_id}/analysis-history",
    summary="Get analysis history for a dimension",
    description="Get historical analysis results for a specific dimension"
)
async def get_dimension_analysis_history(
    client_id: str,
    dimension_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get analysis history for a specific dimension."""
    try:
        # Verify dimension exists
        dimension = db.execute(
            text("""
                SELECT id FROM generic_custom_dimensions 
                WHERE client_id = :client_id AND dimension_id = :dimension_id
            """),
            {"client_id": client_id, "dimension_id": dimension_id}
        ).fetchone()
        
        if not dimension:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dimension '{dimension_id}' not found"
            )
        
        # Get analysis history
        results = db.execute(
            text("""
                SELECT gda.*, ca.url, ca.title, ca.created_at as analysis_date
                FROM generic_dimension_analysis gda
                JOIN content_analysis ca ON gda.content_analysis_id = ca.id
                WHERE gda.dimension_id = :dimension_id
                ORDER BY gda.analyzed_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"dimension_id": dimension_id, "limit": limit, "offset": offset}
        ).fetchall()
        
        # Get total count
        count_result = db.execute(
            text("""
                SELECT COUNT(*) as total
                FROM generic_dimension_analysis gda
                JOIN content_analysis ca ON gda.content_analysis_id = ca.id
                WHERE gda.dimension_id = :dimension_id
            """),
            {"dimension_id": dimension_id}
        ).fetchone()
        
        total_count = count_result.total if count_result else 0
        
        return {
            "dimension_id": dimension_id,
            "total_analyses": total_count,
            "analyses": [
                {
                    "id": str(row.id),
                    "url": row.url,
                    "title": row.title,
                    "final_score": row.final_score,
                    "confidence_score": row.confidence_score,
                    "analyzed_at": row.analyzed_at,
                    "analysis_date": row.analysis_date,
                    "evidence_summary": row.evidence_summary
                }
                for row in results
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total_count,
                "has_more": offset + limit < total_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dimension analysis history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analysis history"
        )


def _row_to_dimension_model(row) -> GenericCustomDimension:
    """Convert database row to GenericCustomDimension model."""
    from backend.app.models.generic_dimensions import (
        AIContext, DimensionCriteria, ScoringFramework
    )
    
    return GenericCustomDimension(
        id=row.id,
        client_id=row.client_id,
        dimension_id=row.dimension_id,
        name=row.name,
        description=row.description,
        ai_context=AIContext(**row.ai_context),
        criteria=DimensionCriteria(**row.criteria),
        scoring_framework=ScoringFramework(**row.scoring_framework),
        metadata=row.metadata or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by=row.created_by,
        is_active=row.is_active
    )
