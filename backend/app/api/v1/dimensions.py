"""
Dimensions and Dimension Groups API

API endpoints for managing custom dimensions and their groupings.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from loguru import logger

from app.core.database import db_pool

router = APIRouter()


# Pydantic models
class DimensionGroupBase(BaseModel):
    group_id: str = Field(..., description="Unique identifier for the group")
    name: str = Field(..., description="Display name of the group")
    description: Optional[str] = Field(None, description="Description of the group")
    selection_strategy: str = Field("highest_score", description="Strategy for selecting primary dimensions")
    max_primary_dimensions: int = Field(1, description="Maximum number of primary dimensions in this group")
    display_order: int = Field(0, description="Order for display")
    color_hex: Optional[str] = Field(None, description="Hex color for UI display")
    icon: Optional[str] = Field(None, description="Icon identifier for UI")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(True)


class DimensionGroupCreate(DimensionGroupBase):
    pass


class DimensionGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    selection_strategy: Optional[str] = None
    max_primary_dimensions: Optional[int] = None
    display_order: Optional[int] = None
    color_hex: Optional[str] = None
    icon: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class DimensionGroup(DimensionGroupBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    dimension_count: Optional[int] = 0


class DimensionBase(BaseModel):
    dimension_id: str = Field(..., description="Unique identifier for the dimension")
    name: str = Field(..., description="Display name of the dimension")
    description: Optional[str] = Field(None, description="Description of the dimension")
    ai_context: Dict[str, Any] = Field(default_factory=dict)
    criteria: Dict[str, Any] = Field(default_factory=dict)
    scoring_framework: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(True)


class DimensionCreate(DimensionBase):
    group_ids: Optional[List[UUID]] = Field(None, description="Groups to assign this dimension to")


class DimensionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ai_context: Optional[Dict[str, Any]] = None
    criteria: Optional[Dict[str, Any]] = None
    scoring_framework: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    group_ids: Optional[List[UUID]] = None


class Dimension(DimensionBase):
    id: UUID
    client_id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    groups: List[DimensionGroup] = []


class DimensionGroupMember(BaseModel):
    dimension_id: str
    dimension_name: str
    priority: int = 100
    added_at: datetime


# API Endpoints

@router.get("/dimension-groups", response_model=List[DimensionGroup])
async def list_dimension_groups(
    active_only: bool = Query(True, description="Filter to active groups only")
):
    """List all dimension groups."""
    try:
        async with db_pool.acquire() as conn:
            query = """
                SELECT dg.*, COUNT(dgm.dimension_id) as dimension_count
                FROM dimension_groups dg
                LEFT JOIN dimension_group_members dgm ON dg.id = dgm.group_id
                WHERE ($1 = false OR dg.is_active = true)
                GROUP BY dg.id
                ORDER BY dg.display_order, dg.name
            """
            
            rows = await conn.fetch(query, active_only)
            
            return [
                DimensionGroup(
                    id=row['id'],
                    group_id=row['group_id'],
                    name=row['name'],
                    description=row['description'],
                    selection_strategy=row['selection_strategy'],
                    max_primary_dimensions=row['max_primary_dimensions'],
                    display_order=row['display_order'],
                    color_hex=row['color_hex'],
                    icon=row['icon'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    dimension_count=row['dimension_count']
                )
                for row in rows
            ]
            
    except Exception as e:
        logger.error(f"Error listing dimension groups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list dimension groups"
        )


@router.post("/dimension-groups", response_model=DimensionGroup, status_code=status.HTTP_201_CREATED)
async def create_dimension_group(group: DimensionGroupCreate):
    """Create a new dimension group."""
    try:
        async with db_pool.acquire() as conn:
            # Check if group_id already exists
            existing = await conn.fetchval(
                "SELECT id FROM dimension_groups WHERE group_id = $1",
                group.group_id
            )
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Dimension group '{group.group_id}' already exists"
                )
            
            # Create the group
            row = await conn.fetchrow("""
                INSERT INTO dimension_groups (
                    group_id, name, description, selection_strategy,
                    max_primary_dimensions, display_order, color_hex, icon,
                    metadata, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
            """,
                group.group_id, group.name, group.description, group.selection_strategy,
                group.max_primary_dimensions, group.display_order, group.color_hex, group.icon,
                group.metadata, group.is_active
            )
            
            return DimensionGroup(
                id=row['id'],
                group_id=row['group_id'],
                name=row['name'],
                description=row['description'],
                selection_strategy=row['selection_strategy'],
                max_primary_dimensions=row['max_primary_dimensions'],
                display_order=row['display_order'],
                color_hex=row['color_hex'],
                icon=row['icon'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {},
                is_active=row['is_active'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                dimension_count=0
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating dimension group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dimension group"
        )


@router.get("/dimension-groups/{group_id}", response_model=DimensionGroup)
async def get_dimension_group(group_id: str):
    """Get a specific dimension group by ID."""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT dg.*, COUNT(dgm.dimension_id) as dimension_count
                FROM dimension_groups dg
                LEFT JOIN dimension_group_members dgm ON dg.id = dgm.group_id
                WHERE dg.id = $1::uuid OR dg.group_id = $1
                GROUP BY dg.id
            """, group_id)
            
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dimension group '{group_id}' not found"
                )
            
            return DimensionGroup(
                id=row['id'],
                group_id=row['group_id'],
                name=row['name'],
                description=row['description'],
                selection_strategy=row['selection_strategy'],
                max_primary_dimensions=row['max_primary_dimensions'],
                display_order=row['display_order'],
                color_hex=row['color_hex'],
                icon=row['icon'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {},
                is_active=row['is_active'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                dimension_count=row['dimension_count']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dimension group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dimension group"
        )


@router.get("/dimension-groups/{group_id}/members", response_model=List[DimensionGroupMember])
async def get_dimension_group_members(group_id: str):
    """Get all dimensions in a specific group."""
    try:
        async with db_pool.acquire() as conn:
            # First verify the group exists
            group_uuid = await conn.fetchval("""
                SELECT id FROM dimension_groups 
                WHERE id = $1::uuid OR group_id = $1
            """, group_id)
            
            if not group_uuid:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dimension group '{group_id}' not found"
                )
            
            # Get members
            rows = await conn.fetch("""
                SELECT dgm.*, gcd.name as dimension_name
                FROM dimension_group_members dgm
                JOIN generic_custom_dimensions gcd ON dgm.dimension_id = gcd.dimension_id
                WHERE dgm.group_id = $1
                ORDER BY dgm.priority, gcd.name
            """, group_uuid)
            
            return [
                DimensionGroupMember(
                    dimension_id=row['dimension_id'],
                    dimension_name=row['dimension_name'],
                    priority=row['priority'],
                    added_at=row['added_at']
                )
                for row in rows
            ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dimension group members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dimension group members"
        )


@router.get("/dimensions", response_model=List[Dimension])
async def list_dimensions(
    active_only: bool = Query(True, description="Filter to active dimensions only"),
    group_id: Optional[str] = Query(None, description="Filter by dimension group")
):
    """List all custom dimensions."""
    try:
        async with db_pool.acquire() as conn:
            # Base query
            query = """
                SELECT DISTINCT gcd.*
                FROM generic_custom_dimensions gcd
            """
            params = []
            
            # Add group filter if specified
            if group_id:
                query += """
                    JOIN dimension_group_members dgm ON gcd.dimension_id = dgm.dimension_id
                    JOIN dimension_groups dg ON dgm.group_id = dg.id
                    WHERE (dg.id = $1::uuid OR dg.group_id = $1)
                """
                params.append(group_id)
                
                if active_only:
                    query += " AND gcd.is_active = true"
            else:
                if active_only:
                    query += " WHERE gcd.is_active = true"
            
            query += " ORDER BY gcd.name"
            
            rows = await conn.fetch(query, *params)
            
            # Get groups for each dimension
            dimensions = []
            for row in rows:
                # Get associated groups
                group_rows = await conn.fetch("""
                    SELECT dg.*
                    FROM dimension_groups dg
                    JOIN dimension_group_members dgm ON dg.id = dgm.group_id
                    WHERE dgm.dimension_id = $1
                    ORDER BY dg.display_order
                """, row['dimension_id'])
                
                groups = [
                    DimensionGroup(
                        id=g['id'],
                        group_id=g['group_id'],
                        name=g['name'],
                        description=g['description'],
                        selection_strategy=g['selection_strategy'],
                        max_primary_dimensions=g['max_primary_dimensions'],
                        display_order=g['display_order'],
                        color_hex=g['color_hex'],
                        icon=g['icon'],
                        metadata=json.loads(g['metadata']) if g['metadata'] else {},
                        is_active=g['is_active'],
                        created_at=g['created_at'],
                        updated_at=g['updated_at']
                    )
                    for g in group_rows
                ]
                
                dimensions.append(Dimension(
                    id=row['id'],
                    client_id=row['client_id'],
                    dimension_id=row['dimension_id'],
                    name=row['name'],
                    description=row['description'],
                    ai_context=json.loads(row['ai_context']) if row['ai_context'] else {},
                    criteria=json.loads(row['criteria']) if row['criteria'] else {},
                    scoring_framework=json.loads(row['scoring_framework']) if row['scoring_framework'] else {},
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    created_by=row['created_by'],
                    groups=groups
                ))
            
            return dimensions
            
    except Exception as e:
        logger.error(f"Error listing dimensions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list dimensions"
        )


@router.post("/dimensions", response_model=Dimension, status_code=status.HTTP_201_CREATED)
async def create_dimension(dimension: DimensionCreate):
    """Create a new custom dimension."""
    try:
        async with db_pool.acquire() as conn:
            # Check if dimension_id already exists
            existing = await conn.fetchval(
                "SELECT id FROM generic_custom_dimensions WHERE dimension_id = $1",
                dimension.dimension_id
            )
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Dimension '{dimension.dimension_id}' already exists"
                )
            
            # Create the dimension
            row = await conn.fetchrow("""
                INSERT INTO generic_custom_dimensions (
                    client_id, dimension_id, name, description,
                    ai_context, criteria, scoring_framework, metadata,
                    is_active
                ) VALUES ('default', $1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb, $8)
                RETURNING *
            """,
                dimension.dimension_id, dimension.name, dimension.description,
                dimension.ai_context, dimension.criteria, dimension.scoring_framework,
                dimension.metadata, dimension.is_active
            )
            
            # Add to groups if specified
            groups = []
            if dimension.group_ids:
                for group_id in dimension.group_ids:
                    await conn.execute("""
                        INSERT INTO dimension_group_members (group_id, dimension_id)
                        VALUES ($1, $2)
                    """, group_id, dimension.dimension_id)
                    
                    # Get group info
                    group_row = await conn.fetchrow(
                        "SELECT * FROM dimension_groups WHERE id = $1",
                        group_id
                    )
                    if group_row:
                        groups.append(DimensionGroup(
                            id=group_row['id'],
                            group_id=group_row['group_id'],
                            name=group_row['name'],
                            description=group_row['description'],
                            selection_strategy=group_row['selection_strategy'],
                            max_primary_dimensions=group_row['max_primary_dimensions'],
                            display_order=group_row['display_order'],
                            color_hex=group_row['color_hex'],
                            icon=group_row['icon'],
                            metadata=group_row['metadata'] or {},
                            is_active=group_row['is_active'],
                            created_at=group_row['created_at'],
                            updated_at=group_row['updated_at']
                        ))
            
            return Dimension(
                id=row['id'],
                client_id=row['client_id'],
                dimension_id=row['dimension_id'],
                name=row['name'],
                description=row['description'],
                ai_context=row['ai_context'] or {},
                criteria=row['criteria'] or {},
                scoring_framework=row['scoring_framework'] or {},
                metadata=json.loads(row['metadata']) if row['metadata'] else {},
                is_active=row['is_active'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                created_by=row['created_by'],
                groups=groups
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating dimension: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dimension"
        )


@router.delete("/dimensions/{dimension_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dimension(dimension_id: str):
    """Delete a custom dimension (soft delete)."""
    try:
        async with db_pool.acquire() as conn:
            # Check if dimension exists
            existing = await conn.fetchval(
                "SELECT id FROM generic_custom_dimensions WHERE dimension_id = $1",
                dimension_id
            )
            
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dimension '{dimension_id}' not found"
                )
            
            # Soft delete
            await conn.execute("""
                UPDATE generic_custom_dimensions 
                SET is_active = false, updated_at = CURRENT_TIMESTAMP
                WHERE dimension_id = $1
            """, dimension_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dimension: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dimension"
        )
