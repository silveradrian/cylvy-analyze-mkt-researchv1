"""Base models for common API responses"""
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class HealthCheck(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
    
    
class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")
    
    
class SuccessResponse(BaseModel):
    """Standard success response model"""
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    
    
class PaginatedResponse(BaseModel):
    """Paginated response model"""
    items: list = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(1, description="Current page number")
    per_page: int = Field(20, description="Items per page")
    pages: int = Field(..., description="Total number of pages")